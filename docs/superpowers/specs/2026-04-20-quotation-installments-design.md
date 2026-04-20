# Quotation Installments — Design Spec

**Date:** 2026-04-20
**App:** `dantata_town`
**Scope:** Add a simplified installment planner on top of ERPNext's existing `payment_schedule` feature on Quotation. User picks `Installment` vs `Outright`; for Installment, fills deposit + start date + number of months, clicks a button, and a schedule of `payment_schedule` rows is generated. Third Phase 2 sub-project (after Project Type refactor and Allocation Letter).

## Background

Sales uses ERPNext's Quotation to prepare property offers for Dantata Town customers. Payment structure today is worked out by hand, then transcribed into the Allocation Letter as a 4-row schedule. The client wants:

1. A single choice on each Quotation — full payment or installment plan.
2. For installment plans, a quick UI for the common case: "X down, Y monthly payments for the balance".
3. Auto-populated schedule rows so sales doesn't re-type dates and amounts.
4. Those rows to flow downstream into the Sales Order, and eventually the Allocation Letter.

ERPNext already has a `Payment Schedule` child table on Quotation (and Payment Terms Template). This sub-project is a thin custom wrapper that writes those native rows, so we stay compatible with all of ERPNext's downstream invoicing.

## Goals

1. Make `payment_type` an explicit, required choice on Quotation (`Installment` or `Outright`).
2. Capture deposit / start date / number of months as three simple fields when the user picks Installment.
3. Provide a `Generate Installment Schedule` button that rewrites `payment_schedule` rows from those three inputs.
4. Amounts must sum exactly to the Quotation's `grand_total`; due dates must use `add_months` for month-end safety.
5. Rows written are standard `Payment Schedule` children — so ERPNext's existing Quotation → Sales Order mapper carries them over for free.
6. Extend the existing `make_allocation_letter` helper to pre-fill the Allocation Letter's `installment_schedule` child table from the Sales Order's `payment_schedule`.

## Non-goals

- Replacing or competing with ERPNext's existing `payment_terms_template` flow. Users who already have templates configured can still use them — our Generate button just overwrites the current rows when clicked.
- Supporting non-monthly cadences (quarterly, 90-day, biweekly). If the client needs those later, an `installment_interval` field can be added; not needed for this iteration.
- Supporting non-equal monthly amounts (20/30/30/20 patterns). If needed, the user can manually edit individual rows after generation — our auto-generator only produces deposit + equal monthly.
- Signature workflow / approval on Quotation — out of scope.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Thin custom wrapper that writes to ERPNext's native `payment_schedule`. | Preserves Quotation → Sales Order → Sales Invoice inheritance that ERPNext does for free; avoids duplicating the payment-schedule feature. |
| 2 | Four custom fields on Quotation: `payment_type` (Select), `installment_deposit_amount` (Currency), `installment_start_date` (Date), `installment_months` (Int). | Matches Gbenga's "deposit + months" mental model exactly. |
| 3 | Schedule = 1 deposit row at `installment_start_date` + N equal monthly rows at `start + 1, 2, ..., N months`. Last monthly row absorbs rounding drift. | Simplest structure that sums exactly to `grand_total` and matches the meeting description. Deviations from equal split are handled by the user hand-editing individual rows after generation. |
| 4 | Due dates use `frappe.utils.add_months`. | Safe for month-end edge cases (Jan 31 + 1 month = Feb 28/29). |
| 5 | Manual button to generate; no auto-regenerate on field change. | Matches the existing `Create BOQ` / `Create Allocation Letter` button idiom in this app. Preserves any manual row edits. |
| 6 | Select labels are `Installment` / `Outright`. | Same terminology as the Allocation Letter's `purchase_price_option` — cross-doc consistency for sales staff. |
| 7 | Outright clears installment_* fields but **not** `payment_schedule` rows. | `payment_schedule` is ERPNext's native feature and may have rows from other flows (Payment Terms Template); we don't own it. Our scope is only the `installment_*` fields. |
| 8 | Generator lives in a new file `dantata_town/dantata_town/quotation.py`, not `utils.py`. | `utils.py` is already mixing BOQ consumption hooks, Project validators, and the site validator. Fresh per-doctype module keeps boundaries clean going forward. |

## Architecture

### Custom fields on Quotation

Installed via `create_custom_fields` in the existing `setup.py` (same pattern used for `Project.project_subtype`, BOQ fields, etc.). All fields in the Terms tab, clustered together so the form reads as a single "Payment Type" block:

| Fieldname | Type | Insert after | Config |
|---|---|---|---|
| `dt_installment_section` | Section Break | `terms_tab` | Label: "Payment Type" |
| `payment_type` | Select | `dt_installment_section` | Options: `\nInstallment\nOutright`. Required. |
| `installment_column_break` | Column Break | `payment_type` | — |
| `installment_start_date` | Date | `installment_column_break` | `depends_on: eval:doc.payment_type === 'Installment'`, `mandatory_depends_on` same |
| `installment_deposit_amount` | Currency | `installment_start_date` | `depends_on` + `mandatory_depends_on` same |
| `installment_months` | Int | `installment_deposit_amount` | `depends_on` + `mandatory_depends_on` same |

