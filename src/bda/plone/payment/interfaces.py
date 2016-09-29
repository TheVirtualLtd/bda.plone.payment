from zope.interface import Interface
from zope.interface import Attribute


class IPaymentExtensionLayer(Interface):
    """Browser layer for bda.plone.payment.
    """


class IPaymentEvent(Interface):
    """Payment related event.
    """
    context = Attribute(u"Context in which this event was triggered.")

    request = Attribute(u"Current request.")

    payment = Attribute(u"Payment instance.")

    order_uid = Attribute(u"Referring order uid.")

    data = Attribute(u"Optional data as dict")


class IPaymentSuccessEvent(IPaymentEvent):
    """This event gets triggered when payment was successful.
    """


class IPaymentFailedEvent(IPaymentEvent):
    """This event gets triggered when payment failed.
    """


class IPaymentSettings(Interface):
    """Payment availability and default settings.
    """
    available = Attribute(u"List of available payment method ids")

    default = Attribute(u"Default payment method")


class IPayment(Interface):
    """Single payment.
    """
    pid = Attribute(u"Unique payment id. Payment adapter is also registered "
                    u"under this name.")

    label = Attribute(u"Payment label")

    available = Attribute(u"Flag whether payment is available in recent "
                          u"payment cycle")

    default = Attribute(u"Flag whether this payment is default payment.")

    def init_url(uid):
        """Return payment initialization URL.
        """

    def succeed(request, order_uid, data=dict()):
        """Notify ``IPaymentSuccessEvent``.
        """

    def failed(request, order_uid, data=dict()):
        """Notify ``IPaymentFailedEvent``.
        """


class IPaymentData(Interface):
    """Interface for providing data required by payment.
    """

    def uid_for(ordernumber):
        """Return order_uid for ordernumber.
        """

    def data(order_uid):
        """Return dict containing payment related order data like:

        {
            'amount': '1000',
            'currency': 'EUR',
            'description': 'description',
            'ordernumber': '1234567890',
        }
        """


class ISurcharge(Interface):
    """Interface for providing surcharge information
    """

    currency = Attribute(u"Currency of cash on delivery")

    fixed_surcharge = Attribute(u"Fixed surcharge in gross to add to total")

    percent_surcharge = Attribute(u"Percentage surcharge to be added to total")

    label = Attribute(u"Payment method label")

    description = Attribute(u"Payment method description")

    def surcharge(total):  # noqa: N805
        """Calculate surcharge based on fixed and/or percentage surcharge given
        the total from the cart and returned as a Decimal.

        :param total: working total form cart
        """
