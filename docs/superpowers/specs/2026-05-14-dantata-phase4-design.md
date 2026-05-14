# Dantata Town Phase 4 — Design

**Date:** 2026-05-14
**Author:** Mmanuel Miles
**Client lead:** Gbenga Abraham

## Goal

Tighten the Project → Sales Order → Payment → BOQ chain so Dantata Town
Developers can track per-site inventory, payment progress per tranche, and
overall project completion without manual spreadsheets. Increase BOQ
granularity (7 → 15 stages) and add a controlled "unlock for edits" workflow
so submitted BOQs can be revised without losing audit trail.

Customer History (still pending from Phase 2) is **deferred** — shipped as
its own focused effort once this lands.

## Scope summary

| # | Feature | Surface |
|---|---|---|
| A | Project ↔ Sales Order (one SO per Project, fetch Customer, drop unique-name) | Sales Order validate hook + property setter |
| B | Per-site Items (auto-created from Site.project_units) | Site doctype hook + new fields on Project Unit Item |
| C | Reserved-quantity enforcement (block over-sale on SO submit) | Sales Order validate hook |
| D | Payment Schedule `paid_amount` + `outstanding` visible & auto-allocated FIFO | Property setter + Payment Entry/Journal Entry hooks |
| E | BOQ stages 7 → 15 | Doctype JSON + setup.py loop + boq_progress.STAGE_TABLES |
| F | BOQ Workflow with `Unlocked` state | Workflow fixture + role + idempotent backfill |
| G | Project overall completion % | Custom field on Project + boq_progress hook |

---

## A. Project ↔ Sales Order

**Flow:** Project is created first (existing flow, no change). Sales Order is
created next; user picks Project via ERPNext's standard `Sales Order.project`
field. Customer auto-fetches from Project. A second SO for the same Project is
hard-blocked.

### Schema

No new fields. Use the standard `Sales Order.project` field.

- Property setter: drop the "unique" constraint on `Project.project_name`.
  Investigate whether it comes from `autoname` or a property setter; remove it
  so multiple sites can have similarly-named projects (e.g., "Block A" on two
  different estates).

### Server logic (`dantata_town/dantata_town/sales_order.py`)

- `fetch_from_project(doc, method)` — on `before_save`:
  - If `doc.project` and not `doc.customer`, set `doc.customer =
    Project.customer`.
- `enforce_one_so_per_project(doc, method)` — on `validate`:
  - If `doc.project` is set, query for any other SO with
    `project = doc.project AND name != doc.name AND docstatus != 2`. If found,
    `frappe.throw("Project {0} is already linked to Sales Order {1}")`.

### Hooks

```python
doc_events = {
    "Sales Order": {
        "before_save": "dantata_town.dantata_town.sales_order.fetch_from_project",
        "validate": "dantata_town.dantata_town.sales_order.enforce_one_so_per_project",
    },
}
```

### UX

`public/js/sales_order.js` keeps its existing Allocation Letter button. Add
an on-`project`-change handler that calls a whitelisted server method to
confirm no existing SO already uses this project; surface the conflict inline
as a red message.

### Tests

- New SO with Project A and no Customer → Customer fetched from Project A on save.
- Two SOs with Project A (second one) → validation error names the first SO.
- Cancelled SO (docstatus=2) on Project A doesn't block a new SO.

---

## B. Per-site Items (auto-created)

**Reason:** Reservation tracking is per-site. To enforce it via standard SO
line items, each (Site × BuildingType) needs a unique Item record.

### Schema (`Project Unit Item`, child of Site)

| Field | Type | Behavior |
|---|---|---|
| `template_item` | Link → Item, mandatory | The *generic* Item the user picks (e.g. "One to Three Apartments") |
| `building_type` | Link → Item, read-only, auto-populated | The *per-site* Item (e.g. "Dantata City - One to Three Apartments") |
| `unit` | Float (existing, relabel "Total Units") | Total units of this building type on this site |
| `reserved_unit` | Float, default 0 (new) | Held back from normal sale |
| `uom` | Link → UOM (existing) | |
| `rate` | Currency (existing) | |
| `amount` | Currency (existing) | |

### Auto-creation (`dantata_town/dantata_town/doctype/site/site.py`)

`validate` hook on Site, for each `project_units` row:

