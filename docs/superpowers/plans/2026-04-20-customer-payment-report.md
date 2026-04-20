# Customer Payment Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a monthly HTML-email digest of outstanding Sales Invoices (joined to Allocation Letter property info) plus an on-demand Script Report, both backed by a shared aggregation helper, configured via a new `Customer Payment Report Settings` Single.

**Architecture:** A new Single stores recipient emails, send day, enable flag, and last-sent status. `dantata_town/dantata_town/reports.py` exposes a shared aggregation helper used by both a scheduled-daily entry point and a whitelisted `send_report_now`. A Script Report at `report/customer_payment_report/` reuses the same helper. The Single has a Send Now button wired via a new client script and `doctype_js`.

**Tech Stack:** Frappe Framework, ERPNext (Sales Invoice, Sales Invoice Item), Python 3, `frappe.sendmail`, `FrappeTestCase`, Script Report.

**Spec:** `docs/superpowers/specs/2026-04-20-customer-payment-report-design.md`

**Working directory:** `/home/okeke/clients/graceco/frappe-bench/apps/dantata_town`

**Test command:** `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_customer_payment_report`

**Migrate command:** `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`

---

## File Structure

**Files created:**

| Path | Responsibility |
|---|---|
| `dantata_town/dantata_town/doctype/customer_payment_report_settings/__init__.py` | Package marker |
| `dantata_town/dantata_town/doctype/customer_payment_report_settings/customer_payment_report_settings.json` | Single DocType definition |
| `dantata_town/dantata_town/doctype/customer_payment_report_settings/customer_payment_report_settings.py` | Controller with `validate` |
| `dantata_town/dantata_town/reports.py` | Aggregation helper, scheduled entry point, `send_report_now`, `_send_report_email`, `_record_status`, `_EMAIL_TEMPLATE` |
| `dantata_town/dantata_town/report/__init__.py` | Package marker (may already exist) |
| `dantata_town/dantata_town/report/customer_payment_report/__init__.py` | Package marker |
| `dantata_town/dantata_town/report/customer_payment_report/customer_payment_report.json` | Script Report metadata |
| `dantata_town/dantata_town/report/customer_payment_report/customer_payment_report.py` | `execute(filters)` calling the shared helper |
| `dantata_town/dantata_town/report/customer_payment_report/customer_payment_report.js` | Empty filter shell for v1 |
| `dantata_town/public/js/customer_payment_report_settings.js` | Send Now button |
| `dantata_town/dantata_town/tests/test_customer_payment_report.py` | Unit tests (settings validator, aggregation, scheduled flow, Send Now, Script Report) |

**Files modified:**

| Path | Change |
|---|---|
| `dantata_town/hooks.py` | Add `scheduler_events["daily"]`; add Settings Single entry to `doctype_js` |

---

## Task 1: Create `Customer Payment Report Settings` Single

**Files:**
- Create: `dantata_town/dantata_town/doctype/customer_payment_report_settings/__init__.py`
- Create: `dantata_town/dantata_town/doctype/customer_payment_report_settings/customer_payment_report_settings.json`
- Create: `dantata_town/dantata_town/doctype/customer_payment_report_settings/customer_payment_report_settings.py`

- [ ] **Step 1: Create the package marker**

File: `dantata_town/dantata_town/doctype/customer_payment_report_settings/__init__.py`

```python
```

(empty file)

- [ ] **Step 2: Create the Single DocType JSON**

File: `dantata_town/dantata_town/doctype/customer_payment_report_settings/customer_payment_report_settings.json`

