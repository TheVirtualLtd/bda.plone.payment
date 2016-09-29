import logging
from zExceptions import Redirect
from zope.i18nmessageid import MessageFactory
from Products.Five import BrowserView
from Products.CMFCore.utils import getToolByName
from bda.plone.orders.common import OrderData
from tvl.payment.dps import dps
from tvl.payment.dps.dps_parameters import DPSConfig
from bda.plone.orders import interfaces as ifaces
from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import getSecurityManager
from AccessControl.SecurityManagement import setSecurityManager
from plone import api
from ..interfaces import IPaymentData
from ..interfaces import ISurcharge
from .. import Payment
from .. import Payments
import os
import sys
import traceback


logger = logging.getLogger('bda.plone.payment')
_ = MessageFactory('bda.plone.payment')

DEPLOYMENT = os.environ.get('deployment', '')


class PxPayPayment(Payment):
    pid = 'pxpay_payment'

    @property
    def label(self):
        settings = ISurcharge(self.context)
        if settings.percent_surcharge and settings.fixed_surcharge:
            return _('pxpay_payment',
                     default=u'Credit card - DPS PaymentExpress - '
                             u'surcharge of ${percent}% '
                             u'and ${fixed} ${currency} '
                             u'added to the order total',
                     mapping={
                         'percent': settings.percent_surcharge,
                         'fixed': settings.fixed_surcharge,
                         'currency': settings.currency
                         })
        elif settings.percent_surcharge:
            return _('pxpay_payment',
                     default=u'Credit card - DPS PaymentExpress - '
                             u'${percent}% surcharge '
                             u'added to the order total',
                     mapping={
                         'percent': settings.percent_surcharge,
                         })
        elif settings.fixed_surcharge:
            return _('pxpay_payment',
                     default=u'Credit card - DPS PaymentExpress - '
                             u'surcharge of ${fixed} ${currency} '
                             u'added to the order total',
                     mapping={
                         'fixed': settings.fixed_surcharge,
                         'currency': settings.currency,
                         })
        else:
            return _('pxpay_payment', 'Credit card - DPS PaymentExpress')

    def init_url(self, uid):
        return '%s/@@pxpay_payment?uid=%s' % (api.portal.get().absolute_url(),
                                              uid)


class PxPayError(Exception):
    """Raised if PxPay payment return an error.
    """


class PxPay(BrowserView):

    def __call__(self):
        base_url = api.portal.get().absolute_url()
        order_uid = self.request['uid']
        logger.info('Start')
        try:
            data = IPaymentData(self.context).data(order_uid)
            dps_parms = DPSConfig()
            req = dps.GenerateRequest()
            req.PxPayUserId = dps_parms.PxPayUserId
            req.PxPayKey = dps_parms.PxPayKey
            req.AmountInput = "%0.2f" % (float(data['amount']) / 100.0)
            req.CurrencyInput = data['currency']
            req.MerchantReference = data['ordernumber']
            req.TxnData1 = 'IPurchaseProcess'
            req.TxnData2 = order_uid
            req.add_txn_parameters(ordernumber=data['ordernumber'])
            if not api.user.is_anonymous():
                req.add_txn_parameters(
                    member_id=api.user.get_current().getMemberId())
            req.TxnType = 'Purchase'
            # req.UrlFail = req.UrlSuccess = self.context.portal_url() + '/ipn'
            req.UrlSuccess = '%s/@@pxpay_payment_success' % base_url
            req.UrlFail = '%s/@@pxpay_payment_failed' % base_url
            # backlink = '%s/@@pxpay_payment_aborted?uid=%s' \
            #    % (base_url, order_uid)
            logger.info("Auth: %s" % req)
            result = req.getResponse()
            logger.info(result)
            if not result.valid:
                logger.info("Auth Error: %s" % result)
                raise PxPayError('Problem Initialising Payment')
            redirect_url = result.URI
        except Exception, e:
            logger.error(u"Could not initialize payment: '%s'" % str(e))
            redirect_url = '%s/@@pxpay_payment_failed?uid=%s' \
                % (base_url, order_uid)

        raise Redirect(redirect_url)


def shopmaster_mail(context):
    props = getToolByName(context, 'portal_properties')
    return props.site_properties.email_from_address


def restore_user(old_security_manager, new_roles):
    if old_security_manager:
        user = api.user.get_current()
        if new_roles:
            api.user.revoke_roles(user=user, roles=new_roles)
        logger.info("restoring user: {} roles: {}".format(
            user, api.user.get_roles()))
        if new_roles:
            for role in new_roles:
                assert role not in api.user.get_roles()
        setSecurityManager(old_security_manager)