1. Compose target name: `f"{site.site_name} - {template_item.item_name}"`.
2. If an Item with that exact `name` exists, set
   `row.building_type = <existing.name>` and continue.
3. Otherwise, clone the template via `frappe.copy_doc(template_item)`,
   override `item_code = item_name = target_name`, save, and set
   `row.building_type = <new.name>`.

### Lifecycle protection

- `before_rename` on Site: block the rename (`frappe.throw` — keeps Item
  names stable).
- `on_trash` on Site: block delete if any of its per-site Items appear on
  submitted SOs.
- Row deletion from `project_units`: leave the per-site Item in place
  (don't auto-delete; might already be referenced by a submitted SO).

### Tests

- Add a row to Site.project_units with template_item "One to Three Apartments";
  on save, `building_type` is set and the new Item exists.
- Re-save the Site → no duplicate Item created.
- Block rename Site.
- Block delete Site that has Items on submitted SOs.

---

## C. Reservation enforcement on Sales Order

**Reason:** Sellable cap per (Site × Item) = `total - reserved`. Reserved is
held-back inventory (premium sales only); over-sale is blocked at SO submit.

### Server logic (`dantata_town/dantata_town/sales_order.py:check_reservations`)

Runs on SO `validate`. For each `doc.items` row:

1. Find which Site row has `building_type = row.item_code`:
   ```sql
   SELECT parent AS site, unit AS total, reserved_unit AS reserved
   FROM `tabProject Unit Item`
   WHERE parenttype = 'Site' AND building_type = %s
   ```
2. If no row matches → skip (Item isn't site-tracked; regular stock item).
3. Cap = `total - reserved`.
4. Sum approved (`docstatus = 1`) SO line qty for this Item across all SOs
   *except* this one. Add this SO's qty for the same Item. If sum > cap →
   `frappe.throw` with: *"Cannot sell {qty} of {item}: only {available} of
   {total} units remain available on {site} (reserved: {reserved})."*

Fires on save (validate), so the user is blocked before submit.

### Where it applies

- Sales Order: yes.
- Quotation: no (proposals don't decrement availability).
- Sales Invoice: no (SO already enforced).

### Tests

- Total=10, reserved=3 → 7 sellable. SO for qty=7 succeeds; qty=8 blocked.
- Two SOs for the same Item: first with qty=5 submits; second with qty=3
  succeeds (5+3=8 > 7? blocked); second with qty=2 succeeds.
- Item not in any Site.project_units → no reservation check, SO submits freely.

---

## D. Payment Schedule paid_amount + outstanding (FIFO)

### Visibility (one shot)

Property setters on the shared `Payment Schedule` child doctype:

- `paid_amount` → `in_list_view = 1`
- `outstanding` → `in_list_view = 1`

Surfaces them in every parent that uses Payment Schedule: Sales Order, Sales
Invoice, Quotation, Purchase Order, Purchase Invoice.

### Auto-update for Sales Order (new module `dantata_town/dantata_town/payment_allocation.py`)

```python
def allocate_so_payments(sales_order: str) -> None:
    """FIFO-allocate received payments across the SO's payment_schedule rows."""
    so = frappe.get_doc("Sales Order", sales_order)
    rows = sorted(so.payment_schedule or [], key=lambda r: (r.due_date, r.idx))
    if not rows:
        return

    received = _sum_pe_to_so(sales_order) + _sum_je_to_project_receivable(so.project)
    remaining = received

    for row in rows:
        paid = min(remaining, flt(row.payment_amount))
        outstanding = flt(row.payment_amount) - paid
        frappe.db.set_value(
            "Payment Schedule", row.name,
            {"paid_amount": paid, "outstanding": outstanding},
            update_modified=False,
        )
        remaining -= paid
```

`_sum_pe_to_so` mirrors `project_aggregations._sum_payment_entry_references`
but filters on `per.reference_doctype = 'Sales Order' AND per.reference_name = %s`.

`_sum_je_to_project_receivable` reuses the existing
`project_aggregations._sum_journal_credits_to_receivable` (already filters JEs
by project + Receivable account).

### Hooks (`hooks.py`)

```python
doc_events = {
    "Payment Entry": {
        "on_submit": "dantata_town.dantata_town.payment_allocation.recalc_for_pe",
        "on_cancel": "dantata_town.dantata_town.payment_allocation.recalc_for_pe",
    },
    "Journal Entry": {
        "on_submit": "dantata_town.dantata_town.payment_allocation.recalc_for_je",
        "on_cancel": "dantata_town.dantata_town.payment_allocation.recalc_for_je",
    },
}
```

- `recalc_for_pe(doc)`: collect all SOs from `doc.references` → call
  `allocate_so_payments` on each. If any has an Allocation Letter, also call
  `allocate_al_installments` on the AL.
- `recalc_for_je(doc)`: collect all projects from `doc.accounts[].project`.
  For each project, find SOs → run both allocations.

### Allocation Letter `installment_schedule`

Mirror function `allocate_al_installments(allocation_letter: str)`:
- Walks `AL.installment_schedule` in date order, allocates same `received`
  number FIFO.
- AL's installment_schedule is a separate custom child doctype, so we update
  its own rows by name.

### Subtlety

`Payment Schedule.paid_amount` and `outstanding` are `allow_on_submit = 1` in
ERPNext core, so `db.set_value` against submitted parents works without doctype
changes. We bypass the parent's validate intentionally (no risk of recursive
recalc loops).

### Tests

- SO with 3 tranches (10k, 10k, 10k); PE for 15k → row 1 paid=10k, row 2 paid=5k
  (outstanding=5k), row 3 paid=0.
- Cancel the PE → all rows reset to paid=0.
- JE credit to debtors with project=SO.project, amount=20k → rows 1 and 2 fully
  paid.
- Allocation Letter with same SO: AL.installment_schedule mirrors the
  allocation.

---

## E. BOQ stages 7 → 15

### Doctype JSON (`bill_of_quantities.json`)

Add 8 more stage section blocks (8–15), each mirroring the existing pattern:

- `section_break_<random>` with `label: "Stage N"`
- `stage_N` (Data)
- `description<N>` (Table → BOQ Items)
- `stage_N_summary` (Table → BOQ Summary Item)

Existing fieldnames for stages 1–7 stay exactly as-is for backward compat
(`table_txao`, `description2..7`, `stage_N_summary`). New stages use
consistent `description8..15` naming.

### `STAGE_TABLES` map (`boq_progress.py`)

Extend the dict to include stages 8–15. No other logic changes — the existing
validate/recalc loop already iterates the dict.

### Custom fields per stage (`setup.py:_create_custom_fields`)

Extend `stage_summary_fieldnames` to include stages 8–15. The existing loop
auto-generates `stage_N_start_date`, `stage_N_end_date`, `stage_N_duration`,
`stage_N_progress`, `stage_N_status`.

Extend `_force_allow_on_submit_flags` to cover stages 8–15.

### Migration

No data migration. Existing BOQs keep their 7-stage data; new fields are
simply empty until used.

### Tests

Extend `test_boq_progress.py` with assertions that stages 8–15 also have
auto-generated fields and behave identically to 1–7.

---

## F. BOQ Workflow with Unlock state

### States

| State | doc_status | Style |
|---|---|---|
| Draft | 0 | Warning |
| Pending Approval | 0 | Primary |
| Approved | 1 | Success |
| Unlocked | 0 | Danger |
| Rejected | 0 | Danger |

### Transitions

| From | Action | To | Allowed Role |
|---|---|---|---|
| Draft | Submit for Approval | Pending Approval | (anyone with BOQ write) |
| Pending Approval | Approve | Approved | BOQ Approver |
| Pending Approval | Reject | Rejected | BOQ Approver |
| Rejected | Re-open | Draft | (anyone with BOQ write) |
| Approved | Unlock for Edit | Unlocked | BOQ Approver |
| Unlocked | Submit for Approval | Pending Approval | (anyone with BOQ write) |

### Role

`BOQ Approver` — created by `setup.py` (same pattern as existing
`Sub Contractor Approver`).

### Mechanics

- Frappe natively flips `docstatus` between 0 ↔ 1 when a workflow transition
  changes `doc_status`. The doc keeps its `name`, so downstream Material
  Requests and Sub Contractor Payment Requests stay linked.
- Re-submission from `Unlocked` → `Pending Approval` → `Approved` returns
  the doc to `docstatus = 1` with the same name.

### Idempotent backfill

For existing production BOQs already at `docstatus = 1`:
```sql
UPDATE `tabBill of Quantities` SET workflow_state = 'Approved'
WHERE docstatus = 1 AND (workflow_state IS NULL OR workflow_state = '');
```
Run inside `setup.py` after creating the workflow.

### Edge cases

- **Existing downstream documents on unlock**: Material Requests and SCPRs
  that already reference an unlocked BOQ stay linked. Editing a line item
  doesn't reconcile against them. We surface a yellow warning toast in the
  form script: *"This BOQ has existing Material Requests / Sub Contractor
  Payment Requests. They will not be revalidated against your edits."*

### Tests

- Workflow created with all 5 states and 6 transitions.
- Approve transition: docstatus 0 → 1.
- Unlock transition: docstatus 1 → 0; doc name unchanged.
- Re-submission cycle: Unlocked → Pending → Approved; same name, docstatus 1.
- Backfill: pre-existing submitted BOQ gets `workflow_state = "Approved"`.

### Admin setup task

One-time per production site:
- (Auto via setup.py) Role `BOQ Approver` created.
- (Auto via fixture) Workflow `Bill of Quantities Approval` installed.

---

## G. Project overall completion %

### Schema

New custom field on Project (in existing Financials section):

```python
{
    "fieldname": "project_completion_percent",
    "fieldtype": "Percent",
    "label": "Completion",
    "insert_after": "project_payment",
    "read_only": 1,
    "module": "Dantata Town",
}
```

ERPNext renders Percent fields as a progress bar.

### Computation (`project_aggregations.py:recalc_project_completion`)

```python
def recalc_project_completion(project: str | None) -> None:
    if not project or not frappe.db.exists("Project", project):
        return

    boqs = frappe.get_all(
        "Bill of Quantities",
        filters={"project": project, "docstatus": 1},
        pluck="name",
    )
    if not boqs:
        frappe.db.set_value("Project", project,
            "project_completion_percent", 0, update_modified=False)
        return

    boq_completions = []
    for boq_name in boqs:
        boq = frappe.get_doc("Bill of Quantities", boq_name)
        active = []
        for stage_no, table_field in STAGE_TABLES.items():
            if boq.get(table_field):
                active.append(flt(boq.get(f"stage_{stage_no}_progress")))
        if active:
            boq_completions.append(sum(active) / len(active))

    completion = (sum(boq_completions) / len(boq_completions)) if boq_completions else 0
    frappe.db.set_value("Project", project,
        "project_completion_percent", completion, update_modified=False)
```

### Trigger

Add one line at the end of `boq_progress.recalc_boq_progress`:

```python
if doc.project:
    from dantata_town.dantata_town.project_aggregations import recalc_project_completion
    recalc_project_completion(doc.project)
```

No new doc-event hook needed — BOQ validate already runs on every save
(including the auto-save triggered by toggling line-item `completed`
checkboxes).

### Tests

- BOQ with 3 active stages at 100/50/0 → `project_completion_percent = 50`.
- BOQ with 0 active stages → 0.
- Two BOQs on same project at 60% and 40% → 50.
- Stage with all `completed=1` rows recalculates progress and rolls up.

---

## Admin setup tasks (one-time per production site)

- (Auto) Role `BOQ Approver` created via `setup.py`.
- (Auto) Workflow `Bill of Quantities Approval` installed.
- (Auto) Existing submitted BOQs backfilled to `workflow_state = "Approved"`.
- (Auto) Property setters on Payment Schedule, Project.project_name uniqueness.
- (Auto) BOQ stages 8–15 custom fields created.

No manual UI configuration required.

## Test status target

All existing tests continue to pass (91 today). Phase 4 adds:
- `test_sales_order_link.py` (A): fetch + duplicate-block + cancelled-SO cases.
- `test_per_site_items.py` (B): auto-create, idempotency, rename/delete blocks.
- `test_reservation.py` (C): cap math, multi-SO sum, non-site Item bypass.
- `test_payment_allocation.py` (D): FIFO across PE + JE; AL mirror; cancel reset.
- `test_boq_progress.py` (E, G): extend for stages 8–15 + project rollup.
- `test_boq_workflow.py` (F): transitions, backfill, name persistence.

Target: ~120 tests passing post-phase.

## Key people

Gbenga Abraham (client lead), Mmanuel Miles (developer/tester).
