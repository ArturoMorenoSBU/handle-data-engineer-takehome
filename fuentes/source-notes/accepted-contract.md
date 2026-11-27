# Accepted source contract: receipt amount

Source: synthetic data-contract review CONTRACT-17, 2026-11-02.
Carrier: Brújula Seguros (`brujula`).
Owner: carrier integration engineering.
Status: accepted.

`amount` is the carrier's installment amount in USD decimal text. It may be included in an amount aggregate only when it is a valid monetary value. The literal `TBD` means the source has not supplied a usable amount; it is not zero.

Retain the original value and make its quality disposition inspectable. A current accepted view can omit an invalid field or record if the missing contribution is explicit. Do not change an entity's identity because its amount is corrected.
