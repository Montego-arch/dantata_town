# Customer Payment Report — Design Spec

**Date:** 2026-04-20
**App:** `dantata_town`
**Scope:** A monthly HTML-email digest to internal finance/sales staff listing every customer with an outstanding Sales Invoice balance, enriched with property information (type / description / plot number) from the customer's Allocation Letter. Report is also available on demand via a Script Report in the Frappe UI. Fourth Phase 2 sub-project; last remaining after this is the Customer History document.

## Background

The client (Dantata Town Developers) invoices customers throughout the lifecycle of an Allocation Letter — deposit, installments, final balance. Finance staff need a regular snapshot of who owes what, so they can chase up payments before they drift overdue, and so management can see the aggregate receivables exposure at a glance. Today this is pulled manually from ERPNext's Accounts Receivable report.

The new feature wraps ERPNext's existing AR data into a monthly email + on-demand UI view that also surfaces the property being paid for (the join to Allocation Letter), which matters to finance staff handling disputes like "I already paid for DCB-339B".

## Goals

1. Monthly HTML-email digest to a configurable list of internal staff addresses on a configurable day-of-month.
2. One row per outstanding Sales Invoice, grouped by customer.
3. Each row shows: customer, invoice, due date, outstanding amount, property type, property description, plot number.
4. Same data exposed as a Script Report in the Frappe UI (`Reports → Customer Payment Report`).
5. Manual "Send Now" button on the settings page for ad-hoc dispatch or testing.
6. Graceful handling of empty results — email still sends with an explicit "No outstanding balances" body so staff can't miss a silent failure.
7. Status recorded on each run so silent failures surface visibly in the settings doc.

## Non-goals

- Per-customer emails directly to customers. This report is internal-only.
- PDF attachment. HTML inline only for v1 (finance staff want speed; PDFs add rendering cost + extra clicks).
- Forward-looking installment data from Sales Order `payment_schedule`. Only what the AR ledger says is owed right now (Sales Invoice `outstanding_amount`).
- Filters / parameters on the Script Report in v1. If staff need to filter by customer or date range later, we extend.
- Integration with the existing Quotation Installments or Allocation Letter work — this feature only reads from them.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Recipient = configurable staff email list; not customer-facing. | Per client: "emailed to concerned staff email that will be provided by management". |
| 2 | "Amount owed" = `Sales Invoice.outstanding_amount` where `docstatus = 1` and `outstanding_amount > 0`. | This is what the AR ledger says is owed. Matches meeting phrasing "invoices". Forward-looking SO-schedule rows are a separate analysis. |
| 3 | Property info from Allocation Letter via `Sales Invoice Item.sales_order → Allocation Letter.sales_order`. | AL has the exact property fields finance needs (type, description, plot_number). |
| 4 | Graceful fallback when a customer's SI has no matching AL — columns show `"—"`. | Edge case: legacy invoices, or deals not finalized via AL. |
| 5 | Configurable send day (`send_day_of_month`, 1–28), default 1. | Admin can align with payroll / bank-statement cycles without redeploys. Capped at 28 to avoid month-end edge cases. |
| 6 | HTML table inline in the email body. No PDF. | Finance staff want to scan the digest in their inbox. Matches the use case ("reduce disputes, keep staff informed"). |
| 7 | Always send, even with zero outstanding rows. | Silent-on-empty is risky — staff can't tell if the job failed vs. there's genuinely nothing to report. |
| 8 | Both email and Script Report call a shared aggregation helper `build_customer_payment_report_rows()`. | Single source of truth prevents data drift between the inbox view and the UI view. |
| 9 | `Customer Payment Report Settings` is a new Single, not tacked onto an existing settings doc. | Narrow scope; one page for everything: recipients, schedule, enable/disable, last-sent status. |
| 10 | Manual trigger via "Send Now" button on the Settings Single. | For testing, or ad-hoc sends between scheduled runs. |

## Architecture

Four moving parts: a Single doctype, a Python module with scheduled + whitelisted functions, a Script Report, and a small client script.

### Single doctype: `Customer Payment Report Settings`

**Module:** Dantata Town. **issingle:** 1. **track_changes:** 1.

