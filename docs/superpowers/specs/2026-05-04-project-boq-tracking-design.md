# Project & BOQ Tracking Enhancements — Design

**Date:** 2026-05-04
**Scope:** Spec 1 of 2 (Spec 2 covers the Sub Contractor Payment Request flow.)
**Status:** Draft for review

## Background

Following Phase 2 (allocation letter, quotation installments, customer payment report), the client wants Project records to surface real cost/revenue totals and the BOQ to track stage-by-stage construction progress. The Site doctype's child table also needs renames so the field labels match the construction terminology actually used in the field.

This spec covers three thematic chunks of work, all related to making Project & BOQ a more accurate reflection of on-site reality:

1. **Site renames** — `Project Unit Item.unit_type` → `building_type`, `projected_quantity` → `unit`.
2. **Project enhancements** — `building_type` selector sourced from the chosen Site, surface and relabel `total_sales_amount`, add aggregated `project_expenses` and `project_payment` fields driven by hooks on supplier/payment doctypes.
3. **BOQ stage tracking** — add `start_date`, `end_date`, auto-computed `duration`, `progress`, and `status` to each of the 7 stages, plus a `completed` checkbox on each `BOQ Items` row that drives the stage's progress.

The Sub Contractor Payment Request flow (with its own workflow, change-detection prompt, and Purchase Invoice creation) is intentionally deferred to Spec 2.

## Goals

- Site list-view headers say "Building Type" / "Unit" without breaking existing data.
- A Project record shows, at a glance: sales-order revenue (existing field, surfaced and relabeled), money-out total (new), money-in total (new) — all auto-maintained.
- A BOQ form shows, per stage: planned date range, computed duration, % complete derived from line-item checkboxes, and a "Completed" status when the stage hits 100%.
- All progress tracking is editable on submitted BOQs (construction milestones happen post-submit).
- The implementation does not duplicate ERPNext logic where ERPNext already maintains a comparable field (`total_sales_amount`).

## Non-goals

- Sub Contractor Payment Request, the BOQ-line `assignment_type` (Company / Sub Contractor) field, the Purchase Invoice creation flow, and the `expense_account` field on Site — all deferred to Spec 2.
- Refactoring BOQ's 7 hardcoded stage sections into a child table. Considered but rejected — too large a structural change for this spec; existing reports/print formats reference `stage_N` fields by name.
- Variation quantity approval workflow (noted as "may still need a formal approval doctype" in Phase 1 memory) is unchanged.

## Architecture overview

```
Site (existing)
└── Project Unit Item (child)
    ├── building_type   (renamed from unit_type)
    └── unit            (renamed from projected_quantity)

Project (ERPNext, custom-fielded)
├── building_type       (Link → Item, set_query filtered by site.project_units.building_type)
├── total_sales_amount  (existing — surfaced via property setter, relabeled "Sales Order Amount")
├── project_expenses    (new, Currency, read-only) ← maintained by hooks
└── project_payment     (new, Currency, read-only) ← maintained by hooks

Hooks → project_aggregations.recalc_for_doc → recalc_project_totals(project)
  ├── on Purchase Invoice submit/cancel
  ├── on Expense Claim submit/cancel
  ├── on Journal Entry submit/cancel
  └── on Payment Entry submit/cancel

Bill of Quantities (existing, submittable)
├── stage_N_start_date     (× 7, allow_on_submit)
├── stage_N_end_date       (× 7, allow_on_submit)
├── stage_N_duration       (× 7, read-only, auto)
├── stage_N_progress       (× 7, read-only, auto)
└── stage_N_status         (× 7, read-only, auto = "Completed" | "")

BOQ Items (child, used by all 7 stages)
└── completed              (Check, allow_on_submit, in_list_view)

Hooks → boq_progress
  ├── validate_stage_dates  (mandatory dates per non-empty stage; end ≥ start)
  └── recalc_boq_progress   (count-based progress, duration, status)
```

## Section 1 — Site renames

### Doctype JSON

In `dantata_town/dantata_town/doctype/project_unit_item/project_unit_item.json`:

- `unit_type` → `building_type` (Link → Item, label "Building Type", `in_list_view`)
- `projected_quantity` → `unit` (Float, label "Unit", `in_list_view`)
- `field_order` updated accordingly.

The parent table label on `Site` ("Project Units") is **not** changed.

### Migration