```json
{
 "actions": [],
 "creation": "2026-04-20 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "enabled",
  "send_day_of_month",
  "recipient_section",
  "recipient_emails",
  "status_section",
  "last_sent_date",
  "column_break_status",
  "last_sent_status"
 ],
 "fields": [
  {
   "default": "1",
   "fieldname": "enabled",
   "fieldtype": "Check",
   "label": "Enabled"
  },
  {
   "default": "1",
   "description": "Day of month on which the monthly report is sent (1 - 28).",
   "fieldname": "send_day_of_month",
   "fieldtype": "Int",
   "label": "Send Day of Month",
   "reqd": 1
  },
  {
   "fieldname": "recipient_section",
   "fieldtype": "Section Break",
   "label": "Recipients"
  },
  {
   "description": "One email address per line.",
   "fieldname": "recipient_emails",
   "fieldtype": "Small Text",
   "label": "Recipient Emails"
  },
  {
   "fieldname": "status_section",
   "fieldtype": "Section Break",
   "label": "Last Run"
  },
  {
   "fieldname": "last_sent_date",
   "fieldtype": "Date",
   "label": "Last Sent Date",
   "read_only": 1
  },
  {
   "fieldname": "column_break_status",
   "fieldtype": "Column Break"
  },
  {
   "fieldname": "last_sent_status",
   "fieldtype": "Select",
   "label": "Last Sent Status",
   "options": "\nSuccess\nFailed\nSkipped (disabled)\nSkipped (wrong day)",
   "read_only": 1
  }
 ],
 "index_web_pages_for_search": 1,
 "issingle": 1,
 "links": [],
 "modified": "2026-04-20 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Dantata Town",
 "name": "Customer Payment Report Settings",
 "owner": "Administrator",
 "permissions": [
  {
   "create": 1,
   "delete": 1,
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "System Manager",
   "share": 1,
   "write": 1
  },
  {
   "email": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "Accounts Manager",
   "share": 1,
   "write": 1
  },
  {
   "email": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "Accounts User",
   "share": 1
  }
 ],
 "row_format": "Dynamic",
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
```

- [ ] **Step 3: Create the controller with `validate`**

File: `dantata_town/dantata_town/doctype/customer_payment_report_settings/customer_payment_report_settings.py`

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_address


class CustomerPaymentReportSettings(Document):
	def validate(self):
		if self.enabled and not (self.recipient_emails or "").strip():
			frappe.throw(_("Recipient Emails is required when Enabled is checked."))
		if self.send_day_of_month < 1 or self.send_day_of_month > 28:
			frappe.throw(_("Send Day of Month must be between 1 and 28."))
		for line in (self.recipient_emails or "").splitlines():
			line = line.strip()
			if line:
				validate_email_address(line, throw=True)
```

- [ ] **Step 4: Run migrate**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`
Expected: Clean migration.

- [ ] **Step 5: Verify Single registered**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com execute frappe.client.get_value --kwargs "{'doctype':'DocType','filters':{'name':'Customer Payment Report Settings'},'fieldname':['issingle','module']}"`
Expected: `{"issingle": 1, "module": "Dantata Town"}`.

- [ ] **Step 6: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/doctype/customer_payment_report_settings/
git commit -m "feat: add Customer Payment Report Settings single

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Settings validator tests

**Files:**
- Create: `dantata_town/dantata_town/tests/test_customer_payment_report.py`

- [ ] **Step 1: Write the test file**

File: `dantata_town/dantata_town/tests/test_customer_payment_report.py`

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestCustomerPaymentReport(FrappeTestCase):
	def _settings(self, **overrides):
		"""Load the single, apply overrides, return the doc."""
		doc = frappe.get_single("Customer Payment Report Settings")
		for k, v in overrides.items():
			doc.set(k, v)
		return doc

	def test_day_below_1_rejected(self):
		doc = self._settings(send_day_of_month=0, enabled=0)
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_day_above_28_rejected(self):
		doc = self._settings(send_day_of_month=29, enabled=0)
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_day_28_accepted(self):
		doc = self._settings(send_day_of_month=28, enabled=0, recipient_emails="")
		doc.save(ignore_permissions=True)  # no raise

	def test_enabled_without_recipients_rejected(self):
		doc = self._settings(enabled=1, send_day_of_month=1, recipient_emails="")
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_malformed_email_rejected(self):
		doc = self._settings(enabled=1, send_day_of_month=1, recipient_emails="not-an-email")
		with self.assertRaises(Exception):  # validate_email_address raises InvalidEmailAddressError
			doc.save(ignore_permissions=True)

	def test_multiple_valid_emails_accepted(self):
		doc = self._settings(
			enabled=1,
			send_day_of_month=1,
			recipient_emails="a@example.com\nb@example.com",
		)
		doc.save(ignore_permissions=True)
		# Reload to confirm persistence.
		doc = frappe.get_single("Customer Payment Report Settings")
		self.assertIn("a@example.com", doc.recipient_emails)
		self.assertIn("b@example.com", doc.recipient_emails)
```

