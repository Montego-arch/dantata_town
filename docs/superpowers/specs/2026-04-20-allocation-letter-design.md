# Allocation Letter — Design Spec

**Date:** 2026-04-20
**App:** `dantata_town`
**Scope:** New submittable `Allocation Letter` doctype linked to Sales Order, a child table for installment schedules, and a site-wide settings single for the legal boilerplate. Workflow, print format, and approver role are admin-configured via the Frappe UI — not seeded by this app. Second of four Phase 2 sub-projects (Project Type refactor shipped 2026-04-20).

## Background

When a customer subscribes to a property at Dantata City Estate, the developer issues a Provisional Offer letter ("Allocation Letter"). Today these are produced in Word and printed manually. The client wants each letter tied to a Sales Order for traceability, reviewed through an internal approval queue, and printed from a consistent template that carries the legal boilerplate — with a historical snapshot so future edits to the terms don't retroactively change submitted letters. Sample PDFs of the current letter are kept with the handover docs (`ALLOCATION LETTER 1.pdf`, `ALLOCATION LETTER 2.pdf`).

## Goals

1. One `Allocation Letter` record per offer, linked to the driving Sales Order.
2. Data pre-filled from the Sales Order via a `Create → Allocation Letter` button on a submitted SO (same pattern as `Create BOQ` on Project).
3. Editable by Sales users, reviewed via a workflow, printed only after approval, finalized via submit.
4. Central 17-clause boilerplate maintained by admins in a Single; frozen as a snapshot onto each letter at submit time.
5. Conditional layout — installment schedule table only shows for installment purchases; hidden for outright.
6. Numbering aligned with the site's existing `SAL-ORD-YYYY-#####` pattern: `ALL-.YYYY.-.#####`.

## Non-goals

- Seeding the workflow, the Allocation Letter Approver role, or the print format in code. These are admin-owned.
- Automatic generation of schedule rows from a Quotation's installment plan — that arrives with the next Phase 2 sub-project (Quotation installments). For now, the user fills rows manually based on the Quotation/SO.
- Customer signature capture (wet-ink signature on the printed page is the record).
- Email dispatch of the letter to the customer from within Frappe — out of scope for v1.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | AL is not auto-created; user clicks a `Create → Allocation Letter` button on a submitted Sales Order | Matches the existing `Create BOQ` pattern on Project; keeps the user in control so no orphan drafts appear for SOs that never need a letter |
| 2 | Single standard layout with conditional blocks (Installment/Outright) | The sample PDFs differ only by data, not structure; no separate "template" doctype needed |
| 3 | 17 legal clauses live in a `Allocation Letter Terms` Single; snapshot copied onto each letter at `before_submit` | Admin can edit boilerplate from the UI; historical letters preserve the text as of their submission |
| 4 | Workflow `Draft → Pending Approval → Approved → Submitted` applied to Allocation Letter | Gives the Chairman's office a review queue; print is hidden until `Approved`; `Submitted` is the final locked state |
| 5 | `purchase_price_option` is a Select; `installment_schedule` child table is shown only when option is `Installment` | Outright deals have no schedule — avoids noise; installment deals use a child table for flexibility beyond 4 rows |
| 6 | Numbering `ALL-.YYYY.-.#####` | Consistent with existing Sales Order numbering on this site |
| 7 | Workflow, Approver role, and Print Format are admin-created in the Frappe UI; not seeded in code | Client preference — lets the admin tune the process without deploys |

## Architecture

Three new doctypes under the Dantata Town module, a custom button on Sales Order, and a mapped-doc helper in Python.

1. **`Allocation Letter`** — primary submittable doctype.
2. **`Allocation Letter Installment`** — child table for the schedule.
3. **`Allocation Letter Terms`** — Single for the central boilerplate.
4. **Sales Order client script** — adds the `Create → Allocation Letter` button.
5. **`make_allocation_letter` whitelisted method** — pre-fills a new AL from a Sales Order via `frappe.model.mapper.get_mapped_doc`.

Workflow and Print Format live in site data (configured manually by the admin). No workflow seeding in `setup.py`.

### Doctype: `Allocation Letter`

