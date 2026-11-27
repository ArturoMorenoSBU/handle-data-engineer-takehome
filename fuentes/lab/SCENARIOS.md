# Source behavior

This is the synthetic read-only Brújula Seguros portal, one of the two example carriers. It runs only on loopback. Its demo login is a convenience for exercising account-scoped extraction, not production authentication. Aurora's separate CSV exports and source versions are described in `fixtures/README.md` and `fixtures/aurora/manifest.json`.

## Scenarios

Select a scenario when launching the server. Restarting changes the source snapshot and clears demo sessions; it does not touch your POC's captures or database.

| Scenario | Behavior | Exercise scope |
| --- | --- | --- |
| `baseline` | Two broker accounts; policies and paginated receipts. | Starting source |
| `corrected` | Only Alder receipt R-102 changes: amount 25.00 → 30.00 and revision 1 → 2. | A later source version |
| `failure` | Alder receipt page 2 and its receipt-detail URLs return HTTP 503. No full receipt export is available. | Optional discussion/probe |
| `drift` | Alder receipt page 2 uses JSON key `items` instead of `receipts`; its amount header also changes. | Optional discussion/probe |

These are available investigation tools, not a feature checklist or hidden grading traps. Decide which help you demonstrate your approach. There is no need to implement an autonomous repair system.

## Portal semantics

- Each login sees only its own broker book. IDs are source-local: two brokers can have the same policy and receipt numbers.
- `amount` is the installment amount, in **USD**, represented as decimal text. An `outstanding` installment contributes to known outstanding amount; a `paid` one does not. `TBD` is not a number.
- Source revisions belong to a receipt, not to a broker. Capturing a response later does not manufacture a new source revision.
- A missing field means not supplied. Explicit JSON `null` is a distinct source statement. Neither supplies a date.
- The baseline policies surface lists the policies available in this demo login; it is not independent proof of the broker's whole book. `reference/book.csv` is a separate broker-provided inventory, scoped to this exercise. Report gaps with that scope, not as evidence that a policy was cancelled.
- Counts on paginated responses describe offered source rows, not a data-quality verdict. A failed page is not an empty page.
- Amounts and statuses on the portal are Brújula statements. Do not apply Brújula's formats or labels to another carrier without checking that source's meaning.

Explore the site and its responses to find the extraction surface. The lab has no rate limits or real CAPTCHA/MFA puzzle.