- [ ] **Step 2: Run the tests**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_customer_payment_report`
Expected: All 6 tests PASS (validator from Task 1 already handles these cases).

- [ ] **Step 3: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/tests/test_customer_payment_report.py
git commit -m "test: cover Customer Payment Report Settings validator paths

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Aggregation helper

**Files:**
- Create: `dantata_town/dantata_town/reports.py`
- Modify: `dantata_town/dantata_town/tests/test_customer_payment_report.py`

- [ ] **Step 1: Add failing tests for the aggregation helper**

Append inside `TestCustomerPaymentReport` in `test_customer_payment_report.py`:

```python
	def test_aggregation_only_submitted_outstanding_invoices(self):
		from dantata_town.dantata_town.reports import build_customer_payment_report_rows
		rows = build_customer_payment_report_rows()
		invoice_names = {r["name"] for r in rows}

		# Every returned invoice must be submitted and have outstanding > 0.
		for inv in invoice_names:
			doc = frappe.db.get_value(
				"Sales Invoice", inv,
				["docstatus", "outstanding_amount"], as_dict=True,
			)
			self.assertEqual(doc.docstatus, 1)
			self.assertGreater(float(doc.outstanding_amount), 0)

		# No invoice with outstanding == 0 should appear.
		paid = frappe.get_all(
			"Sales Invoice",
			filters={"docstatus": 1, "outstanding_amount": 0},
			pluck="name",
		)
		self.assertTrue(invoice_names.isdisjoint(paid))

	def test_aggregation_property_fields_fallback_to_dash(self):
		"""For any returned row whose SO has no submitted AL, property fields = '—'."""
		from dantata_town.dantata_town.reports import build_customer_payment_report_rows
		rows = build_customer_payment_report_rows()
		for r in rows:
			so = frappe.db.get_value(
				"Sales Invoice Item",
				{"parent": r["name"], "sales_order": ("!=", "")},
				"sales_order",
			)
			has_al = so and frappe.db.exists(
				"Allocation Letter", {"sales_order": so, "docstatus": 1}
			)
			if not has_al:
				self.assertEqual(r["property_type"], "—")
				self.assertEqual(r["property_description"], "—")
				self.assertEqual(r["plot_number"], "—")

	def test_aggregation_property_fields_match_linked_al(self):
		"""For any returned row whose SO has a submitted AL, property fields match
		the AL's values (positive path)."""
		from dantata_town.dantata_town.reports import build_customer_payment_report_rows
		rows = build_customer_payment_report_rows()
		tested_any = False
		for r in rows:
			so = frappe.db.get_value(
				"Sales Invoice Item",
				{"parent": r["name"], "sales_order": ("!=", "")},
				"sales_order",
			)
			if not so:
				continue
			al_name = frappe.db.get_value(
				"Allocation Letter",
				{"sales_order": so, "docstatus": 1},
				"name",
				order_by="letter_date desc",
			)
			if not al_name:
				continue
			al = frappe.db.get_value(
				"Allocation Letter", al_name,
				["property_type", "property_description", "plot_number"],
				as_dict=True,
			)
			self.assertEqual(r["property_type"], al.property_type or "—")
			self.assertEqual(r["property_description"], al.property_description or "—")
			self.assertEqual(r["plot_number"], al.plot_number or "—")
			tested_any = True
		if not tested_any:
			self.skipTest("No outstanding SI → SO → submitted AL path present on this site")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_customer_payment_report`
Expected: `ImportError: cannot import name 'build_customer_payment_report_rows' from 'dantata_town.dantata_town.reports'` — the module doesn't exist yet.

- [ ] **Step 3: Create the reports module**

File: `dantata_town/dantata_town/reports.py`

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _


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

- [ ] **Step 4: Re-run tests**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_customer_payment_report`
Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/reports.py dantata_town/dantata_town/tests/test_customer_payment_report.py
git commit -m "feat: build_customer_payment_report_rows joins SI to Allocation Letter

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Email template + `_send_report_email` + `_record_status`