| Fieldname | Type | Default | Notes |
|---|---|---|---|
| `enabled` | Check | `1` | Uncheck to pause the scheduled send. |
| `send_day_of_month` | Int | `1` | 1–28. Validator rejects out-of-range. |
| `recipient_emails` | Small Text | — | One email per line. Required when `enabled = 1`. |
| `last_sent_date` | Date | — | Read-only. Set after each successful send. |
| `last_sent_status` | Select | — | Options: `Success`, `Failed`, `Skipped (disabled)`, `Skipped (wrong day)`. Read-only. |

**Permissions:** `System Manager` + `Accounts Manager` read/write; `Accounts User` read-only.

**Validator:**

```python
def validate(self):
    if self.enabled and not (self.recipient_emails or "").strip():
        frappe.throw(_("Recipient Emails is required when Enabled is checked."))
    if self.send_day_of_month < 1 or self.send_day_of_month > 28:
        frappe.throw(_("Send Day of Month must be between 1 and 28."))
    for line in (self.recipient_emails or "").splitlines():
        line = line.strip()
        if line:
            frappe.utils.validate_email_address(line, throw=True)
```

### Python module: `dantata_town/dantata_town/reports.py`

Three top-level functions (public) and three helpers (private).

**Public:**

- `build_customer_payment_report_rows()` — shared aggregation, returns a list of dicts.
- `send_monthly_customer_payment_report()` — scheduled entry point (wired in hooks.daily).
- `send_report_now()` — `@frappe.whitelist()` manual trigger.

**Private (module-level underscore-prefixed):**

- `_send_report_email(settings, today)` — renders + sends.
- `_record_status(settings, status, sent_date=None)` — updates the Single's status fields via `frappe.db.set_value`.
- `_EMAIL_TEMPLATE` — Jinja HTML constant.

**Aggregation helper:**

```python
def build_customer_payment_report_rows():
    """Return a list of dicts, one per outstanding (customer, invoice) row,
    ordered by customer asc, posting_date asc. Each row contains:
      customer, customer_name, name (invoice), posting_date, due_date,
      outstanding_amount, property_type, property_description, plot_number.
    Property fields default to "—" when there's no linked Allocation Letter.
    """
    sis = frappe.get_all(
        "Sales Invoice",
        filters={"docstatus": 1, "outstanding_amount": (">", 0)},
        fields=["name", "customer", "customer_name", "posting_date",
                "due_date", "outstanding_amount"],
        order_by="customer asc, posting_date asc",
    )
    so_to_al = {}
    rows = []
    for si in sis:
        so = frappe.db.get_value(
            "Sales Invoice Item",
            {"parent": si.name, "sales_order": ("!=", "")},
            "sales_order",
        )
        if so and so not in so_to_al:
            al_name = frappe.db.get_value(
                "Allocation Letter",
                {"sales_order": so, "docstatus": 1},
                "name",
                order_by="letter_date desc",
            )
            so_to_al[so] = frappe.db.get_value(
                "Allocation Letter", al_name,
                ["property_type", "property_description", "plot_number"],
                as_dict=True,
            ) if al_name else None
        al = so_to_al.get(so) if so else None
        rows.append({
            **si,
            "property_type": (al or {}).get("property_type") or "—",
            "property_description": (al or {}).get("property_description") or "—",
            "plot_number": (al or {}).get("plot_number") or "—",
        })
    return rows
```

**Scheduled entry point:**

```python
def send_monthly_customer_payment_report():
    """Scheduled daily; sends the monthly digest when today is the configured day.
    Always records status so silent failures surface visibly.
    """
    settings = frappe.get_single("Customer Payment Report Settings")
    today = frappe.utils.getdate()

    if not settings.enabled:
        _record_status(settings, "Skipped (disabled)")
        return
    if today.day != int(settings.send_day_of_month):
        _record_status(settings, "Skipped (wrong day)")
        return
    # Double-send guard: scheduler may retry within the same day.
    if settings.last_sent_date and frappe.utils.getdate(settings.last_sent_date) == today:
        _record_status(settings, "Success")
        return

    try:
        _send_report_email(settings, today)
        _record_status(settings, "Success", sent_date=today)
    except Exception:
        _record_status(settings, "Failed")
        raise
```

**Manual trigger:**

```python
@frappe.whitelist()
def send_report_now():
    frappe.only_for(["System Manager", "Accounts Manager"])
    settings = frappe.get_single("Customer Payment Report Settings")
    if not settings.enabled:
        frappe.throw(_("Enable the report before sending."))
    today = frappe.utils.getdate()
    try:
        _send_report_email(settings, today)
        _record_status(settings, "Success", sent_date=today)
    except Exception:
        _record_status(settings, "Failed")
        raise
```

