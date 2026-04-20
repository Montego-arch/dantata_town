# Quotation Installments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a simplified deposit + monthly installment generator on top of ERPNext's native `payment_schedule` feature on Quotation, with flow-through into the Allocation Letter.

**Architecture:** Four custom fields on Quotation (`payment_type`, `installment_deposit_amount`, `installment_start_date`, `installment_months`) installed via `setup.py`. A whitelisted generator in `dantata_town/dantata_town/quotation.py` writes 1 deposit row + N monthly rows into the existing `payment_schedule` child table; the last row absorbs rounding drift. A Quotation client script adds the `Generate Installment Schedule` button. `make_allocation_letter` is extended to copy SO.payment_schedule rows into AL.installment_schedule.

**Tech Stack:** Frappe Framework, ERPNext (Quotation + Sales Order + Payment Schedule), Python 3, JavaScript form scripts, `FrappeTestCase`.

**Spec:** `docs/superpowers/specs/2026-04-20-quotation-installments-design.md`

**Working directory:** `/home/okeke/clients/graceco/frappe-bench/apps/dantata_town`

**Test command (Quotation module):** `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_quotation_installments`

**Test command (AL module):** `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`

**Migrate command:** `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`

---

## File Structure

**Files created:**

| Path | Responsibility |
|---|---|
| `dantata_town/dantata_town/quotation.py` | `generate_installment_schedule` whitelisted method + `validate_quotation_payment_type` doc hook + private `_validate_installment_inputs` |
| `dantata_town/public/js/quotation.js` | Quotation form script: Generate button + Outright-clears-fields on toggle |
| `dantata_town/dantata_town/tests/test_quotation_installments.py` | Unit tests for custom-field install, validators, generator, rounding, idempotency |

**Files modified:**

| Path | Change |
|---|---|
| `dantata_town/dantata_town/setup.py` | Add 4 installment custom fields + 2 layout breaks under a `Quotation` key in `_create_custom_fields()` |
| `dantata_town/hooks.py` | Add Quotation entries to `doc_events` and `doctype_js` |
| `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py` | Extend `make_allocation_letter` to map `sales_order.payment_schedule` into `allocation_letter.installment_schedule` |
| `dantata_town/dantata_town/tests/test_allocation_letter.py` | Add test for the AL integration path |

---

## Task 1: Install Quotation installment custom fields

**Files:**
- Modify: `dantata_town/dantata_town/setup.py`
- Create: `dantata_town/dantata_town/tests/test_quotation_installments.py`

- [ ] **Step 1: Write the failing test**

File: `dantata_town/dantata_town/tests/test_quotation_installments.py`

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from dantata_town.dantata_town.setup import create_boq_custom_fields