**Files:**
- Modify: `dantata_town/dantata_town/reports.py`

- [ ] **Step 1: Add the email template and helpers**

Append to `dantata_town/dantata_town/reports.py`:

```python
_EMAIL_TEMPLATE = """
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
"""


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

- [ ] **Step 2: No tests yet — these are private helpers exercised via Task 5**

The tests for `_send_report_email` and `_record_status` are covered indirectly through the scheduled entry point tests in Task 5.

- [ ] **Step 3: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/reports.py
git commit -m "feat: add email template plus _send_report_email and _record_status helpers

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Scheduled entry point `send_monthly_customer_payment_report` — TDD

**Files:**
- Modify: `dantata_town/dantata_town/reports.py`
- Modify: `dantata_town/dantata_town/tests/test_customer_payment_report.py`

- [ ] **Step 1: Add failing tests**

Append inside `TestCustomerPaymentReport`:

```python
	def _reset_settings(self, enabled=1, day=1, emails="a@example.com", last_sent_date=None, last_sent_status=None):
		"""Reset the single to a known baseline."""
		doc = frappe.get_single("Customer Payment Report Settings")
		doc.enabled = enabled
		doc.send_day_of_month = day
		doc.recipient_emails = emails
		doc.last_sent_date = last_sent_date
		doc.last_sent_status = last_sent_status
		doc.save(ignore_permissions=True)

	def _count_queued_emails(self, subject_substring):
		return frappe.db.count(
			"Email Queue",
			{"message": ("like", f"%{subject_substring}%")},
		)

	def test_scheduled_disabled_skips(self):
		from dantata_town.dantata_town.reports import send_monthly_customer_payment_report
		self._reset_settings(enabled=0)
		before = self._count_queued_emails("Monthly Customer Payment Report")
		send_monthly_customer_payment_report()
		after = self._count_queued_emails("Monthly Customer Payment Report")
		self.assertEqual(after, before)
		doc = frappe.get_single("Customer Payment Report Settings")
		self.assertEqual(doc.last_sent_status, "Skipped (disabled)")

	def test_scheduled_wrong_day_skips(self):
		from dantata_town.dantata_town.reports import send_monthly_customer_payment_report
		today = frappe.utils.getdate()
		other_day = 28 if today.day != 28 else 27
		self._reset_settings(enabled=1, day=other_day)
		before = self._count_queued_emails("Monthly Customer Payment Report")
		send_monthly_customer_payment_report()
		after = self._count_queued_emails("Monthly Customer Payment Report")
		self.assertEqual(after, before)
		doc = frappe.get_single("Customer Payment Report Settings")
		self.assertEqual(doc.last_sent_status, "Skipped (wrong day)")

	def test_scheduled_right_day_sends(self):
		from dantata_town.dantata_town.reports import send_monthly_customer_payment_report
		today = frappe.utils.getdate()
		self._reset_settings(enabled=1, day=today.day, last_sent_date=None)
		before = self._count_queued_emails("Monthly Customer Payment Report")
		send_monthly_customer_payment_report()
		after = self._count_queued_emails("Monthly Customer Payment Report")
		self.assertEqual(after, before + 1)
		doc = frappe.get_single("Customer Payment Report Settings")
		self.assertEqual(doc.last_sent_status, "Success")
		self.assertEqual(frappe.utils.getdate(doc.last_sent_date), today)

	def test_scheduled_double_send_guard(self):
		from dantata_town.dantata_town.reports import send_monthly_customer_payment_report
		today = frappe.utils.getdate()
		self._reset_settings(enabled=1, day=today.day, last_sent_date=today)
		before = self._count_queued_emails("Monthly Customer Payment Report")
		send_monthly_customer_payment_report()
		after = self._count_queued_emails("Monthly Customer Payment Report")
		self.assertEqual(after, before)  # no new email
		doc = frappe.get_single("Customer Payment Report Settings")
		self.assertEqual(doc.last_sent_status, "Success")

	def test_scheduled_empty_rows_still_sends(self):
		"""When there are no outstanding invoices, the email still goes out with
		the empty-state body so silence doesn't mask a silent failure."""
		from dantata_town.dantata_town import reports
		from dantata_town.dantata_town.reports import send_monthly_customer_payment_report
		today = frappe.utils.getdate()
		self._reset_settings(enabled=1, day=today.day, last_sent_date=None)

		original = reports.build_customer_payment_report_rows
		reports.build_customer_payment_report_rows = lambda: []
		try:
			before = self._count_queued_emails("Monthly Customer Payment Report")
			send_monthly_customer_payment_report()
			after = self._count_queued_emails("Monthly Customer Payment Report")
			self.assertEqual(after, before + 1)
		finally:
			reports.build_customer_payment_report_rows = original

		recent = frappe.get_all(
			"Email Queue",
			filters={"message": ("like", "%No outstanding balances this month%")},
			pluck="name",
		)
		self.assertGreaterEqual(len(recent), 1)
		doc = frappe.get_single("Customer Payment Report Settings")
		self.assertEqual(doc.last_sent_status, "Success")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_customer_payment_report`
Expected: 5 new tests FAIL with `ImportError: cannot import name 'send_monthly_customer_payment_report'`.

- [ ] **Step 3: Implement the scheduled entry point**

Append to `dantata_town/dantata_town/reports.py`:

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
	# Double-send guard: the scheduler may retry within the same day.
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

- [ ] **Step 4: Re-run tests**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_customer_payment_report`
Expected: All 14 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/reports.py dantata_town/dantata_town/tests/test_customer_payment_report.py
git commit -m "feat: scheduled send_monthly_customer_payment_report with disabled/wrong-day/double-send guards

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Manual `send_report_now` — TDD