**Email builder:**

```python
def _send_report_email(settings, today):
    rows = build_customer_payment_report_rows()
    total = sum(frappe.utils.flt(r["outstanding_amount"]) for r in rows)
    month_label = today.strftime("%B %Y")
    html = frappe.render_template(_EMAIL_TEMPLATE, {
        "rows": rows, "total": total, "month_label": month_label,
    })
    recipients = [
        line.strip() for line in (settings.recipient_emails or "").splitlines()
        if line.strip()
    ]
    if not recipients:
        frappe.throw(_("No recipient emails configured."))
    frappe.sendmail(
        recipients=recipients,
        subject=_("Monthly Customer Payment Report — {0}").format(month_label),
        message=html,
        now=True,
    )


def _record_status(settings, status, sent_date=None):
    updates = {"last_sent_status": status}
    if sent_date:
        updates["last_sent_date"] = sent_date
    frappe.db.set_value(
        "Customer Payment Report Settings", None, updates, update_modified=False
    )
```

**Jinja HTML template (`_EMAIL_TEMPLATE`):**

```jinja
<h3>Monthly Customer Payment Report — {{ month_label }}</h3>
{% if rows %}
<table cellpadding="8" cellspacing="0" border="1" style="border-collapse:collapse;">
  <thead>
    <tr>
      <th>Customer</th><th>Invoice</th><th>Due Date</th>
      <th>Outstanding</th><th>Property Type</th><th>Description</th><th>Plot</th>
    </tr>
  </thead>
  <tbody>
  {% for r in rows %}
    <tr>
      <td>{{ r.customer_name or r.customer }}</td>
      <td>{{ r.name }}</td>
      <td>{{ frappe.format(r.due_date, {'fieldtype': 'Date'}) }}</td>
      <td style="text-align:right;">{{ frappe.utils.fmt_money(r.outstanding_amount, currency='NGN') }}</td>
      <td>{{ r.property_type }}</td>
      <td>{{ r.property_description }}</td>
      <td>{{ r.plot_number }}</td>
    </tr>
  {% endfor %}
  </tbody>
  <tfoot>
    <tr>
      <td colspan="3" style="text-align:right;"><b>Total Outstanding</b></td>
      <td style="text-align:right;"><b>{{ frappe.utils.fmt_money(total, currency='NGN') }}</b></td>
      <td colspan="3"></td>
    </tr>
  </tfoot>
</table>
{% else %}
<p>No outstanding balances this month.</p>
{% endif %}
```

### Script Report: `Customer Payment Report`

Location: `dantata_town/dantata_town/report/customer_payment_report/`. Files:

- `__init__.py`
- `customer_payment_report.json` — `is_standard: "Yes"`, `report_type: "Script Report"`, `ref_doctype: "Sales Invoice"`, `module: "Dantata Town"`, permissions for `Accounts Manager`, `Accounts User`, `System Manager`.
- `customer_payment_report.py`:

```python
import frappe
from dantata_town.dantata_town.reports import build_customer_payment_report_rows


def execute(filters=None):
    columns = [
        {"label": "Customer", "fieldname": "customer", "fieldtype": "Link",
         "options": "Customer", "width": 180},
        {"label": "Customer Name", "fieldname": "customer_name",
         "fieldtype": "Data", "width": 200},
        {"label": "Invoice", "fieldname": "name", "fieldtype": "Link",
         "options": "Sales Invoice", "width": 180},
        {"label": "Posting Date", "fieldname": "posting_date",
         "fieldtype": "Date", "width": 110},
        {"label": "Due Date", "fieldname": "due_date", "fieldtype": "Date", "width": 110},
        {"label": "Outstanding", "fieldname": "outstanding_amount",
         "fieldtype": "Currency", "width": 140},
        {"label": "Property Type", "fieldname": "property_type",
         "fieldtype": "Data", "width": 130},
        {"label": "Description", "fieldname": "property_description",
         "fieldtype": "Data", "width": 260},
        {"label": "Plot", "fieldname": "plot_number", "fieldtype": "Data", "width": 100},
    ]
    return columns, build_customer_payment_report_rows()
```

- `customer_payment_report.js` — empty shell for v1 (no filters). Present so Frappe doesn't complain when the report loads.

### Client script for the Single

`dantata_town/public/js/customer_payment_report_settings.js`:

```javascript
frappe.ui.form.on("Customer Payment Report Settings", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("Send Now"), () => {
                frappe.confirm(
                    __("Send the report to all configured recipients now?"),
                    () => {
                        frappe.call({
                            method: "dantata_town.dantata_town.reports.send_report_now",
                            freeze: true,
                            freeze_message: __("Sending..."),
                            callback: () => {
                                frappe.show_alert({
                                    message: __("Report sent"),
                                    indicator: "green",
                                });
                                frm.reload_doc();
                            },
                        });
                    },
                );
            });
        }
    },
});
```

### Hooks wiring

In `dantata_town/hooks.py`:

```python
doctype_js = {
    "Project": "public/js/project.js",
    "Sales Order": "public/js/sales_order.js",
    "Allocation Letter": "public/js/allocation_letter.js",
    "Quotation": "public/js/quotation.js",
    "Customer Payment Report Settings": "public/js/customer_payment_report_settings.js",
}

scheduler_events = {
    "daily": [
        "dantata_town.dantata_town.reports.send_monthly_customer_payment_report",
    ],
}
```

## Data flow

**Scheduled run (daily):**

1. Scheduler fires `send_monthly_customer_payment_report()`.
2. Function loads `Customer Payment Report Settings` single.
3. If `enabled = 0` → record `Skipped (disabled)` status, return.
4. If `today.day != send_day_of_month` → record `Skipped (wrong day)`, return.
5. If `last_sent_date == today` → record `Success` (no-op, double-send guard), return.
6. Try: `_send_report_email(settings, today)` → on success, record `Success` with `last_sent_date = today`. On exception, record `Failed` and re-raise.
7. `_send_report_email`:
   - Calls `build_customer_payment_report_rows()` — queries outstanding SIs, joins ALs.
   - Renders `_EMAIL_TEMPLATE` with rows + total + month label.
   - Parses `recipient_emails` into a list; throws if empty.
   - `frappe.sendmail(recipients, subject, message, now=True)`.

**UI run (Script Report):**

1. User navigates to `Reports → Customer Payment Report`.
2. Frappe calls `customer_payment_report.execute(filters=None)`.
3. Function calls `build_customer_payment_report_rows()` — same helper as the email.
4. Function returns `(columns, rows)`. Frappe renders the table.
5. User can sort, filter by column, export to Excel via the toolbar.

**Manual "Send Now":**

1. User opens the Settings Single, clicks `Send Now`, confirms.
2. Client script calls `send_report_now` (whitelisted).
3. Permission gate: `frappe.only_for(["System Manager", "Accounts Manager"])`.
4. Throws if `enabled = 0`.
5. Calls `_send_report_email(settings, today)` — same path as the scheduled function, no day/last-sent checks.

## Error handling

| Scenario | Behavior |
|---|---|
| `enabled = 0` | Scheduler skips; status `"Skipped (disabled)"`. `Send Now` rejects with "Enable the report before sending." |
| Today != configured day | Scheduler skips; status `"Skipped (wrong day)"`. |
| Scheduler retries same day | `last_sent_date == today` → short-circuit; no double-send. |
| `recipient_emails` empty (when `enabled = 1`) | Save-time validator blocks it. Defense in depth: `_send_report_email` also throws. |
| `sendmail` failure (SMTP down, template error) | Exception caught in the entry point, `last_sent_status = "Failed"`, re-raised so the scheduler log records it. |
| Zero outstanding rows | `rows = []`; template renders empty-state paragraph; email still sent. |
| Customer has SIs but no linked AL | `property_type / property_description / plot_number` each = `"—"`. No crash. |
| Customer SI has no linked Sales Order | Same graceful fallback as above. |
| Invalid email in `recipient_emails` | Save-time validator throws via `frappe.utils.validate_email_address`. |
| `send_day_of_month` out of range (0, 29, 31) | Save-time validator rejects. |

## Testing

### Unit tests — `dantata_town/dantata_town/tests/test_customer_payment_report.py`