class TestQuotationInstallments(FrappeTestCase):
	def test_custom_fields_installed(self):
		create_boq_custom_fields()

		expected = {
			"payment_type": {"fieldtype": "Select", "options": "\nInstallment\nOutright"},
			"installment_start_date": {"fieldtype": "Date"},
			"installment_deposit_amount": {"fieldtype": "Currency"},
			"installment_months": {"fieldtype": "Int"},
		}

		for fieldname, props in expected.items():
			field = frappe.db.get_value(
				"Custom Field",
				{"dt": "Quotation", "fieldname": fieldname},
				["fieldtype", "options", "depends_on"],
				as_dict=True,
			)
			self.assertIsNotNone(
				field,
				f"Custom Field {fieldname} not found on Quotation",
			)
			self.assertEqual(field.fieldtype, props["fieldtype"])
			if "options" in props:
				self.assertEqual(field.options, props["options"])
			if fieldname != "payment_type":
				self.assertEqual(field.depends_on, "eval:doc.payment_type === 'Installment'")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_quotation_installments`
Expected: FAIL — fields don't exist yet.

- [ ] **Step 3: Add Quotation entries to `_create_custom_fields()` in setup.py**

In `dantata_town/dantata_town/setup.py`, inside `_create_custom_fields()`'s `custom_fields` dict, add a new `"Quotation"` key after the existing `"Project"` entry:

```python
		"Quotation": [
			{
				"fieldname": "dt_installment_section",
				"fieldtype": "Section Break",
				"label": "Payment Type",
				"insert_after": "terms_tab",
				"module": "Dantata Town",
			},
			{
				"fieldname": "payment_type",
				"fieldtype": "Select",
				"label": "Payment Type",
				"options": "\nInstallment\nOutright",
				"reqd": 1,
				"insert_after": "dt_installment_section",
				"module": "Dantata Town",
			},
			{
				"fieldname": "installment_column_break",
				"fieldtype": "Column Break",
				"insert_after": "payment_type",
				"module": "Dantata Town",
			},
			{
				"fieldname": "installment_start_date",
				"fieldtype": "Date",
				"label": "Installment Start Date",
				"insert_after": "installment_column_break",
				"depends_on": "eval:doc.payment_type === 'Installment'",
				"mandatory_depends_on": "eval:doc.payment_type === 'Installment'",
				"module": "Dantata Town",
			},
			{
				"fieldname": "installment_deposit_amount",
				"fieldtype": "Currency",
				"label": "Installment Deposit Amount",
				"insert_after": "installment_start_date",
				"depends_on": "eval:doc.payment_type === 'Installment'",
				"mandatory_depends_on": "eval:doc.payment_type === 'Installment'",
				"module": "Dantata Town",
			},
			{
				"fieldname": "installment_months",
				"fieldtype": "Int",
				"label": "Installment Months",
				"insert_after": "installment_deposit_amount",
				"depends_on": "eval:doc.payment_type === 'Installment'",
				"mandatory_depends_on": "eval:doc.payment_type === 'Installment'",
				"module": "Dantata Town",
			},
		],
```

- [ ] **Step 4: Run migrate so custom fields are created**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`
Expected: Clean migration.

- [ ] **Step 5: Re-run the test**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_quotation_installments`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/setup.py dantata_town/dantata_town/tests/test_quotation_installments.py
git commit -m "feat: add Quotation installment custom fields"
```

---

## Task 2: `validate_quotation_payment_type` doc hook

**Files:**
- Create: `dantata_town/dantata_town/quotation.py`
- Modify: `dantata_town/hooks.py`
- Modify: `dantata_town/dantata_town/tests/test_quotation_installments.py`

- [ ] **Step 1: Add failing tests for the validator**

Append inside `TestQuotationInstallments` class in `test_quotation_installments.py`:

```python
	def _new_quotation(self, **overrides):
		"""Helper: build a draft Quotation in memory with sensible defaults."""
		defaults = {
			"doctype": "Quotation",
			"quotation_to": "Customer",
			"party_name": frappe.db.get_value("Customer", {}, "name"),
			"currency": "NGN",
			"conversion_rate": 1,
			"selling_price_list": frappe.db.get_value("Price List", {"selling": 1}, "name"),
			"items": [{
				"item_code": frappe.db.get_value("Item", {"disabled": 0}, "name"),
				"qty": 1,
				"rate": 50000,
			}],
			"payment_type": "Installment",
			"installment_deposit_amount": 10000,
			"installment_start_date": frappe.utils.today(),
			"installment_months": 4,
		}
		defaults.update(overrides)
		return frappe.get_doc(defaults)

	def test_outright_clears_installment_fields(self):
		create_boq_custom_fields()
		doc = self._new_quotation(payment_type="Outright")
		doc.insert(ignore_permissions=True)
		doc.reload()
		self.assertIn(doc.installment_deposit_amount, (0, None))
		self.assertIn(doc.installment_start_date, (None, ""))
		self.assertIn(doc.installment_months, (0, None))

	def test_installment_draft_save_permissive(self):
		"""Draft saves are permissive — user is still filling in fields."""
		create_boq_custom_fields()
		doc = self._new_quotation(installment_deposit_amount=0)
		doc.insert(ignore_permissions=True)  # Should not raise
		self.assertTrue(doc.name)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_quotation_installments`