**Files:**
- Modify: `dantata_town/dantata_town/reports.py`
- Modify: `dantata_town/dantata_town/tests/test_customer_payment_report.py`

- [ ] **Step 1: Add failing tests**

Append inside `TestCustomerPaymentReport`:

```python
	def test_send_report_now_disabled_rejected(self):
		from dantata_town.dantata_town.reports import send_report_now
		self._reset_settings(enabled=0)
		with self.assertRaises(frappe.ValidationError):
			send_report_now()

	def test_send_report_now_sends_regardless_of_day(self):
		"""Send Now bypasses day/last-sent checks."""
		from dantata_town.dantata_town.reports import send_report_now
		today = frappe.utils.getdate()
		other_day = 28 if today.day != 28 else 27
		self._reset_settings(enabled=1, day=other_day, last_sent_date=today)
		before = self._count_queued_emails("Monthly Customer Payment Report")
		send_report_now()
		after = self._count_queued_emails("Monthly Customer Payment Report")
		self.assertEqual(after, before + 1)
		doc = frappe.get_single("Customer Payment Report Settings")
		self.assertEqual(doc.last_sent_status, "Success")

	def test_send_report_now_requires_privileged_role(self):
		"""Accounts User lacks permission; System Manager / Accounts Manager do."""
		from dantata_town.dantata_town.reports import send_report_now
		self._reset_settings(enabled=1, day=1)

		# Find or create an Accounts User with none of the privileged roles.
		test_user_email = "cpr_accounts_user@example.com"
		if not frappe.db.exists("User", test_user_email):
			user = frappe.get_doc({
				"doctype": "User",
				"email": test_user_email,
				"first_name": "CPR",
				"last_name": "Accounts User",
				"enabled": 1,
				"roles": [{"role": "Accounts User"}],
				"send_welcome_email": 0,
			})
			user.insert(ignore_permissions=True)

		original_user = frappe.session.user
		frappe.set_user(test_user_email)
		try:
			with self.assertRaises(frappe.PermissionError):
				send_report_now()
		finally:
			frappe.set_user(original_user)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_customer_payment_report`
