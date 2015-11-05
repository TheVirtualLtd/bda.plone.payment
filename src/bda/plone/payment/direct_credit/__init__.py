from zope.i18nmessageid import MessageFactory
from Products.Five import BrowserView
from bda.plone.orders.common import get_order
from bda.plone.payment import Payment
from bda.plone.payment import Payments


_ = MessageFactory('bda.plone.payment')


class DirectCredit(Payment):
    pid = 'direct_credit'
    label = _('direct_credit', default=u'DirectCredit')

    def init_url(self, uid):
        return '%s/@@direct_credit?uid=%s' % (self.context.absolute_url(), uid)


class DoDirectCredit(BrowserView):

    def __call__(self, **kw):
        uid = self.request['uid']
        payment = Payments(self.context).get('direct_credit')
        payment.succeed(self.request, uid)
        url = '%s/@@directcredituid=%s' % (self.context.absolute_url(), uid)
        self.request.response.redirect(url)


class DirectCreditFinished(BrowserView):

    def id(self):
        uid = self.request.get('uid', None)
        try:
            order = get_order(self.context, uid)
        except ValueError:
            return None
        return order.attrs.get('ordernumber')