Expected: Both new tests FAIL — validator is not wired up, Outright fields not cleared.

- [ ] **Step 3: Create the quotation module**

File: `dantata_town/dantata_town/quotation.py`

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

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
		# Drafts are permissive so users can fill in gradually;
		# submit-time triggers a strict check.
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

- [ ] **Step 4: Wire into `hooks.py`**

In `dantata_town/hooks.py`, add a `Quotation` entry to the existing `doc_events` dict, alongside the existing `Project`, `Purchase Receipt`, `Stock Entry` entries:

```python
	"Quotation": {
		"validate": "dantata_town.dantata_town.quotation.validate_quotation_payment_type",
	},
```

- [ ] **Step 5: Re-run tests**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_quotation_installments`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/quotation.py dantata_town/hooks.py dantata_town/dantata_town/tests/test_quotation_installments.py
git commit -m "feat: validate_quotation_payment_type clears Outright and validates Installment on submit"
```

---

## Task 3: Installment submit strictness

**Files:**
- Modify: `dantata_town/dantata_town/tests/test_quotation_installments.py`

- [ ] **Step 1: Add the failing submit tests**

Append inside `TestQuotationInstallments`:

```python
	def test_installment_submit_requires_deposit(self):
		create_boq_custom_fields()
		doc = self._new_quotation(installment_deposit_amount=0)
		doc.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_installment_submit_requires_start_date(self):
		create_boq_custom_fields()
		doc = self._new_quotation(installment_start_date=None)
		doc.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_installment_submit_requires_months(self):
		create_boq_custom_fields()
		doc = self._new_quotation(installment_months=0)
		doc.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_installment_submit_rejects_deposit_ge_total(self):
		create_boq_custom_fields()
		doc = self._new_quotation(installment_deposit_amount=60000)  # total is 50000
		doc.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			doc.submit()
```

- [ ] **Step 2: Run tests**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_quotation_installments`
Expected: all 4 new tests PASS (the validator from Task 2 already handles submit correctly).

- [ ] **Step 3: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/tests/test_quotation_installments.py
git commit -m "test: cover installment submit validation paths"
```

---

## Task 4: `generate_installment_schedule` — row count and sum

**Files:**
- Modify: `dantata_town/dantata_town/tests/test_quotation_installments.py`

- [ ] **Step 1: Add failing tests**

Append inside `TestQuotationInstallments`:

```python
	def test_generate_produces_n_plus_1_rows(self):
		create_boq_custom_fields()
		doc = self._new_quotation()
		doc.insert(ignore_permissions=True)

		from dantata_town.dantata_town.quotation import generate_installment_schedule
		generate_installment_schedule(doc.name)
		doc.reload()

		self.assertEqual(len(doc.payment_schedule), 5)  # 1 deposit + 4 monthly
		self.assertEqual(flt(doc.payment_schedule[0].payment_amount), 10000)
		for i in range(1, 5):
			self.assertGreater(flt(doc.payment_schedule[i].payment_amount), 0)

	def test_generate_sum_equals_grand_total(self):
		create_boq_custom_fields()
		doc = self._new_quotation()
		doc.insert(ignore_permissions=True)

		from dantata_town.dantata_town.quotation import generate_installment_schedule
		generate_installment_schedule(doc.name)
		doc.reload()

		total = sum(flt(row.payment_amount) for row in doc.payment_schedule)
		self.assertEqual(total, flt(doc.grand_total))
```

Also add this import at the top of the test file (above `class TestQuotationInstallments`):

```python
from frappe.utils import flt
```

