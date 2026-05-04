# Sub Contractor Flow — Design

**Date:** 2026-05-04
**Scope:** Spec 2 of 2 (Spec 1 covered Project & BOQ tracking enhancements.)
**Status:** Draft for review

## Background

Spec 1 added the project-side aggregations and BOQ stage tracking. Spec 2 introduces the sub-contractor payment workflow that closes the loop between the BOQ (which lines are sub-contracted), the procurement record (a payment request the chairman approves), and the accounting hit (a Purchase Invoice posted against the Site's expense account).

The flow:

1. **BOQ classifies each line** as `Company` (default) or `Sub Contractor` via a new `assignment_type` Select on `BOQ Items`.
2. **The user generates a Sub Contractor Payment Request** by clicking a button on a submitted BOQ. A modal lets them pick the supplier, the date, and which sub-contractor lines to include (multiple suppliers per BOQ → multiple requests).
3. **The request is submittable** with a 4-state admin-created workflow (Draft → Pending Approval → Approved → Paid + Rejected). At the moment of submission, the user is shown a diff modal listing any qty/rate changes from the original BOQ values, and asked to Proceed or Cancel.
4. **Once Approved**, a "Create Purchase Invoice" button on the request creates a draft PI (1 line: "Sub Contractor Cost", qty=1, rate=total_amount), with the expense_account looked up from the Site and the project set on the line. Site is added as a custom field on the PI parent.

The Spec 1 aggregation hooks (`recalc_for_doc` on PI submit/cancel) automatically pick up the PI's contribution to `project_expenses` once the user submits the PI.

## Goals

- A submitted BOQ with sub-contractor lines can be turned into one or more payment requests via a single button + modal.
- Approvers see exactly what changed on a request relative to the original BOQ at the moment of approval (submit).
- An Approved request can be turned into a draft Purchase Invoice with one click; the PI's `expense_account` resolves automatically from the Site.
- Workflow is admin-managed (UI-driven), per the Allocation Letter precedent.

## Non-goals

- Auto-creating the "Sub Contractor Cost" Item — admin pre-creates it (clear error if absent).
- Auto-submitting the PI — submission has accounting consequences; user reviews and submits manually.
- Auto-transitioning the request to `Paid` after PI creation — kept manual; admin advances workflow after Payment Entry settles.
- Per-line supplier on `BOQ Items` — supplier is captured at request creation, not on the BOQ.
- Shipping a hardcoded workflow JSON — admin creates via UI.

## Architecture overview

```
Site (custom-owned)
└── expense_account  (new, Link → Account)

BOQ Items (custom child)
├── completed         (existing, Spec 1)
└── assignment_type   (new, Select Company|Sub Contractor)

Bill of Quantities (existing, submittable)
└── refresh handler in bill_of_quantities.js
    └── "Create Sub Contractor Payment Request" button
        └── modal picker (Supplier, Date, checkbox grid by stage)
            └── on Create →
                dantata_town.dantata_town.sub_contractor.make_request_from_boq

Sub Contractor Payment Request (new, submittable, custom-owned)
├── parent fields: naming_series, date, site, project, boq, supplier, items, total_amount, amended_from
├── Sub Contractor Payment Request Item (child)
│   └── stage_label, description, unit, quantity, rate, amount,
│       original_quantity, original_rate, boq_item
├── controller: validate → recompute amounts and total
└── form script:
    ├── before_submit → diff modal (Proceed/Cancel)
    └── refresh → "Create Purchase Invoice" button (gated on docstatus=1 AND workflow_state=Approved)
        └── on click → dantata_town.dantata_town.sub_contractor.make_purchase_invoice

Purchase Invoice (ERPNext, custom-fielded)
├── site                            (new, Link → Site, on parent)
└── sub_contractor_payment_request  (new, Link → Sub Contractor Payment Request, on parent)
```

## Section 1 — Site & BOQ field additions

### Site (`dantata_town/dantata_town/doctype/site/site.json`)

Add directly to JSON (Site is custom-owned):

| Fieldname | Type | Notes |
|-----------|------|-------|
| `expense_account` | Link → Account | inserted in `column_break_lflt` after `expected_end_date`. Used by the PI creation flow. |

### BOQ Items (registered via `setup.py`)

| Fieldname | Type | Notes |
|-----------|------|-------|
| `assignment_type` | Select | options `Company\nSub Contractor`, default `Company`, `allow_on_submit: 1`, `in_list_view: 1`, `insert_after: completed` |

Default `Company` matches the user's intent that most lines are company-handled and only the few sub-contracted ones get explicitly flagged.

### Why `allow_on_submit`

Operators may need to retroactively reclassify a line if work changes hands. Same precedent as the Spec 1 `completed` checkbox.

## Section 2 — Sub Contractor Payment Request doctype

### Parent (`dantata_town/dantata_town/doctype/sub_contractor_payment_request/sub_contractor_payment_request.json`)

| Fieldname | Type | Notes |
|-----------|------|-------|
| `naming_series` | Select | `SCPR-.YYYY.-.#####`, `set_only_once: 1` |
| `date` | Date | reqd, default = today |
| `site` | Link → Site | reqd, read-only after generation |
| `project` | Link → Project | reqd, read-only after generation |
| `boq` | Link → Bill of Quantities | reqd, read-only; filtered to `docstatus = 1` |
| `supplier` | Link → Supplier | reqd, read-only after generation |
| `items` | Table → Sub Contractor Payment Request Item | line items |
| `total_amount` | Currency | read-only, auto-summed in `validate` |
| `amended_from` | Link self | for amend/cancel |

`is_submittable: 1`, `track_changes: 1`, `autoname` from naming_series.

**Permissions**: System Manager full; `Sub Contractor Approver` (read/submit/cancel); `Accounts Manager` (read, transition to Paid).

**Connections dashboard**: `links` array entry pointing to `Purchase Invoice` via `sub_contractor_payment_request` field, so a request shows its derived PI.

### Child (`dantata_town/dantata_town/doctype/sub_contractor_payment_request_item/sub_contractor_payment_request_item.json`)

| Fieldname | Type | Notes |
|-----------|------|-------|
| `stage_label` | Data | read-only, e.g. "Stage 2 — Carcass" |
| `description` | Link → BOQ Item Detail | reqd |
| `unit` | Data | `fetch_from: description.unit`, read-only |
| `quantity` | Float | reqd, editable in draft |
| `rate` | Currency | reqd, editable in draft |
| `amount` | Currency | read-only, auto |
| `original_quantity` | Float | hidden, snapshot at creation |
| `original_rate` | Currency | hidden, snapshot at creation |
| `boq_item` | Data | hidden, ref to source BOQ Items row's `name` |

`istable: 1`.

### Why snapshots, not lookups, for the diff

If the BOQ row is amended after the request is generated, a lookup-based diff would silently disappear. Snapshots make the diff stable.

## Section 3 — BOQ modal picker → request creation

### Form-script extension (`dantata_town/public/js/bill_of_quantities.js`)

Adds a `refresh` handler branch:

```js
if (!frm.is_new() && frm.doc.docstatus === 1) {
    frm.add_custom_button(__("Create Sub Contractor Payment Request"), () =>
        open_sub_contractor_modal(frm)
    );
}
```

`open_sub_contractor_modal(frm)`:

1. Scans `frm.doc[stage_table_field]` for all 7 stages, collecting rows where `assignment_type === "Sub Contractor"`. Each is tagged with its stage label (`Stage N — <stage_N data field>`).
2. If no rows match → `frappe.msgprint("No sub-contractor lines on this BOQ")` and return.
3. Otherwise opens a `frappe.ui.Dialog` with:
   - **Supplier** Link field (reqd).
   - **Date** Date field (default today).
   - HTML section with a checkbox grid grouped by stage. Columns: `[ ] Stage | Description | Unit | Qty | Rate | Amount`. All checked by default.
   - **Create** primary button.
4. On Create: validate at least one row checked; call:
   ```js
   frappe.call({
       method: "dantata_town.dantata_town.sub_contractor.make_request_from_boq",
       args: { boq: frm.doc.name, supplier, date, selected: JSON.stringify(selected_rows) },
   })
   ```
5. On success → `frappe.set_route("Form", "Sub Contractor Payment Request", r.message)`.

### Server method (`dantata_town/dantata_town/sub_contractor.py`)

```python
@frappe.whitelist()
def make_request_from_boq(boq: str, supplier: str, date: str, selected: str) -> str:
    """Create a draft Sub Contractor Payment Request from selected BOQ rows.

    `selected` is a JSON-serialized list of dicts:
      [{"stage_label", "boq_item_name", "description", "unit", "quantity", "rate"}]
    """
    if not frappe.db.exists("Bill of Quantities", boq):
        frappe.throw(_("BOQ {0} does not exist").format(boq))
    if frappe.db.get_value("Bill of Quantities", boq, "docstatus") != 1:
        frappe.throw(_("BOQ {0} must be submitted before generating a payment request").format(boq))

    rows = frappe.parse_json(selected)
    if not rows:
        frappe.throw(_("Select at least one line"))

    site, project = frappe.db.get_value(
        "Bill of Quantities", boq, ["site", "project"]
    )

    req = frappe.new_doc("Sub Contractor Payment Request")
    req.date = date
    req.site = site
    req.project = project
    req.boq = boq
    req.supplier = supplier
    for r in rows:
        req.append("items", {
            "stage_label": r["stage_label"],
            "description": r["description"],
            "unit": r.get("unit"),
            "quantity": r["quantity"],
            "rate": r["rate"],
            "original_quantity": r["quantity"],
            "original_rate": r["rate"],
            "boq_item": r.get("boq_item_name"),
        })
    req.insert(ignore_permissions=False)
    return req.name
```

## Section 4 — At-submit diff prompt

### Form script (`dantata_town/public/js/sub_contractor_payment_request.js`)

```js
frappe.ui.form.on("Sub Contractor Payment Request", {
    before_submit(frm) {
        const diffs = collect_row_diffs(frm.doc);
        if (diffs.length === 0) return;  // no diffs, allow submit

        return new Promise((resolve, reject) => {
            const dialog = new frappe.ui.Dialog({
                title: __("Confirm changes before submitting"),
                fields: [{ fieldtype: "HTML", fieldname: "diff_html" }],
                primary_action_label: __("Proceed"),
                primary_action: () => { dialog.hide(); resolve(); },
                secondary_action_label: __("Cancel"),
                secondary_action: () => { dialog.hide(); reject(); },
            });
            dialog.fields_dict.diff_html.$wrapper.html(render_diff_html(diffs));
            dialog.on_hide = () => reject();
            dialog.show();
        });
    },
});
```

Returning a rejected Promise from `before_submit` cancels the submit. The doc stays in its current draft state with edits preserved.

### Helpers (same file)

`collect_row_diffs(doc)` returns an array of:

```js
{
    stage_label: "Stage 2 — Carcass",
    description: "Concrete cast in-situ",
    qty_changed: { from: 10, to: 8 } | null,
    rate_changed: { from: 1000, to: 1200 } | null
}
```

Comparison uses `flt()` semantics (treat null/undefined as 0).

`render_diff_html(diffs)` renders a Bootstrap-style table.

### Live recompute (UX)

Client-side handlers on `Sub Contractor Payment Request Item` events `quantity` and `rate` recompute the row's `amount` (qty × rate) and the parent's `total_amount`. Same pattern as the BOQ stage live recompute. Server-side `validate` is the source of truth on save.

## Section 5 — Purchase Invoice creation

### Custom fields on PI (registered in `setup.py`)

| Fieldname | Type | Notes |
|-----------|------|-------|
| `site` | Link → Site | new, on PI parent, `insert_after: company` |
| `sub_contractor_payment_request` | Link → Sub Contractor Payment Request | new, on PI parent, read-only, `insert_after: site` |

### Button visibility

In `sub_contractor_payment_request.js` `refresh`:

```js
if (
    frm.doc.docstatus === 1 &&
    frm.doc.workflow_state === "Approved"
) {
    frm.add_custom_button(__("Create Purchase Invoice"), () => create_pi(frm));
}
```

### Server method (`dantata_town/dantata_town/sub_contractor.py`)

```python
@frappe.whitelist()
def make_purchase_invoice(request_name: str) -> str:
    req = frappe.get_doc("Sub Contractor Payment Request", request_name)

    if req.docstatus != 1:
        frappe.throw(_("Request must be submitted to create a Purchase Invoice"))
    if req.workflow_state != "Approved":
        frappe.throw(_("Request must be in Approved state to create a Purchase Invoice"))

    expense_account = frappe.db.get_value("Site", req.site, "expense_account")
    if not expense_account:
        frappe.throw(_("Set Expense Account on Site '{0}' before creating a Purchase Invoice").format(req.site))

    if not frappe.db.exists("Item", "Sub Contractor Cost"):
        frappe.throw(_("Create an Item named 'Sub Contractor Cost' before using this feature"))

    pi = frappe.new_doc("Purchase Invoice")
    pi.supplier = req.supplier
    pi.posting_date = today()
    pi.due_date = add_days(today(), 30)
    pi.site = req.site
    pi.sub_contractor_payment_request = req.name
    pi.append("items", {
        "item_code": "Sub Contractor Cost",
        "qty": 1,
        "rate": req.total_amount,
        "project": req.project,
        "expense_account": expense_account,
    })
    pi.set_missing_values()
    pi.insert(ignore_permissions=False)
    return pi.name
```

The user is routed to the new draft PI; they review and submit manually. We do not auto-submit (avoids unintended GL entries).

## Section 6 — Workflow + admin setup (no code)

The Workflow is **created entirely via the Frappe UI** (no JSON shipped). The deployment runbook lists the states/transitions/roles for the admin to set up.

### States

| State | Doc Status | Style | Allow Edit (roles) |
|-------|-----------|-------|---------------------|
| Draft | 0 | Primary | System Manager, Sub Contractor Approver |
| Pending Approval | 0 | Warning | System Manager, Sub Contractor Approver |
| Approved | 1 | Success | (none — submitted, no edits) |
| Rejected | 1 | Danger | (none — terminal) |
| Paid | 1 | Success | (none — terminal) |

### Transitions

| From | Action | To | Allowed Role |
|------|--------|------|--------------|
| Draft | Submit for Approval | Pending Approval | System Manager, Sub Contractor Approver |
| Pending Approval | Approve | Approved | Sub Contractor Approver |
| Pending Approval | Reject | Rejected | Sub Contractor Approver |
| Approved | Mark Paid | Paid | Accounts Manager |

### Roles

- `Sub Contractor Approver` — admin creates via UI; assign to Project Manager / Chairman office user(s).
- `Accounts Manager` — already exists in ERPNext.

### Why workflow is admin-managed

Identical reasoning to Allocation Letter (Phase 2): workflows are sensitive to client policy; the UI-driven approach lets the admin tailor it without code changes.

## Section 7 — Code organization & migration

### New files

```
dantata_town/dantata_town/sub_contractor.py
dantata_town/dantata_town/doctype/sub_contractor_payment_request/__init__.py
dantata_town/dantata_town/doctype/sub_contractor_payment_request/sub_contractor_payment_request.json
dantata_town/dantata_town/doctype/sub_contractor_payment_request/sub_contractor_payment_request.py
dantata_town/dantata_town/doctype/sub_contractor_payment_request/sub_contractor_payment_request.js
dantata_town/dantata_town/doctype/sub_contractor_payment_request/test_sub_contractor_payment_request.py
dantata_town/dantata_town/doctype/sub_contractor_payment_request_item/__init__.py
dantata_town/dantata_town/doctype/sub_contractor_payment_request_item/sub_contractor_payment_request_item.json
dantata_town/dantata_town/doctype/sub_contractor_payment_request_item/sub_contractor_payment_request_item.py
dantata_town/dantata_town/tests/test_sub_contractor_flow.py
```

### Edited files

```
dantata_town/dantata_town/setup.py                          # +BOQ Items.assignment_type, +PI.site, +PI.sub_contractor_payment_request
dantata_town/dantata_town/doctype/site/site.json            # +expense_account
dantata_town/public/js/bill_of_quantities.js                # +Create Sub Contractor Payment Request button + modal
```

### Doctype controller — `sub_contractor_payment_request.py`

```python
import frappe
from frappe.model.document import Document
from frappe.utils import flt


class SubContractorPaymentRequest(Document):
    def validate(self):
        self._compute_amounts()

    def _compute_amounts(self):
        for row in self.items:
            row.amount = flt(row.quantity) * flt(row.rate)
        self.total_amount = sum(flt(row.amount) for row in self.items)
```

### Migration

No special patches — everything is additive. `bench migrate` picks up the new doctype JSONs automatically; `setup.py`'s existing `create_boq_custom_fields` (called from `after_install` and `after_migrate` hooks) registers the new custom fields on Site/BOQ Items/PI.

### Workflow & "Sub Contractor Cost" Item

Both admin-managed; not shipped in code. Documented in the deployment runbook.

## Section 8 — Testing

### `test_sub_contractor_payment_request.py`

- `test_doctype_installs` — parent and child doctypes exist with correct fields.
- `test_validate_recomputes_amounts` — qty/rate change → amount = qty×rate, total_amount = sum.
- `test_total_amount_sums_rows` — multi-row total.
- `test_submit_lifecycle` — insert → save → submit → cancel works.

### `test_sub_contractor_flow.py`

- `test_assignment_type_field_installed` — BOQ Items has `assignment_type` Select with default "Company", `allow_on_submit=1`, `in_list_view=1`.
- `test_expense_account_field_on_site` — Site JSON has `expense_account` Link to Account.
- `test_pi_custom_fields_installed` — PI has `site` and `sub_contractor_payment_request` Link fields on parent.
- `test_make_request_from_boq` — submitted BOQ with mixed assignment types → `make_request_from_boq(boq, supplier, today, [sub_contractor_row])` creates draft request with one item, snapshots correct, `boq`/`site`/`project` set.
- `test_make_request_with_no_rows_errors` — empty `selected` raises ValidationError.
- `test_make_request_against_draft_boq_errors` — draft BOQ raises (per Q9b).
- `test_make_purchase_invoice_succeeds` — Approved request + Site has `expense_account` + "Sub Contractor Cost" Item exists → PI returned with all expected fields.
- `test_make_purchase_invoice_without_expense_account_errors` — clear error if Site is missing `expense_account`.
- `test_make_purchase_invoice_without_sub_contractor_cost_item_errors` — clear error if Item absent.
- `test_make_purchase_invoice_on_non_approved_request_errors` — `workflow_state ≠ "Approved"` → error.
- `test_make_purchase_invoice_on_draft_request_errors` — `docstatus = 0` → error.
- `test_pi_submit_increases_project_expenses` — Spec 1 hook regression: submitting the generated PI bumps `project_expenses`.

### Manual verification (deployment runbook)

- BOQ button: open a submitted BOQ with a mix of assignment types → button appears → modal lists only Sub Contractor lines, grouped by stage, all checked → pick supplier, click Create → routed to draft request with the right rows.
- Diff prompt: edit a row's qty in the request → click Submit → modal lists the diff → Cancel → still draft, edits preserved → click Submit again → Proceed → request submitted.
- Workflow: admin-set states + transitions exercise correctly; "Create Purchase Invoice" button appears only on Approved.
- PI flow: approved request → Create PI → routed to draft PI → supplier, items[0] = (Sub Contractor Cost, qty=1, rate=total, project=request.project, expense_account=Site.expense_account), parent.site set → submit PI → request's project sees `project_expenses` increase per Spec 1 hooks.

## Risks & mitigations

- **`Sub Contractor Cost` Item missing**: PI button errors with a clear message; admin pre-creates per the deployment runbook.
- **`Site.expense_account` unset**: PI button errors with a clear message naming the Site.
- **BOQ amend after request creation**: snapshots make the diff stable; user sees the original values they generated against, not a moving target.
- **Workflow state tampering via direct API**: server-side `make_purchase_invoice` re-validates `workflow_state == "Approved"` so the JS gate isn't the only line of defense.
- **`set_missing_values()` on the PI may pull defaults that conflict with our explicit fields**: tests cover the happy path; manual verification on prod mirror is part of the runbook.

## Open follow-ups (out of scope)

- Auto-creating the "Sub Contractor Cost" Item via setup. Decision was admin-creates (Q6b); revisit if onboarding friction becomes a problem.
- Per-line supplier on `BOQ Items`. Out of scope; supplier is captured at request creation.
- Bulk PI creation across multiple Approved requests. Out of scope.