**Autoname:** `naming_series:` with options `ALL-.YYYY.-.#####` (single-entry select).
**Is submittable:** Yes.
**Module:** Dantata Town.

Fields (grouped; field-order in the JSON matches this order):

**Header block**

| Fieldname | Type | Notes |
|---|---|---|
| `naming_series` | Select | Options: `ALL-.YYYY.-.#####`. Required. |
| `letter_date` | Date | Required. Default today. |
| `sales_order` | Link → Sales Order | Required. Pre-filled by the create button. Filtered to submitted SOs. |
| `customer` | Link → Customer | Required. `fetch_from: sales_order.customer`. |
| `customer_name` | Data | `fetch_from: customer.customer_name`. Read-only. |

**Addressee**

| Fieldname | Type | Notes |
|---|---|---|
| `addressee_name` | Data | Required. Defaults to `customer_name` via the create helper. |
| `addressee_address` | Small Text | Multi-line; defaults to the customer's primary address. |

**Property**

| Fieldname | Type | Notes |
|---|---|---|
| `property_type` | Select | Options: `Residential`, `Commercial`. Required. |
| `property_description` | Data | Required. E.g. "4-bedrooms Semi-Detached Duplex - DPC". |
| `location_scheme` | Small Text | Required. E.g. "Dantata City Estate, F01 Kubwa, Abuja, FCT, Nigeria". |
| `purchase_price_option` | Select | Options: `Installment`, `Outright`. Required. |
| `cost_of_property` | Currency | Required. Default = `sales_order.grand_total`. |
| `payment_duration` | Data | Required when `purchase_price_option = Installment`. E.g. "9 months". |
| `plot_number` | Data | Required. E.g. "DCB-339B". |

**Schedule**

| Fieldname | Type | Notes |
|---|---|---|
| `installment_schedule` | Table → Allocation Letter Installment | `depends_on: eval:doc.purchase_price_option === 'Installment'`. |

**Approval & snapshot**

| Fieldname | Type | Notes |
|---|---|---|
| `workflow_state` | Link → Workflow State | Added automatically by Frappe when the workflow is applied. |
| `approved_by` | Link → User | Read-only. Stamped on transition to `Approved`. |
| `approved_on` | Datetime | Read-only. Stamped on transition to `Approved`. |
| `terms_snapshot` | Text Editor | Read-only. Populated at `before_submit`. |

**Signature/meta**

| Fieldname | Type | Notes |
|---|---|---|
| `chairman_name` | Data | Defaults from `Allocation Letter Terms.default_chairman_name`. |
| `company_name` | Data | Defaults to `"Dantata Town Developers Ltd"` (overrideable from the single). |
| `amended_from` | Link → Allocation Letter | Standard Frappe amendment chain. |

**Permissions:**

- System Manager — full.
- Sales Manager — full (create, read, write, submit, print, amend).
- Sales User — create, read, write, print (no submit).
- Allocation Letter Approver (admin-created role) — role used by the workflow transitions; no direct permission level beyond what the workflow grants.

### Doctype: `Allocation Letter Installment`

**Is child table:** Yes. **Module:** Dantata Town.

| Fieldname | Type | Notes |
|---|---|---|
| `sequence_label` | Data | Required. Free-form label: "First", "Second", "Third", "Fourth", or anything. |
| `amount` | Currency | Required. |
| `due_date` | Date | Required. Rendered under "On or before" in the print format. |

### Doctype: `Allocation Letter Terms`

**Is single:** Yes. **Module:** Dantata Town.

| Fieldname | Type | Notes |
|---|---|---|
| `conditions_text` | Text Editor | Required. The full 17-clause boilerplate, with numbering. |
| `withdrawal_clause_text` | Text Editor | Optional. The "Withdrawal of Provisional Offer" block from the sample's page 3. If blank, print format skips the section. |
| `default_chairman_name` | Data | Required. E.g. "Alhassan A. Dantata". |
| `default_company_name` | Data | Default: "Dantata Town Developers Ltd". |

**Permissions:** System Manager and Sales Manager read/write.

### Sales Order integration