- [ ] **Step 2: Run tests**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_quotation_installments`
Expected: Both new tests PASS (generator was already written in Task 2).

- [ ] **Step 3: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/tests/test_quotation_installments.py
git commit -m "test: generator produces N+1 rows summing to grand total"
```

---

## Task 5: Generator — rounding drift and due dates

**Files:**
- Modify: `dantata_town/dantata_town/tests/test_quotation_installments.py`

- [ ] **Step 1: Add the failing tests**

Append inside `TestQuotationInstallments`:

```python
	def test_generate_last_row_absorbs_rounding_drift(self):
		"""deposit=10000, total=40001, months=3 → balance=30001, per_month=10000.33,
		last row = 10000.34 (absorbs the 0.01 drift)."""
		create_boq_custom_fields()
		# Use rate=40001 to force non-even division.
		doc = self._new_quotation(
			items=[{
				"item_code": frappe.db.get_value("Item", {"disabled": 0}, "name"),
				"qty": 1,
				"rate": 40001,
			}],
			installment_deposit_amount=10000,
			installment_months=3,
		)
		doc.insert(ignore_permissions=True)

		from dantata_town.dantata_town.quotation import generate_installment_schedule
		generate_installment_schedule(doc.name)
		doc.reload()

		# Rows 1 and 2 should be equal; row 3 (last) should differ by the rounding drift.
		self.assertEqual(flt(doc.payment_schedule[1].payment_amount), 10000.33)
		self.assertEqual(flt(doc.payment_schedule[2].payment_amount), 10000.33)
		self.assertEqual(flt(doc.payment_schedule[3].payment_amount), 10000.34)
		# Sum still equals grand_total.
		total = sum(flt(row.payment_amount) for row in doc.payment_schedule)
		self.assertEqual(total, flt(doc.grand_total))

	def test_generate_due_dates_step_monthly_with_add_months(self):
		"""start=2026-01-31, months=2. First monthly row due end of Feb, second end of Mar."""
		create_boq_custom_fields()
		doc = self._new_quotation(
			installment_start_date="2026-01-31",
			installment_months=2,
		)
		doc.insert(ignore_permissions=True)

		from dantata_town.dantata_town.quotation import generate_installment_schedule
		generate_installment_schedule(doc.name)
		doc.reload()

		# Deposit row: exact start date.
		self.assertEqual(str(doc.payment_schedule[0].due_date), "2026-01-31")
		# First monthly: Feb's last day (28 in 2026, non-leap).
		self.assertEqual(str(doc.payment_schedule[1].due_date), "2026-02-28")
		# Second monthly: March's 31st.
		self.assertEqual(str(doc.payment_schedule[2].due_date), "2026-03-31")
```

- [ ] **Step 2: Run tests**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_quotation_installments`
Expected: Both tests PASS (generator already implements this).

- [ ] **Step 3: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/tests/test_quotation_installments.py
git commit -m "test: last row absorbs rounding drift; add_months handles month-end"
```

---

## Task 6: Generator — rejection cases and idempotency

**Files:**
- Modify: `dantata_town/dantata_town/tests/test_quotation_installments.py`

- [ ] **Step 1: Add the failing tests**

Append inside `TestQuotationInstallments`:

```python
	def test_generate_rejects_deposit_ge_total(self):
		create_boq_custom_fields()
		doc = self._new_quotation(installment_deposit_amount=60000)  # total=50000
		doc.insert(ignore_permissions=True)

		from dantata_town.dantata_town.quotation import generate_installment_schedule
		with self.assertRaises(frappe.ValidationError):
			generate_installment_schedule(doc.name)

	def test_generate_rejects_months_below_1(self):
		create_boq_custom_fields()
		doc = self._new_quotation(installment_months=0)
		doc.insert(ignore_permissions=True)

		from dantata_town.dantata_town.quotation import generate_installment_schedule
		with self.assertRaises(frappe.ValidationError):
			generate_installment_schedule(doc.name)

	def test_generate_is_idempotent(self):
		"""Running twice produces the same row count and amounts — no accumulation."""
		create_boq_custom_fields()
		doc = self._new_quotation()
		doc.insert(ignore_permissions=True)

		from dantata_town.dantata_town.quotation import generate_installment_schedule
		generate_installment_schedule(doc.name)
		doc.reload()
		first_rows = [(r.payment_amount, r.due_date) for r in doc.payment_schedule]

		generate_installment_schedule(doc.name)
		doc.reload()
		second_rows = [(r.payment_amount, r.due_date) for r in doc.payment_schedule]

		self.assertEqual(first_rows, second_rows)
		self.assertEqual(len(doc.payment_schedule), 5)
```

