from zope.i18nmessageid import MessageFactory
from Products.Five import BrowserView
from bda.plone.payment import (
    Payment,
    Payments,
)


_ = MessageFactory('bda.plone.payment')


class Invoice(Payment):
    pid = 'invoice'
    label = _('invoice', 'Invoice')
    available = True
    default = False
    
    def init_url(self, uid):
        return '%s/@@invoice?uid=%s' % (self.context.absolute_url(), uid)


class InvoiceFinished(BrowserView):
    
    def finalize(self):
        payment = Payments(self.context).get('invoice')
        payment.succeed(self.request, self.request['uid'])