A patch handles the in-place SQL rename so production data isn't lost. JSON-only changes would create new empty columns alongside the old ones.

`dantata_town/patches/rename_project_unit_item_fields.py`:

```python
import frappe
from frappe.model.rename_field import rename_field

def execute():
    cols = frappe.db.get_table_columns("Project Unit Item")
    if "unit_type" in cols:
        rename_field("Project Unit Item", "unit_type", "building_type")
    if "projected_quantity" in cols:
        rename_field("Project Unit Item", "projected_quantity", "unit")
```

Registered in `dantata_town/patches.txt` as `dantata_town.patches.rename_project_unit_item_fields`. Idempotent — guarded by column-existence checks.

## Section 2 — Project enhancements

### Custom fields (registered in `setup.py`)

| Fieldname | Type | Insert after | Notes |
|-----------|------|--------------|-------|
| `building_type` | Link → Item | `site` | `depends_on: eval:doc.site`; client-side `set_query` filters Item to those present in the chosen Site's `project_units.building_type` |
| `dt_financials_section` | Section Break | `project_subtype` | label "Financials" |
| `project_expenses` | Currency | `dt_financials_section` | read-only |
| `dt_financials_col` | Column Break | `project_expenses` | |
| `project_payment` | Currency | `dt_financials_col` | read-only |

### Property setters (`_create_property_setters` in `setup.py`)

- `Project.total_sales_amount.hidden = 0` (Check) — surface the existing field.
- `Project.total_sales_amount.label = "Sales Order Amount"` (Data) — relabel.

### `project_name` behavior

No code change. The field is already free-text Data with no `fetch_from`; today's `dantata_town/public/js/project.js` does not auto-set it. Customer link is already mandatory via property setter from Phase 2. The user types the project name freely; customer is a separate required link.

### `building_type` set_query

Added to `dantata_town/public/js/project.js`:

```js
frappe.ui.form.on("Project", {
    site(frm) {
        frm.set_value("building_type", null);
    },
    setup(frm) {
        frm.set_query("building_type", () => {
            if (!frm.doc.site) {
                return { filters: { name: ["in", []] } };
            }
            return {
                query: "dantata_town.dantata_town.project_aggregations.get_site_building_types",
                filters: { site: frm.doc.site },
            };
        });
    },
});
```

The whitelisted server method `get_site_building_types(doctype, txt, searchfield, start, page_len, filters)` returns Items present in `Project Unit Item` rows where `parent = filters.site`, matching the standard Frappe search-query signature.

### Aggregation module (`dantata_town/dantata_town/project_aggregations.py`)

```python
import frappe

def recalc_project_totals(project: str) -> None:
    if not project:
        return
    expenses = (
        _sum_purchase_invoice_items(project)
        + _sum_expense_claims(project)
        + _sum_journal_debits(project)
    )
    payment = (
        _sum_payment_entry_references(project)
        + _sum_journal_credits_to_receivable(project)
    )
    frappe.db.set_value(
        "Project", project,
        {"project_expenses": expenses, "project_payment": payment},
        update_modified=False,
    )

def recalc_for_doc(doc, method=None):
    """Hook entrypoint. Extracts project links from `doc` and recalculates each."""
    for project in _projects_touched_by(doc):
        recalc_project_totals(project)
```

Each `_sum_*` is one query filtered by `docstatus = 1` and the project link. Layout:

| Doctype | Where the project lives | Sign |
|---------|------------------------|------|
| Purchase Invoice | items table `project` field | sum of `amount` |
| Expense Claim | parent `project` field | sum of `total_sanctioned_amount` |
| Journal Entry | accounts table `project` field, `debit_in_account_currency > 0` | sum of debits |
| Payment Entry | references table when reference doctype is Sales Invoice on this project, OR direct `project` link | sum of allocated amount |
| Journal Entry (credit) | accounts table where `credit_in_account_currency > 0` AND account.account_type = "Receivable" | sum of credits |

`_projects_touched_by(doc)` returns a deduped set of project names from whatever location the doc carries them — different shape per doctype.

### Hook wiring (`hooks.py`)

```python
doc_events = {
    # ... existing entries unchanged ...
    "Purchase Invoice": {
        "on_submit": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
        "on_cancel": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
    },
    "Expense Claim": {
        "on_submit": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
        "on_cancel": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
    },
    "Journal Entry": {
        "on_submit": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
        "on_cancel": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
    },
    "Payment Entry": {
        "on_submit": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
        "on_cancel": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
    },
}
```