- [ ] **Step 2: Run tests**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_quotation_installments`
Expected: All 3 new tests PASS.

- [ ] **Step 3: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/tests/test_quotation_installments.py
git commit -m "test: generator rejects invalid inputs and is idempotent"
```

---

## Task 7: Quotation client script — Generate button + Outright toggle

**Files:**
- Create: `dantata_town/public/js/quotation.js`
- Modify: `dantata_town/hooks.py`

- [ ] **Step 1: Write the client script**

File: `dantata_town/public/js/quotation.js`

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

- [ ] **Step 2: Wire into `hooks.py`**

In `dantata_town/hooks.py`, find the `doctype_js` dict and add a Quotation entry alongside the existing Project / Sales Order / Allocation Letter entries:

```python
	"Quotation": "public/js/quotation.js",
```

- [ ] **Step 3: Build assets**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench build --app dantata_town`
Expected: Build completes cleanly.

- [ ] **Step 4: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/public/js/quotation.js dantata_town/hooks.py
git commit -m "feat: Quotation form script — Generate Installment Schedule button"
```

---

## Task 8: Extend `make_allocation_letter` to copy payment_schedule into AL

**Files:**
- Modify: `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py`
- Modify: `dantata_town/dantata_town/tests/test_allocation_letter.py`

- [ ] **Step 1: Add the failing test**

Append inside `TestAllocationLetter` in `dantata_town/dantata_town/tests/test_allocation_letter.py`:

```python
	def test_make_allocation_letter_copies_payment_schedule(self):
		"""When the source Sales Order has payment_schedule rows, they map into
		the target AL's installment_schedule as First / Second / Third / Fourth /
		Installment 5 labels."""
		_ensure_terms()
		from dantata_town.dantata_town.doctype.allocation_letter.allocation_letter import (
			make_allocation_letter,
		)

		# Find a submitted SO that has payment_schedule rows; skip if none.
		so_name = None
		for so in frappe.get_all(
			"Sales Order",
			filters={"docstatus": 1},
			fields=["name"],
		):
			if frappe.db.count("Payment Schedule", {"parent": so.name}) > 0:
				so_name = so.name
				break
		if not so_name:
			self.skipTest("No submitted Sales Order with payment_schedule on this site")

		target = make_allocation_letter(so_name)
		self.assertGreater(len(target.installment_schedule), 0)

		so_rows = frappe.get_all(
			"Payment Schedule",
			filters={"parent": so_name},
			fields=["payment_amount", "due_date"],
			order_by="idx asc",
		)
		self.assertEqual(len(target.installment_schedule), len(so_rows))

		ordinal_labels = ["First", "Second", "Third", "Fourth"]
		for i, (al_row, so_row) in enumerate(zip(target.installment_schedule, so_rows)):
			expected_label = ordinal_labels[i] if i < len(ordinal_labels) else f"Installment {i + 1}"
			self.assertEqual(al_row.sequence_label, expected_label)
			self.assertEqual(flt(al_row.amount), flt(so_row.payment_amount))
			self.assertEqual(str(al_row.due_date), str(so_row.due_date))
```

Also ensure `flt` is imported at the top of `test_allocation_letter.py`:

```python
from frappe.utils import flt
```