class PxPaySuccess(BrowserView):

    def verify(self):
        old_security_manager = None  # Used for anon notification IPN
        new_roles = None
        receipt = None
        success = None
        try:
            result = self.request.get('result', '')
            if result:
                dps_parms = DPSConfig()
                req = dps.ProcessResponse()
                req.PxPayUserId = dps_parms.PxPayUserId
                req.PxPayKey = dps_parms.PxPayKey
                req.Response = result
                receipt = req.getResponse()
                logger.info(receipt)

                uid = receipt.TxnData2
                # payment = Payments(self.context).get('pxpay_payment')
                if receipt.ResponseText == 'APPROVED':
                    success = True
                else:
                    success = False
                    logger.error(u"Payment completion failed: '%s' uid %s" %
                                 (receipt.MerchantReference, uid))
                ordernumber = receipt.MerchantReference
                tid = receipt.DpsTxnRef  # ????
                order_uid = IPaymentData(self.context).uid_for(ordernumber)
                order_uid = receipt.TxnData2
                payment = Payments(self.context).get('pxpay_payment')
                order = OrderData(self.context, uid=order_uid)
                self._receipt = receipt
                # Already Processed
                try:
                    receipt = order.receipt
                    success = False
                except AttributeError:
                    pass

            else:
                receipt = None
                success = False
                tid = None

            evt_data = {'tid': tid, 'receipt': receipt}

            if (api.user.is_anonymous() and receipt and
                    receipt.tvl_txn_parameters.get('member_id', None)):
                # We need to act as the user in case of anon ipn from DPS.
                # This is needed to send email and such if basket content is
                # not available to Anon users
                # Unfortunately we can't just use a context manager as things
                # happen in events outside the block
                old_security_manager = getSecurityManager()
                with api.env.adopt_roles(roles=['Manager']):
                    user = api.user.get(
                        # userid=receipt.tvl_txn_parameters['member_id'])
                        userid='amauser')
                    newSecurityManager(self.request, user)
                    # Need to have access to content
                    old_roles = api.user.get_roles()
                    if set(['SiteAdministrator',
                            'Manager']).isdisjoint(old_roles):
                        new_roles = ['SiteAdministrator']
                        api.user.grant_roles(
                            user=user, roles=new_roles)
                        logger.info("user {} roles: {} : new roles: {}".format(
                            api.user.get_current(), api.user.get_roles()))
                logger.info("promoting user: {} roles: {}".format(
                    api.user.get_current(), new_roles))

            # TID is added as part of event processing for success or fail.
            # ensure events are only triggered once.
            if tid in order.tid:
                logger.info("Payment with tid: {} has already been "
                            "returned".format(tid))
                return success
            elif success:
                payment.succeed(self.request, order_uid, evt_data)
                restore_user(old_security_manager, new_roles)
                return True
            else:
                payment.failed(self.request, order_uid, evt_data)
                restore_user(old_security_manager, new_roles)
                return False
        except Exception, e:
            restore_user(old_security_manager, new_roles)

            msg = "Receipt: {}\nsuccess: {}\n\n {}".format(
                receipt,
                success,
                ''.join(traceback.format_exception(*sys.exc_info())))

            api.portal.send_email(
                recipient='support@thevirtual.co.nz',
                subject="{} - {} PXPay Payment Error".format(
                    DEPLOYMENT, api.portal.get().Title()),
                body=msg)
            logger.error(u"Payment verification failed: '%s'" % str(e))
            return False

    @property
    def receipt(self):
        try:
            return self._receipt

        except AttributeError:
            return None

    @property
    def shopmaster_mail(self):
        return shopmaster_mail(self.context)


class PxPayFailed(BrowserView):

    def finalize(self):
        dps_parms = DPSConfig()
        result = self.request.get('result', '')
        if result:
            req = dps.ProcessResponse()
            req.PxPayUserId = dps_parms.PxPayUserId
            req.PxPayKey = dps_parms.PxPayKey
            req.Response = result

            receipt = req.getResponse()
            self._receipt = receipt
            logger.info(receipt)
            uid = receipt.TxnData2
            tid = receipt.DpsTxnRef  # ????
        else:
            uid = self.request.get('uid', '')
            tid = None
            receipt = None

        payment = Payments(self.context).get('pxpay_payment')
        payment.failed(self.request, uid, {'tid': tid,
                       'receipt': receipt})

    @property
    def receipt(self):
        try:
            return self._receipt
        except AttributeError:
            return None

    @property
    def shopmaster_mail(self):
        return shopmaster_mail(self.context)


def payment_success(event):
    if event.payment.pid == 'pxpay_payment':
        data = event.data
        order = OrderData(event.context, uid=event.order_uid)
        # Processed already
        if data['tid'] in order.tid:
            return
        order.salaried = ifaces.SALARIED_YES
        order.tid = data['tid']
        order.receipt = data['receipt']


def payment_failed(event):
    if event.payment.pid == 'pxpay_payment':
        data = event.data
        order = OrderData(event.context, uid=event.order_uid)
        # Processed already
        if data['tid'] in order.tid:
            return
        order.salaried = ifaces.SALARIED_FAILED
        order.tid = data['tid']
        order.receipt = data['receipt']