**Client script** (`dantata_town/public/js/sales_order.js`, wired via `hooks.py` `doctype_js`):

```javascript
frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        if (frm.doc.docstatus === 1 && !frm.is_new()) {
            frm.add_custom_button(__("Allocation Letter"), () => {
                frappe.model.open_mapped_doc({
                    method: "dantata_town.dantata_town.doctype.allocation_letter.allocation_letter.make_allocation_letter",
                    frm: frm,
                });
            }, __("Create"));
        }
    },
});
```

The button only appears for submitted Sales Orders, and is placed in the `Create` group to match ERPNext's convention for `Create → Delivery Note` etc.

**Whitelisted helper** (in `allocation_letter.py`):

```python
@frappe.whitelist()
def make_allocation_letter(source_name, target_doc=None):
    from frappe.model.mapper import get_mapped_doc

    def set_defaults(source, target, source_parent):
        target.letter_date = frappe.utils.today()
        target.addressee_name = source.customer_name
        primary_addr = frappe.db.get_value(
            "Address",
            {"link_doctype": "Customer", "link_name": source.customer, "is_primary_address": 1},
            "name",
        )
        if primary_addr:
            addr = frappe.get_doc("Address", primary_addr)
            lines = [addr.address_line1, addr.address_line2, addr.city, addr.country]
            target.addressee_address = "\n".join([l for l in lines if l])

        terms = frappe.get_single("Allocation Letter Terms")
        if terms.default_chairman_name:
            target.chairman_name = terms.default_chairman_name
        target.company_name = terms.default_company_name or "Dantata Town Developers Ltd"

    target = get_mapped_doc(
        "Sales Order",
        source_name,
        {
            "Sales Order": {
                "doctype": "Allocation Letter",
                "field_map": {
                    "name": "sales_order",
                    "customer": "customer",
                    "customer_name": "customer_name",
                    "grand_total": "cost_of_property",
                },
            },
        },
        target_doc,
        set_defaults,
    )
    return target
```

Frappe's Connections panel auto-detects the `sales_order` Link field on Allocation Letter and lists letters under the SO without any additional configuration.

### Validation and side-effect hooks

In `dantata_town/dantata_town/utils.py` (or a dedicated `allocation_letter.py` controller — see File-change summary):

- **`validate`** — business rules:
  - When `purchase_price_option = Outright`, clear `installment_schedule` silently and clear `payment_duration`.
  - When `purchase_price_option = Installment`:
    - `payment_duration` required → `frappe.throw` if empty.
    - At least one row in `installment_schedule` → `frappe.throw` if empty.
    - Sum of row amounts == `cost_of_property` → `frappe.throw` with a message showing both totals if mismatched.
- **`on_update`** — if `workflow_state` just transitioned into `Approved` (prev workflow_state loaded via `doc.get_doc_before_save()`), stamp `approved_by = frappe.session.user` and `approved_on = frappe.utils.now()`.
- **`before_submit`** — populate `terms_snapshot`:
  ```python
  terms = frappe.get_single("Allocation Letter Terms")
  if not terms.conditions_text:
      frappe.throw(_("Please configure Allocation Letter Terms → Conditions Text before submitting."))
  snapshot = terms.conditions_text
  if terms.withdrawal_clause_text:
      snapshot += "\n\n" + terms.withdrawal_clause_text
  self.terms_snapshot = snapshot
  ```

### Client-side print guard

In `dantata_town/public/js/allocation_letter.js`:

```javascript
frappe.ui.form.on("Allocation Letter", {
    refresh(frm) {
        const state = frm.doc.workflow_state;
        const can_print = state === "Approved" || state === "Submitted";
        frm.page.btn_print_action?.toggle(can_print);
        if (!can_print) {
            frm.page.clear_secondary_action();
        }
    },
    purchase_price_option(frm) {
        if (frm.doc.purchase_price_option === "Outright") {
            frm.clear_table("installment_schedule");
            frm.set_value("payment_duration", null);
            frm.refresh_field("installment_schedule");
        }
    },
});
```

## Admin-managed artifacts (not in code)

These are documented here for the admin who sets up the site after the app is installed:

1. **Workflow `Allocation Letter Approval`** applied to Allocation Letter, `workflow_state_field = workflow_state`. States and transitions per the matrix in the workflow section below.
2. **Role `Allocation Letter Approver`** created in Role List, assigned to the Chairman-office user(s).
3. **Print Format `Allocation Letter`** on the site, `doc_type = Allocation Letter`, `print_format_type = Jinja`. Reference Jinja body below.

### Workflow matrix (for admin reference)

States:

| State | docstatus |
|---|---|
| Draft | 0 |
| Pending Approval | 0 |
| Approved | 0 |
| Submitted | 1 |

Transitions:

| From → To | Action | Allowed role |
|---|---|---|
| Draft → Pending Approval | Submit for Approval | Sales User, Sales Manager |
| Pending Approval → Approved | Approve | Allocation Letter Approver |
| Pending Approval → Draft | Request Changes | Allocation Letter Approver |
| Approved → Submitted | Finalize | Sales Manager |
| Approved → Draft | Recall | Allocation Letter Approver |

### Reference Jinja for the Print Format

```jinja
<!-- Header -->
<div class="header">
  <img src="/assets/dantata_town/images/logo.png" style="height:60px;">
  <div class="rc-no" style="float:right;">RC NO: 966609</div>
</div>

<!-- Date + Subject to Contract row -->
<div style="margin-top:30px;">
  <span>{{ frappe.format(doc.letter_date, {'fieldtype': 'Date'}) }}</span>
  <span style="float:right; font-style:italic;">'Subject to Contract'</span>
</div>

<!-- Addressee -->
<div style="margin-top:30px; font-weight:bold;">
  {{ doc.addressee_name }}<br>
  {{ doc.addressee_address | replace('\n', '<br>') | safe }}
</div>

<p style="margin-top:20px;">Dear Sir/Ma,</p>

<!-- Title -->
<h3 style="text-align:center; text-decoration:underline;">
  PROVISIONAL OFFER FOR HOUSE/PLOT RESERVATION<br>
  AT {{ doc.location_scheme | upper }}
</h3>

<!-- Intro paragraph -->
<p>
  We hereby acknowledge the receipt of your Expression of Interest Form in respect of a
  {{ doc.property_description }} at {{ doc.location_scheme }} and hereby provisionally
  offer you a subscription to <b>House/Plot Number {{ doc.plot_number }}</b> on the
  following terms and conditions below, which are made subject to review:
</p>

<!-- Property table -->
<table border="1" cellpadding="6" cellspacing="0" style="width:100%; margin-top:10px;">
  <tr><td>Type</td><td>{{ doc.property_type }}</td></tr>
  <tr><td>Description</td><td>{{ doc.property_description }}</td></tr>
  <tr><td>Location/Scheme</td><td>{{ doc.location_scheme }}</td></tr>
  <tr>
    <td>Purchase Price Option</td>
    <td>
      Installment Payment within 90-days of each interval
      {% if doc.purchase_price_option == 'Installment' %}&#9746;{% else %}&#9744;{% endif %}
      &nbsp;&nbsp; Outright
      {% if doc.purchase_price_option == 'Outright' %}&#9746;{% else %}&#9744;{% endif %}
    </td>
  </tr>
  <tr><td>Cost of Property</td><td>{{ frappe.utils.fmt_money(doc.cost_of_property, currency='NGN') }}</td></tr>
  <tr><td>Payment Duration</td><td>{{ doc.payment_duration or '-' }}</td></tr>
</table>

<!-- Payment Schedule (installment only) -->
{% if doc.purchase_price_option == 'Installment' and doc.installment_schedule %}
<h4 style="margin-top:20px;">PAYMENT SCHEDULE</h4>
<table border="1" cellpadding="6" cellspacing="0" style="width:100%;">
  <thead>
    <tr>
      <th></th>
      {% for row in doc.installment_schedule %}
        <th>{{ row.sequence_label }}</th>
      {% endfor %}
      <th>Total</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Amount</td>
      {% for row in doc.installment_schedule %}
        <td>{{ frappe.utils.fmt_money(row.amount, currency='NGN') }}</td>
      {% endfor %}
      <td>{{ frappe.utils.fmt_money(doc.cost_of_property, currency='NGN') }}</td>
    </tr>
    <tr>
      <td>On or before</td>
      {% for row in doc.installment_schedule %}
        <td>{{ frappe.format(row.due_date, {'fieldtype': 'Date'}) }}</td>
      {% endfor %}
      <td></td>
    </tr>
  </tbody>
</table>
{% endif %}

<!-- Conditions snapshot -->
<div style="margin-top:30px;">
  {{ doc.terms_snapshot | safe }}
</div>

<!-- Chairman signature -->
<div style="margin-top:40px;">
  <p>Yours faithfully,<br>
     <b>For: {{ doc.company_name }}</b></p>
  <br><br>
  <p><b>{{ doc.chairman_name }}</b><br>
     <b>Chairman</b></p>
</div>

<!-- Subscriber's Acceptance -->
<div style="margin-top:40px;">
  <h4>Subscriber's Acceptance:</h4>
  <p>I _______________________________________________ accept this
  provisional offer on all the terms and conditions stated above and willing to abide
  by same. I am willing to be a subscriber to the scheme.</p>
  <div style="margin-top:20px;">Signature _______________________ &nbsp;&nbsp; Date _______________</div>
  <div><b>(Attach means of Identification)</b></div>
</div>
```