- [ ] **Step 2: Run test — expect failure**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`
Expected: the new test FAILS (or skips if there's no SO with payment_schedule yet). If it runs, it fails because `make_allocation_letter` does not yet copy rows.

- [ ] **Step 3: Extend `make_allocation_letter` in `allocation_letter.py`**

In `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py`, above the `make_allocation_letter` definition, add the helper:

```python
_ORDINAL_LABELS = ["First", "Second", "Third", "Fourth"]


def _label_for(idx):
	"""Map a 0-based row index to a human label."""
	if idx < len(_ORDINAL_LABELS):
		return _ORDINAL_LABELS[idx]
	return "Installment {0}".format(idx + 1)
```

Then modify `set_defaults` inside `make_allocation_letter` to also populate the installment_schedule. Replace the entire `set_defaults` function body with:

```python
	def set_defaults(source, target):
		from frappe.contacts.doctype.address.address import get_default_address

		target.letter_date = today()
		target.addressee_name = source.customer_name
		primary_addr = get_default_address("Customer", source.customer)
		if primary_addr:
			addr = frappe.get_doc("Address", primary_addr)
			lines = [addr.address_line1, addr.address_line2, addr.city, addr.country]
			target.addressee_address = "\n".join([l for l in lines if l])

		terms = frappe.get_single("Allocation Letter Terms")
		if terms.default_chairman_name:
			target.chairman_name = terms.default_chairman_name
		target.company_name = terms.default_company_name or "Dantata Town Developers Ltd"

		if source.get("payment_schedule"):
			target.purchase_price_option = "Installment"
			target.installment_schedule = []
			for idx, row in enumerate(source.payment_schedule):
				target.append("installment_schedule", {
					"sequence_label": _label_for(idx),
					"amount": row.payment_amount,
					"due_date": row.due_date,
				})
```

- [ ] **Step 4: Re-run the AL test suite**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`
Expected: All AL tests including the new one PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py dantata_town/dantata_town/tests/test_allocation_letter.py
git commit -m "feat: make_allocation_letter maps Sales Order payment_schedule into AL installment_schedule"
```

---

## Task 9: Full migrate + tests + smoke check

**Files:** none (verification)

- [ ] **Step 1: Full migrate**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`
Expected: Clean output ending with `Queued rebuilding of search index`.

- [ ] **Step 2: Run both test modules**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_quotation_installments`
Expected: All tests PASS.

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`
Expected: All tests PASS.

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_project_type_setup`
Expected: All tests PASS.

- [ ] **Step 3: Rebuild assets**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com clear-cache && bench build --app dantata_town`
Expected: Both commands clean.

- [ ] **Step 4: Manual UI smoke test (reported, not executed here)**

As a user with Sales Manager permissions:

1. Open a draft Quotation, add items, save → `grand_total` populates.
2. In the Terms tab, find the new `Payment Type` field. Pick `Installment` — `Installment Start Date`, `Installment Deposit Amount`, `Installment Months` appear as required.
3. Fill them (e.g. start today, deposit 10000, months 4) on a Quotation with `grand_total = 50000`. Save.
4. `Generate Installment Schedule` button appears in the toolbar. Click it.
5. `payment_schedule` child table populates: 5 rows, deposit first, 4 monthly rows of 10000 each.
6. Switch `Payment Type` to `Outright`. Deposit/start date/months fields clear. `payment_schedule` rows remain (standard ERPNext behavior — user deletes manually if desired).
7. Switch back to `Installment`, refill, regenerate. Rows replace.
8. Submit Quotation. Convert to Sales Order — verify `payment_schedule` copies over.
9. From the submitted SO, click `Create → Allocation Letter`. Verify `Purchase Price Option = Installment` is pre-selected and `Installment Schedule` contains 5 rows with labels `First, Second, Third, Fourth, Installment 5` matching the SO's amounts and due_dates.

- [ ] **Step 5: No additional commit unless a manual-test follow-up fix is required.**
