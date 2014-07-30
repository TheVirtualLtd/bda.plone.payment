import logging
from zExceptions import Redirect
from zope.i18nmessageid import MessageFactory
from Products.Five import BrowserView
from Products.CMFCore.utils import getToolByName
from bda.plone.orders.common import OrderData
from tvl.payment.dps import dps
from tvl.payment.dps.dps_parameters import DPSConfig
from bda.plone.orders import interfaces as ifaces
from ..interfaces import IPaymentData
from .. import Payment
from .. import Payments


logger = logging.getLogger('bda.plone.payment')
_ = MessageFactory('bda.plone.payment')


class PxPayPayment(Payment):
    pid = 'pxpay_payment'
    label = _('pxpay_payment', 'DPS PaymentExpress')
    available = True
    default = True

    def init_url(self, uid):
        return '%s/@@pxpay_payment?uid=%s' % (self.context.absolute_url(), uid)


class PxPayError(Exception):
    """Raised if PxPay payment return an error.
    """

class PxPay(BrowserView):

    def __call__(self):
        base_url = self.context.absolute_url()
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
            parms = []
            parms.append('description=%s' % data['description'])
            parms.append('ordernumber=%s' % data['ordernumber'])
            req.TxnData3 = ','.join(parms)
            req.TxnType = 'Purchase'
            #req.UrlFail = req.UrlSuccess = self.context.portal_url() + '/ipn'
            req.UrlSuccess = '%s/@@pxpay_payment_success' % base_url
            req.UrlFail = '%s/@@pxpay_payment_failed' % base_url
            #backlink = '%s/@@pxpay_payment_aborted?uid=%s' \
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


class PxPaySuccess(BrowserView):

    def verify(self):
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
                #payment = Payments(self.context).get('pxpay_payment')
                if receipt.ResponseText == 'APPROVED':
                    success = True
                else:
                    success = False
                    logger.error(u"Payment completion failed: '%s'" %
                            receipt.MerchantReference)
                ordernumber = receipt.MerchantReference
                tid = receipt.DpsTxnRef # ????
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
            if success:
                payment.succeed(self.request, order_uid, evt_data)
                return True
            else:
                payment.failed(self.request, order_uid, evt_data)
                return False
        except Exception, e:
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
            tid = receipt.DpsTxnRef # ????
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
