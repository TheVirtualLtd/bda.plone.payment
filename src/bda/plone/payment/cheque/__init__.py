from zope.i18nmessageid import MessageFactory
from Products.Five import BrowserView
from bda.plone.orders.common import get_order
from bda.plone.payment import Payment
from bda.plone.payment import Payments


_ = MessageFactory('bda.plone.payment')


class Cheque(Payment):
    pid = 'cheque'
    label = _('cheque', default=u'Cheque')

    def init_url(self, uid):
        return '%s/@@cheque?uid=%s' % (self.context.absolute_url(), uid)


class DoCheque(BrowserView):

    def __call__(self, **kw):
        uid = self.request['uid']
        payment = Payments(self.context).get('cheque')
        payment.succeed(self.request, uid)
        url = '%s/@@cheque_done?uid=%s' % (self.context.absolute_url(), uid)
        self.request.response.redirect(url)


class ChequeFinished(BrowserView):

    def id(self):
        uid = self.request.get('uid', None)
        try:
            order = get_order(self.context, uid)
        except ValueError:
            return None
        return order.attrs.get('ordernumber')
