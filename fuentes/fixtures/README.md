# Example carrier sources

All records are synthetic. The two carriers deliberately describe similar insurance concepts differently. These are sample inputs for your POC, not a required target schema or an extraction implementation.

| Carrier | Supplied source | Native shape |
| --- | --- | --- |
| Brújula Seguros (`brujula`) | The local portal in `lab/`; its backing example records are in `lab/fixtures.json` | Paginated JSON, English field names, decimal amounts, ISO dates, USD |
| Aurora Demo (`aurora`) | The CSV exports in `fixtures/aurora/` | Semicolon-separated files, Portuguese field names and statuses, decimal-comma amounts, day/month/year dates, BRL |

The same broker, policy number or receipt number can appear at both carriers. Matching text alone does not establish that two records are the same policy or receipt. There is no cross-carrier identity crosswalk or exchange-rate feed in this packet.

Brújula has a runnable source surface; Aurora is an example of a carrier that supplies files. You do not need to build another portal. Use both carriers to explore what should be shared and what remains source-specific. Choose a small useful scope within the four-hour timebox; handling every field or scenario is not expected.

Read `source-notes/aurora-contract.md` for the meaning of the Aurora columns. `aurora/manifest.json` identifies the available export versions. The corrected version is a later observation, not permission to discard earlier evidence.