All registered under `module: "Dantata Town"`.

### Generator (`dantata_town/dantata_town/quotation.py`)

```python
import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate


@frappe.whitelist()
def generate_installment_schedule(quotation_name):
    """Rewrite the Quotation's payment_schedule child table from
    installment_deposit_amount + installment_start_date + installment_months.
    """
    doc = frappe.get_doc("Quotation", quotation_name)
    _validate_installment_inputs(doc)

    total = flt(doc.grand_total)
    deposit = flt(doc.installment_deposit_amount)
    months = int(doc.installment_months)
    start = getdate(doc.installment_start_date)

    balance = total - deposit
    per_month = flt(balance / months, 2)
    last_month = flt(balance - per_month * (months - 1), 2)

    doc.set("payment_schedule", [])
    doc.append("payment_schedule", {
        "due_date": start,
        "payment_amount": deposit,
        "invoice_portion": flt(deposit / total * 100, 6),
        "description": _("Deposit"),
    })
    for i in range(1, months + 1):
        amount = per_month if i < months else last_month
        doc.append("payment_schedule", {
            "due_date": add_months(start, i),
            "payment_amount": amount,
            "invoice_portion": flt(amount / total * 100, 6),
            "description": _("Installment {0} of {1}").format(i, months),
        })
    doc.save()
    return doc


def validate_quotation_payment_type(doc, method=None):
    """Doc hook: clear installment fields if Outright; validate on submit if Installment."""
    if doc.payment_type == "Outright":
        doc.installment_deposit_amount = None
        doc.installment_start_date = None
        doc.installment_months = None
        return
    if doc.payment_type == "Installment":
        # Only hard-validate on submit; drafts are permissive so users can fill in gradually.
        if doc.docstatus == 0:
            return
        _validate_installment_inputs(doc)


def _validate_installment_inputs(doc):
    if flt(doc.installment_deposit_amount) <= 0:
        frappe.throw(_("Installment Deposit Amount must be greater than zero."))
    if flt(doc.installment_deposit_amount) >= flt(doc.grand_total):
        frappe.throw(_("Installment Deposit Amount must be less than the Quotation total."))
    if not doc.installment_start_date:
        frappe.throw(_("Installment Start Date is required for installment plans."))
    if not doc.installment_months or int(doc.installment_months) < 1:
        frappe.throw(_("Installment Months must be at least 1."))
```

### Doc-event wiring (`hooks.py`)

Add to the existing `doc_events`:

```python
"Quotation": {
    "validate": "dantata_town.dantata_town.quotation.validate_quotation_payment_type",
},
```

Add to the existing `doctype_js`:

```python
"Quotation": "public/js/quotation.js",
```

### Client script (`dantata_town/public/js/quotation.js`)

```javascript
frappe.ui.form.on("Quotation", {
    refresh(frm) {
        if (
            frm.doc.payment_type === "Installment"
            && frm.doc.docstatus === 0
            && !frm.is_new()
            && frm.doc.installment_deposit_amount
            && frm.doc.installment_start_date
            && frm.doc.installment_months
        ) {
            frm.add_custom_button(__("Generate Installment Schedule"), () => {
                frappe.call({
                    method: "dantata_town.dantata_town.quotation.generate_installment_schedule",
                    args: { quotation_name: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Generating schedule..."),
                    callback: () => frm.reload_doc(),
                });
            });
        }
    },

    payment_type(frm) {
        if (frm.doc.payment_type === "Outright") {
            frm.set_value("installment_deposit_amount", null);
            frm.set_value("installment_start_date", null);
            frm.set_value("installment_months", null);
        }
    },
});
```

### Allocation Letter integration

Extend `make_allocation_letter` in `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py`:

- When the source Sales Order has `payment_schedule` rows, map them into the target AL's `installment_schedule` child table:
  - `sequence_label`: "First", "Second", "Third", "Fourth", or `Installment {idx}` for rows past the fourth.
  - `amount`: `row.payment_amount`.
  - `due_date`: `row.due_date`.
- If the SO has no `payment_schedule` (Outright deal), no rows are mapped — user fills manually.

A small helper `_label_for(idx)` inside the module handles the sequence-label logic with a constant list `["First", "Second", "Third", "Fourth"]` plus an `Installment {idx + 1}` fallback.

## Data flow

1. Sales user creates a Quotation as usual, adds items, save → `grand_total` populates.
2. User toggles `payment_type` in Terms tab. Picking `Installment` reveals the three installment fields.
3. User fills start date, deposit, and months. Form refresh shows the `Generate Installment Schedule` button.
4. Click → server rewrites `payment_schedule` with 1 deposit row + N monthly rows. UI reloads; schedule is visible in the standard `payment_schedule` grid.
5. User hand-edits any rows if needed (e.g. to match a 20/30/30/20 structure the customer negotiated).
6. Save → Submit Quotation.
7. Convert to Sales Order — ERPNext's standard mapper carries `payment_schedule` over unchanged.
8. From the SO, user clicks `Create → Allocation Letter`. Extended `make_allocation_letter` maps the SO's `payment_schedule` into the AL's `installment_schedule` with First/Second/Third/Fourth labels.

