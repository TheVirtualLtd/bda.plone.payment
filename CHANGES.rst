
Changelog
=========

0.3
---

- Remove ``bda.plone.payment.six_payment.ISixPaymentData`` interface. Use
  ``bda.plone.payment.interfaces.IPaymentData`` instead.
  [rnix]


0.2
---

- show "emails sent" status message when displaying the
  "thanks for your order" page of the invoce payment processor.
  in addition, show the order id
  [fRiSi]

- fix lookup for default IPayment adapter in case no default adapter
  is registered
  [fRiSi]


0.1
---

- initial work
  [rnix]