Expected: ImportError on `send_report_now`.

- [ ] **Step 3: Implement `send_report_now`**

Append to `dantata_town/dantata_town/reports.py`:

```python
@frappe.whitelist()
def send_report_now():
	"""Manual trigger from the Settings Single toolbar — sends immediately."""
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

- [ ] **Step 4: Re-run tests**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_customer_payment_report`
Expected: All 17 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/reports.py dantata_town/dantata_town/tests/test_customer_payment_report.py
git commit -m "feat: send_report_now whitelisted manual trigger bypassing day checks

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Script Report `Customer Payment Report`

**Files:**
- Create: `dantata_town/dantata_town/report/__init__.py` (if missing)
- Create: `dantata_town/dantata_town/report/customer_payment_report/__init__.py`
- Create: `dantata_town/dantata_town/report/customer_payment_report/customer_payment_report.json`
- Create: `dantata_town/dantata_town/report/customer_payment_report/customer_payment_report.py`
- Create: `dantata_town/dantata_town/report/customer_payment_report/customer_payment_report.js`
- Modify: `dantata_town/dantata_town/tests/test_customer_payment_report.py`

- [ ] **Step 1: Add failing test for Script Report shape**

Append inside `TestCustomerPaymentReport`:

```python
	def test_script_report_execute_shape(self):
		from dantata_town.dantata_town.report.customer_payment_report.customer_payment_report import execute
		columns, data = execute(filters=None)
		self.assertEqual(len(columns), 9)
		expected_fieldnames = [
			"customer", "customer_name", "name", "posting_date", "due_date",
			"outstanding_amount", "property_type", "property_description", "plot_number",
		]
		self.assertEqual([c["fieldname"] for c in columns], expected_fieldnames)
		# Data shape matches the aggregation helper's output.
		from dantata_town.dantata_town.reports import build_customer_payment_report_rows
		self.assertEqual(data, build_customer_payment_report_rows())
```

- [ ] **Step 2: Create package markers**

Check if `dantata_town/dantata_town/report/` exists. If not, create `dantata_town/dantata_town/report/__init__.py` (empty file).

Create `dantata_town/dantata_town/report/customer_payment_report/__init__.py` (empty file).

- [ ] **Step 3: Create the Script Report metadata JSON**

File: `dantata_town/dantata_town/report/customer_payment_report/customer_payment_report.json`

```json
{
 "add_total_row": 0,
 "creation": "2026-04-20 00:00:00.000000",
 "disabled": 0,
 "docstatus": 0,
 "doctype": "Report",
 "idx": 0,
 "is_standard": "Yes",
 "modified": "2026-04-20 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Dantata Town",
 "name": "Customer Payment Report",
 "owner": "Administrator",
 "ref_doctype": "Sales Invoice",
 "report_name": "Customer Payment Report",
 "report_type": "Script Report",
 "roles": [
  {"role": "System Manager"},
  {"role": "Accounts Manager"},
  {"role": "Accounts User"}
 ]
}
```

- [ ] **Step 4: Create the execute module**