The admin pastes this into the Print Format's `html` field and adjusts styling via the Print Format's CSS field to match the sample PDF's margins.

## Data flow

1. Sales user opens a submitted Sales Order.
2. Clicks `Create → Allocation Letter`.
3. `make_allocation_letter` returns a new in-memory AL doc with `sales_order`, `customer`, `customer_name`, `cost_of_property` set, plus addressee block and chairman defaults.
4. User fills property block, plot number, and (if Installment) schedule rows + payment duration.
5. User saves → server validates (schedule sum, duration) and silently clears schedule/duration for Outright.
6. User actions workflow `Submit for Approval` → state moves to `Pending Approval`.
7. Approver reviews and actions `Approve` → state moves to `Approved`; `approved_by` and `approved_on` stamped via `on_update`; Print button now visible.
8. Sales Manager actions `Finalize` → Frappe `submit()` fires; `before_submit` copies `Allocation Letter Terms.conditions_text` (+ withdrawal clause if present) into `doc.terms_snapshot`; docstatus = 1.
9. Letter is printed; customer signs the printed page; signed copy scanned and attached back to the record via Frappe's standard attachments.

## Error handling

- **Missing Terms Single content at submit** — throw with "Please configure Allocation Letter Terms → Conditions Text before submitting."
- **Schedule sum mismatch** — throw with both totals shown: "Installment schedule total (₦X) does not match Cost of Property (₦Y)."
- **Installment without duration** — throw with "Payment Duration is required for installment offers."
- **Installment without schedule rows** — throw with "Add at least one installment row for installment offers."
- **Outright with schedule/duration** — silently clear on save (no error; Outright letters have no schedule).
- **Attempting to create AL from a draft SO** — the button only appears on submitted SOs, so this is prevented at the UI. If someone calls `make_allocation_letter` directly on a draft, `get_mapped_doc` will still work, but the `sales_order` Link-field docstatus validation on Allocation Letter save (configured via `no_copy` + `search_index` + the doctype's `states`) will reject draft SOs. Not a required hard-block for v1.

## Testing

### Unit tests (`tests/test_allocation_letter.py`)

1. **`make_allocation_letter` pre-fills from SO** — given a submitted SO with customer, grand_total, and primary address, the returned AL has `sales_order`, `customer`, `customer_name`, `cost_of_property`, `addressee_name` populated.
2. **Outright clears schedule and duration** — save an AL with `purchase_price_option=Outright` and pre-populated schedule rows + duration; after save both are cleared, no error.
3. **Installment schedule sum mismatch rejected** — AL with `purchase_price_option=Installment`, `cost_of_property=1000`, rows summing to 900 → `frappe.ValidationError`.
4. **Installment without payment_duration rejected** — installment AL with valid schedule but empty `payment_duration` → `frappe.ValidationError`.
5. **Installment without schedule rows rejected** — installment AL with no rows → `frappe.ValidationError`.
6. **Terms snapshot at submit** — populate Single with known text; submit a valid AL; `terms_snapshot` equals that text. Then edit the Single; reload the submitted AL; `terms_snapshot` unchanged.
7. **Missing Terms at submit rejected** — clear `conditions_text` on the Single; submitting a valid AL raises `frappe.ValidationError` with the configuration message.
8. **Approved stamps** — simulate workflow transition by setting `workflow_state = "Approved"` via `db_set` on a saved AL, reload, trigger `on_update`; `approved_by == frappe.session.user`, `approved_on` set.
9. **Create button visibility** — client-side, covered by manual smoke test.

### Manual smoke test

- Admin configures:
  1. `Allocation Letter Terms` single with known boilerplate text, chairman name, company name.
  2. Role `Allocation Letter Approver` (Role List).
  3. Workflow `Allocation Letter Approval` with the 4 states and 5 transitions.
  4. Print Format `Allocation Letter` using the reference Jinja.
- Create a submitted Sales Order for a real customer with a primary address and a grand_total.
- From the SO, click `Create → Allocation Letter`. Verify `sales_order`, `customer`, `customer_name`, `cost_of_property`, `addressee_name`, `addressee_address`, `chairman_name`, `company_name` are pre-filled.
- Fill property block, set `purchase_price_option = Installment`, add 4 schedule rows summing to `cost_of_property`, set `payment_duration`, save.
- Verify installment_schedule is visible, payment_duration is visible, both required.
- Change option to Outright; save. Schedule and duration both clear silently.
- Switch back to Installment, re-fill; Submit for Approval → the doc moves to `Pending Approval`, Print button hidden.
- Log in as an `Allocation Letter Approver` user. Approve the letter. `approved_by` and `approved_on` fill in; Print button now shows.
- Log back in as Sales Manager. Finalize. Verify `docstatus = 1`, `terms_snapshot` holds the configured text.
- Print the letter — output matches the sample PDF's structure.
- Edit the Terms Single; re-print the submitted letter — snapshot is unchanged.
- Open the Sales Order → Connections panel — the Allocation Letter appears and clicks through.

## File-change summary

**New:**

- `dantata_town/dantata_town/doctype/allocation_letter/` — `__init__.py`, `allocation_letter.json`, `allocation_letter.py`, `test_allocation_letter.py`. (Form script lives in `public/js/allocation_letter.js`, wired via `hooks.py` `doctype_js` — matches the existing `public/js/project.js` pattern already used by the app.)
- `dantata_town/dantata_town/doctype/allocation_letter_installment/` — `__init__.py`, `allocation_letter_installment.json`, `allocation_letter_installment.py`.
- `dantata_town/dantata_town/doctype/allocation_letter_terms/` — `__init__.py`, `allocation_letter_terms.json`, `allocation_letter_terms.py`.
- `dantata_town/dantata_town/tests/test_allocation_letter.py` — integration tests covering the `make_allocation_letter` helper, validation, snapshot, and approval stamps.
- `dantata_town/public/js/sales_order.js` — adds the `Create → Allocation Letter` button.
- `dantata_town/public/js/allocation_letter.js` — hides Print until Approved, clears schedule/duration on Outright toggle.
- `dantata_town/public/images/logo.png` — Dantata logo for the print format header (optional; admin can link any URL).

**Modified:**

- `dantata_town/hooks.py` — add `Sales Order` and `Allocation Letter` entries to `doctype_js`.

**Unchanged:**

- `setup.py` — no new seeding needed (workflow/role/print format are admin-managed). If a `default_company_name` seed is wanted for the Single, that can be added to `_seed_project_types_and_subtypes`'s sibling helper later.

## Out of scope / future work

- Auto-generation of `installment_schedule` rows from a Quotation's installment plan — arrives with the Quotation Installments Phase 2 sub-project.
- Email dispatch of the printed PDF to the customer.
- Customer signature capture (wet-ink today).
- Multiple Letter Templates (variant layouts) — would become a later doctype if the client needs commercial-vs-residential variants.
