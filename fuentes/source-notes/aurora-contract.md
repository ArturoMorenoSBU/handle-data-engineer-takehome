# Aurora Demo export notes

Source: synthetic carrier export guide AUR-01, 2026-11-02.
Carrier: Aurora Demo (`aurora`). Owner: carrier integration engineering.
Status: accepted description of the supplied files, not a proposed common schema.

The exports are UTF-8, semicolon-separated CSV. Amounts use a decimal comma and may contain a period as a thousands separator. Dates are day/month/year. `moeda` is the stated currency. No exchange rates are supplied.

Policy export:
- `corretora`: the broker account (`alder` or `birch`).
- `numero_apolice`: the carrier's policy identifier. Leading zeros matter.
- `segurado_ref`: Aurora's local insured reference, not Brújula's customer reference.
- `ramo`: carrier line-of-business label; `AUTO` and `PATRIMONIAL` are source labels.
- `situacao`: `ATIVA` states that the policy is active.
- `inicio_vigencia` and `fim_vigencia`: policy coverage dates, not installment due dates.
- `premio_total`: policy premium, not an amount to add to receipt amounts.

Receipt export:
- `id_cobranca`: the source collection/receipt identifier, meaningful within this carrier and broker account.
- `numero_parcela`: installment number; `valor_parcela` is the installment amount.
- `status_cobranca`: `EM_ABERTO` means open; `LIQUIDADO` means paid. `EM_CONCILIACAO` means under reconciliation and does not establish a final paid or unpaid state.
- `vencimento`: due date; `data_pagamento`: stated payment date, empty when not supplied.
- `revisao`: the source revision for that receipt.

An identical row can appear twice in one delivered file. Row position is not a stable business identifier. Later exports may change a receipt's state; they do not erase the earlier evidence. A missing row alone is not a cancellation statement.

The examples include a malformed date. Preserve the distinction between a source value, its meaning and whether it passes your checks. Do not silently repair it from another field or assume that an unfamiliar state is paid.