1. **Settings validator: day-of-month boundaries** — save with `send_day_of_month = 0` raises; `= 29` raises; `= 28` saves; `= 1` saves.
2. **Settings validator: enabled without recipients rejected** — `enabled=1`, empty `recipient_emails` → `ValidationError`.
3. **Settings validator: malformed email rejected** — `recipient_emails = "not-an-email"` → `ValidationError`.
4. **Settings validator: multiple valid emails accepted** — `"a@b.com\nc@d.com"` saves cleanly.
5. **Aggregation: only submitted outstanding SIs** — fixture with two submitted SIs (one `outstanding_amount > 0`, one `= 0`) → only the first appears in rows.
6. **Aggregation: AL fields populated when available** — fixture submitted SI → SO → submitted AL → row's `property_type` / `property_description` / `plot_number` match the AL.
7. **Aggregation: AL fields default to "—"** — fixture submitted SI with no linked SO → all three AL fields = `"—"`.
8. **Scheduled: disabled skips** — `enabled=0`; call `send_monthly_customer_payment_report()` → no email queued; `last_sent_status = "Skipped (disabled)"`.
9. **Scheduled: wrong day skips** — set `send_day_of_month` to tomorrow's day → call → no email queued; `last_sent_status = "Skipped (wrong day)"`.
10. **Scheduled: right day sends** — set `send_day_of_month = today.day`, `last_sent_date = None`, recipients configured → call → exactly one email queued (check via `Email Queue`); `last_sent_status = "Success"`, `last_sent_date = today`.
11. **Scheduled: double-send guard** — `last_sent_date = today` → call twice → only the pre-test queue entries exist; status stays `"Success"`; no new email queued.
12. **Scheduled: empty rows still sends** — monkeypatch `build_customer_payment_report_rows` to return `[]` → email still queued, body contains "No outstanding balances".
13. **`send_report_now`: permission gate** — as a user with only `Accounts User` role, call → `frappe.PermissionError`.
14. **`send_report_now`: disabled rejected** — `enabled=0`; call as System Manager → throws "Enable the report before sending."
15. **Script Report `execute` shape** — call with `filters=None` → first element is a list of 9 column dicts in expected order; second is the aggregation output.

### Email capture in tests

Frappe's test framework sets `frappe.flags.in_test = True` which queues emails without sending. Tests assert by counting rows in the `Email Queue` doctype that match the subject pattern.

### Manual smoke test

1. Navigate to `/app/customer-payment-report-settings`. Set `enabled=1`, `send_day_of_month=today.day`, `recipient_emails` = your test inbox. Save.
2. Click `Send Now` → confirm → toast "Report sent".
3. Inspect inbox: email subject `Monthly Customer Payment Report — <Month> <Year>`, body HTML table with one row per outstanding SI, total at the bottom.
4. Save settings with `send_day_of_month = 0` → save blocked with clear message.
5. Save settings with `recipient_emails = "not-an-email"` → save blocked.
6. Navigate to `/app/query-report/Customer Payment Report` → same rows in a sortable grid. Export to Excel via the toolbar — works.
7. Clear all Sales Invoice outstanding balances (pay them all). `Send Now` again → email arrives with body "No outstanding balances this month."
8. Uncheck `enabled`, save. Click `Send Now` → clear error "Enable the report before sending."
9. Re-enable. Tomorrow the scheduler fires and sends (or skips if wrong day).

## File-change summary

**New:**

- `dantata_town/dantata_town/doctype/customer_payment_report_settings/` — `__init__.py`, `customer_payment_report_settings.json`, `customer_payment_report_settings.py` (controller with `validate`).
- `dantata_town/dantata_town/reports.py` — aggregation helper, scheduled entry point, `send_report_now`, `_send_report_email`, `_record_status`, `_EMAIL_TEMPLATE`.
- `dantata_town/dantata_town/report/customer_payment_report/` — `__init__.py`, `customer_payment_report.json`, `customer_payment_report.py`, `customer_payment_report.js`.
- `dantata_town/public/js/customer_payment_report_settings.js` — Send Now button.
- `dantata_town/dantata_town/tests/test_customer_payment_report.py` — 15 unit tests.

**Modified:**

- `dantata_town/hooks.py` — add `scheduler_events` dict with the daily entry; add Settings Single entry to `doctype_js`.

**Unchanged:**

- All existing doctypes and modules from prior Phase 2 work.

## Out of scope / future work

- Per-customer emails sent directly to customers (the opposite of this internal digest).
- PDF attachment of the report for archival.
- Filters on the Script Report (by customer, by date range, by property type).
- Forward-looking installment view — showing upcoming `Sales Order.payment_schedule` rows that haven't been invoiced yet.
- Aging buckets (0–30 / 31–60 / 61–90 / 90+ days overdue). v2 if demand exists.
- Color-coding overdue rows in the HTML email (visually lighter than aging buckets but still useful).