### Why hooks (not live recompute)

- Same pattern as the existing BOQ consumed-qty hooks in `utils.py`.
- Project list views and reports read `project_expenses` / `project_payment` directly from the table — no per-row aggregation latency.
- Cancellation reverses the contribution naturally because we re-sum from `docstatus = 1` only — no delta math, no drift.

## Section 3 — BOQ stage tracking

### Custom field on `BOQ Items` child

Registered in `setup.py`:

| Fieldname | Type | Notes |
|-----------|------|-------|
| `completed` | Check | `in_list_view`, `allow_on_submit: 1`, `insert_after: actual_amount` |

### Per-stage parent fields (× 7)

Generated by a loop in `setup.py`. For each stage `N` in 1..7, append after `stage_N_summary`:

| Fieldname | Type | Notes |
|-----------|------|-------|
| `stage_{N}_start_date` | Date | `allow_on_submit: 1` |
| `stage_{N}_end_date` | Date | `allow_on_submit: 1` |
| `stage_{N}_duration` | Int | read-only, label "Duration (days)" |
| `stage_{N}_progress` | Percent | read-only |
| `stage_{N}_status` | Data | read-only, set by validate |

### Compute module (`dantata_town/dantata_town/boq_progress.py`)

```python
import frappe
from frappe import _

STAGE_TABLES = {
    1: "table_txao",
    2: "description2",
    3: "description3",
    4: "description4",
    5: "description5",
    6: "description6",
    7: "description7",
}

def validate_stage_dates(doc, method=None):
    for stage_no, table_field in STAGE_TABLES.items():
        rows = doc.get(table_field) or []
        if not rows:
            continue
        start = doc.get(f"stage_{stage_no}_start_date")
        end = doc.get(f"stage_{stage_no}_end_date")
        if not start or not end:
            frappe.throw(_(
                "Stage {0} has line items — start and end dates are required."
            ).format(stage_no))
        if end < start:
            frappe.throw(_(
                "Stage {0} end date cannot be before start date."
            ).format(stage_no))

def recalc_boq_progress(doc, method=None):
    for stage_no, table_field in STAGE_TABLES.items():
        rows = doc.get(table_field) or []
        total = len(rows)
        done = sum(1 for r in rows if r.completed)
        progress = (100 * done / total) if total else 0
        doc.set(f"stage_{stage_no}_progress", progress)
        doc.set(f"stage_{stage_no}_status",
                "Completed" if total and progress == 100 else "")
        start = doc.get(f"stage_{stage_no}_start_date")
        end = doc.get(f"stage_{stage_no}_end_date")
        doc.set(f"stage_{stage_no}_duration",
                (end - start).days if start and end else 0)
```

### Hook wiring (`hooks.py`)

```python
doc_events = {
    # ... existing ...
    "Bill of Quantities": {
        "validate": [
            "dantata_town.dantata_town.boq_progress.validate_stage_dates",
            "dantata_town.dantata_town.boq_progress.recalc_boq_progress",
        ],
    },
}

doctype_js = {
    # ... existing ...
    "Bill of Quantities": "public/js/bill_of_quantities.js",
}
```

### Form script (`dantata_town/public/js/bill_of_quantities.js`)

New file. On `BOQ Items` child `completed` toggle and on stage `start_date`/`end_date` change, recompute the affected stage's `progress` / `duration` / `status` client-side and refresh the field. Server-side `validate` is the source of truth on save.

The form script needs a `parentfield` → stage_no map (mirror of `STAGE_TABLES`) so a row event can identify its stage.

### Editable post-submit

`allow_on_submit: 1` on:
- All 7 × `stage_N_start_date` and `stage_N_end_date`
- `BOQ Items.completed`

Computed fields (`duration`, `progress`, `status`) stay read-only and refresh because Frappe runs `validate` on the auto-save that fires when an `allow_on_submit` field changes.

## Section 4 — Code organization & migration

### Files added

```
dantata_town/dantata_town/project_aggregations.py
dantata_town/dantata_town/boq_progress.py
dantata_town/patches/__init__.py                          # if missing
dantata_town/patches/rename_project_unit_item_fields.py
dantata_town/public/js/bill_of_quantities.js
dantata_town/dantata_town/tests/test_project_aggregations.py
dantata_town/dantata_town/tests/test_boq_progress.py
dantata_town/dantata_town/tests/test_rename_project_unit_item_fields.py
```