File: `dantata_town/dantata_town/report/customer_payment_report/customer_payment_report.py`

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

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
		{"label": "Due Date", "fieldname": "due_date",
		 "fieldtype": "Date", "width": 110},
		{"label": "Outstanding", "fieldname": "outstanding_amount",
		 "fieldtype": "Currency", "width": 140},
		{"label": "Property Type", "fieldname": "property_type",
		 "fieldtype": "Data", "width": 130},
		{"label": "Description", "fieldname": "property_description",
		 "fieldtype": "Data", "width": 260},
		{"label": "Plot", "fieldname": "plot_number",
		 "fieldtype": "Data", "width": 100},
	]
	return columns, build_customer_payment_report_rows()
```

- [ ] **Step 5: Create the empty filter JS shell**

File: `dantata_town/dantata_town/report/customer_payment_report/customer_payment_report.js`

```javascript
frappe.query_reports["Customer Payment Report"] = {
	filters: [],
};
```

- [ ] **Step 6: Run migrate so the Report record registers**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`
Expected: Clean migration.

- [ ] **Step 7: Run tests**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_customer_payment_report`
Expected: All 18 tests PASS.

- [ ] **Step 8: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/report/
git commit -m "feat: Customer Payment Report Script Report reusing the shared aggregation

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Client script (Send Now button) + hooks wiring

**Files:**
- Create: `dantata_town/public/js/customer_payment_report_settings.js`
- Modify: `dantata_town/hooks.py`

- [ ] **Step 1: Write the client script**

File: `dantata_town/public/js/customer_payment_report_settings.js`

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

- [ ] **Step 2: Wire `doctype_js` + `scheduler_events` in `hooks.py`**

In `dantata_town/hooks.py`:

- Add `"Customer Payment Report Settings": "public/js/customer_payment_report_settings.js"` to the `doctype_js` dict.
- Add a new `scheduler_events` dict (currently commented out in the template) with the daily entry. Find the commented block starting with `# scheduler_events = {` and replace it with an active block:

```python
scheduler_events = {
	"daily": [
		"dantata_town.dantata_town.reports.send_monthly_customer_payment_report",
	],
}
```

- [ ] **Step 3: Build assets**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench build --app dantata_town`
Expected: Build completes cleanly.

- [ ] **Step 4: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/public/js/customer_payment_report_settings.js dantata_town/hooks.py
git commit -m "feat: Send Now button on settings + daily scheduler wiring

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Final migrate + full test run + smoke

**Files:** none (verification)

- [ ] **Step 1: Full migrate**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`
Expected: Clean.

- [ ] **Step 2: Run all three test modules**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_customer_payment_report`
Expected: 18 tests PASS.

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_quotation_installments`
Expected: 14 tests PASS.

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`
Expected: 9 tests PASS.

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_project_type_setup`
Expected: 7 tests PASS.

- [ ] **Step 3: Rebuild assets**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com clear-cache && bench build --app dantata_town`
Expected: Both commands clean.

- [ ] **Step 4: Manual UI smoke test (reported, not executed)**

As a user with System Manager or Accounts Manager role:

1. Navigate to `/app/customer-payment-report-settings`. Set `enabled = 1`, `send_day_of_month = today.day`, `recipient_emails` = your test inbox (one per line).
2. Save — verify success; status fields remain blank.
3. Click `Send Now` → confirm → expect toast `Report sent`.
4. Inspect your inbox: email with subject `Monthly Customer Payment Report — <Month> <Year>`, HTML table of outstanding SIs, total at bottom.
5. Save with `send_day_of_month = 0` → blocked with "must be between 1 and 28".
6. Save with `recipient_emails = "not-an-email"` → blocked with the email-validation error.
7. Navigate to `/app/query-report/Customer Payment Report` → sortable table with the same data. Export via toolbar — Excel file downloads.
8. Uncheck `enabled`, save. Click `Send Now` → "Enable the report before sending."
9. Re-enable, leave it. Next time the scheduler fires on the configured day, the email will go out (or be skipped if wrong day / already sent today).

- [ ] **Step 5: No additional commit unless a manual-test follow-up fix is required.**