## Error handling

- Generator rejects `deposit <= 0`, `deposit >= total`, missing start date, `months < 1`. All with specific messages surfaced via `frappe.throw`.
- On submit of an Installment Quotation with missing fields, `validate_quotation_payment_type` throws before docstatus changes.
- On `payment_type = Outright` save, installment_* fields are silently cleared. No error — symmetric with Allocation Letter.
- If `grand_total` changes after generation, the user will get ERPNext's built-in "payment schedule total != total" error on next save. They regenerate. We do not auto-regenerate — would destroy manual edits.
- Generator is re-runnable; clicking twice replaces the rows, no accumulation.

## Testing

### Unit tests (`dantata_town/dantata_town/tests/test_quotation_installments.py`)

1. **Custom fields installed** — assert the 4 installment-related fields exist on Quotation with correct `depends_on` expressions after `create_boq_custom_fields()`.
2. **Outright clears installment fields on save** — a draft Quotation with `payment_type=Outright` + pre-filled installment fields saves with those fields cleared.
3. **Installment submit requires all four fields** — submit with `installment_deposit_amount=None` throws; likewise for each of the other three fields.
4. **Installment submit with valid fields + schedule succeeds**.
5. **Generator produces N+1 rows** — deposit=10000, months=4, start=2026-05-01, total=50000 → 5 rows (1 deposit + 4 monthly).
6. **Generator: amounts sum to grand_total exactly** — regardless of rounding, `sum(row.payment_amount) == grand_total`.
7. **Generator: last row absorbs drift** — deposit=10000, total=40001, months=3. Assert the last monthly row differs from the others by exactly 0.01.
8. **Generator: due dates step monthly from start** — start=2026-01-31, months=2. First monthly row due 2026-02-28, second 2026-03-31. Verifies `add_months` is used.
9. **Generator rejects deposit >= grand_total** — `frappe.ValidationError`.
10. **Generator rejects months < 1**.
11. **Generator is idempotent** — running twice consecutively produces identical `payment_schedule` state (no accumulation).
12. **AL integration: SO payment_schedule maps to AL installment_schedule** — given a submitted SO with 5 payment_schedule rows (1 deposit + 4 monthly), `make_allocation_letter(so.name)` returns an AL with 5 `installment_schedule` rows, labels `First, Second, Third, Fourth, Installment 5`, matching amounts and due_dates.

### Manual smoke test

- Open a draft Quotation, add items, save → `grand_total` populates.
- In Terms tab, `Payment Type` Select is required; pick `Installment`. The three installment fields appear and are mandatory.
- Fill `installment_start_date = today`, `installment_deposit_amount = 10000`, `installment_months = 4`. Grand total currently 50000.
- `Generate Installment Schedule` button appears in the toolbar. Click it.
- `payment_schedule` child table populates with 5 rows: deposit row at today for 10000, then 4 monthly rows of 10000 each. Sum = 50000.
- Hand-edit one row's amount. Save. ERPNext's built-in validation accepts it as long as sum still matches total.
- Switch `payment_type` to `Outright`. Installment fields clear. `payment_schedule` rows remain (can be deleted manually).
- Switch back to `Installment`, refill, regenerate. Rows replaced.
- Submit Quotation. Convert to Sales Order — verify `payment_schedule` is carried over identically.
- From submitted SO, `Create → Allocation Letter`. AL's `installment_schedule` is pre-filled with 5 rows, labels `First, Second, Third, Fourth, Installment 5`.

## File-change summary

**New:**

- `dantata_town/dantata_town/quotation.py` — `generate_installment_schedule` whitelisted method + `validate_quotation_payment_type` doc hook + `_validate_installment_inputs` private helper.
- `dantata_town/public/js/quotation.js` — Generate button + payment_type toggle clearing.
- `dantata_town/dantata_town/tests/test_quotation_installments.py` — 12 unit tests covering field installation, validation, generation, AL integration.

**Modified:**

- `dantata_town/dantata_town/setup.py` — add 4 installment custom fields + 2 layout breaks to `_create_custom_fields()` under the `Quotation` key.
- `dantata_town/hooks.py` — add `Quotation` entry to `doc_events` and `doctype_js`.
- `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py` — extend `make_allocation_letter` to map `sales_order.payment_schedule` into the target AL's `installment_schedule`.
- `dantata_town/dantata_town/tests/test_allocation_letter.py` — add test for the AL integration path.

## Out of scope / future work

- Non-monthly cadences (quarterly, 90-day, biweekly). Add an `installment_interval` field if needed.
- Non-equal monthly splits (20/30/30/20 etc.). Users hand-edit rows for now.
- Auto-regeneration of `payment_schedule` when `grand_total` changes. Currently manual — protects hand-edits at the cost of a reminder when totals change.
- Extending the monthly customer payment report to use these new fields — that report is its own Phase 2 sub-project.