### Files edited

```
dantata_town/dantata_town/setup.py                                            # extend create_boq_custom_fields
dantata_town/dantata_town/doctype/project_unit_item/project_unit_item.json    # field renames
dantata_town/hooks.py                                                          # +doc_events + doctype_js entry
dantata_town/public/js/project.js                                              # building_type set_query + clear-on-site-change
dantata_town/patches.txt                                                       # register patch
```

### `setup.py` extension shape

`create_boq_custom_fields()` already runs on `after_install` and `after_migrate`. It will be extended to also:

- Register `building_type`, `dt_financials_section`, `project_expenses`, `dt_financials_col`, `project_payment` on Project.
- Register `completed` on BOQ Items.
- Loop over 1..7 to register the 5 per-stage fields on Bill of Quantities.
- Add property setters `Project.total_sales_amount.hidden = 0` and `Project.total_sales_amount.label = "Sales Order Amount"`.

Function name kept (`create_boq_custom_fields`) to avoid touching `hooks.py` install/migrate wiring; consider a more generic name in a follow-up.

## Section 5 — Testing

### Automated tests

Use `frappe.tests.utils.FrappeTestCase` + transactional rollback (matches `test_site.py`).

**`test_project_aggregations.py`:**
- Submit a Purchase Invoice with `project = X` → `project_expenses` increases by row amount.
- Cancel the PI → `project_expenses` returns to prior value.
- Submit an Expense Claim on Project X → contributes to `project_expenses`.
- Journal Entry: debit on Project X → `project_expenses`; credit to a Receivable account on Project X → `project_payment`.
- Submit a Payment Entry against a Sales Invoice on Project X → `project_payment` increases.
- Doc with no project link → no-op, no errors.
- Doc touching two projects → both update.

**`test_boq_progress.py`:**
- Empty stage (no items) — no validation error, progress stays 0, status blank.
- Stage with items but no start/end date → `validate` raises.
- `end_date < start_date` → `validate` raises.
- 4 line items, 1 checked → progress = 25, status blank.
- All 4 checked → progress = 100, status = "Completed".
- 10-day stage → duration = 10.
- Toggle `completed` on a submitted BOQ row, save → parent progress recomputes.

**`test_rename_project_unit_item_fields.py`:**
- Insert a Site with old fieldnames in DB, run patch → values appear under new fieldnames.
- Run patch twice → no error, no data loss.

### Manual verification checklist

- `bench migrate` on a copy of production: confirm Project Unit Item rows still carry their values under `building_type` / `unit`; list view shows new headers.
- Open a Project, confirm `total_sales_amount` shows with new label "Sales Order Amount" and `project_expenses` / `project_payment` populate after submitting a PI / PE on that project.
- Open a Project, change Site → `building_type` clears and re-filters.
- Open an existing submitted BOQ, toggle a line-item checkbox, save → parent progress updates without re-submitting.

## Risks & mitigations

- **`rename_field` on a child table with existing data:** the patch is column-existence-guarded, but if a site has been on the new fieldnames already (manually patched), the patch is a no-op. Verified by idempotency test.
- **`bench migrate` ordering:** the patch runs before `after_migrate` (which re-runs `create_boq_custom_fields`), so by the time setup re-asserts the JSON, the SQL columns are already on the new names.
- **Hook-driven aggregation correctness under concurrency:** two simultaneous PI submits on the same project both `recalc_project_totals` from the same `docstatus = 1` snapshot — final write reflects whoever ran second; no drift since both queries see the committed rows. Acceptable for this scale.
- **BOQ form script and `allow_on_submit` interaction:** Frappe auto-saves when an `allow_on_submit` field changes; `validate` re-runs and recomputes derived fields. The client-side recompute is purely UX (no save round-trip) — server is authoritative.

## Open follow-ups (out of scope here)

- Spec 2 will add `assignment_type` (Company / Sub Contractor) on `BOQ Items`, the `Sub Contractor Payment Request` doctype, the change-detection prompt, and the Purchase Invoice creation path. It will also add `expense_account` to Site (used only by that flow).
- Renaming `create_boq_custom_fields` to a more generic name once it carries non-BOQ fields too.
- Optional follow-up: amount-weighted progress alternative if count-based proves too coarse.
