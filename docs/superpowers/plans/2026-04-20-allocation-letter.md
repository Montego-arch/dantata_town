# Allocation Letter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `Allocation Letter` submittable doctype (with its child + single) and wire it into Sales Order so users can generate, approve via Frappe workflow, print, and submit allocation offer letters.

**Architecture:** Three new doctypes in the Dantata Town module (`Allocation Letter`, `Allocation Letter Installment` child, `Allocation Letter Terms` single) plus a `Sales Order` client button that calls a whitelisted Python helper to open a mapped AL doc. Server-side validators in the AL controller enforce the Installment/Outright rules, snapshot the central terms at submit, and stamp approver info on workflow transitions to `Approved`. Workflow + role + print format are admin-configured in the Frappe UI (not seeded in code).

**Tech Stack:** Frappe Framework, ERPNext (Sales Order), Python 3, JavaScript form scripts, `FrappeTestCase`.

**Spec:** `docs/superpowers/specs/2026-04-20-allocation-letter-design.md`

**Working directory:** `/home/okeke/clients/graceco/frappe-bench/apps/dantata_town`

**Test command (one module):** `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`

**Migrate command:** `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`

---

## File Structure

**Files created:**

| Path | Responsibility |
|---|---|
| `dantata_town/dantata_town/doctype/allocation_letter_installment/__init__.py` | Package marker |
| `dantata_town/dantata_town/doctype/allocation_letter_installment/allocation_letter_installment.json` | Child table DocType definition |
| `dantata_town/dantata_town/doctype/allocation_letter_installment/allocation_letter_installment.py` | Empty child controller |
| `dantata_town/dantata_town/doctype/allocation_letter_terms/__init__.py` | Package marker |
| `dantata_town/dantata_town/doctype/allocation_letter_terms/allocation_letter_terms.json` | Single DocType definition |
| `dantata_town/dantata_town/doctype/allocation_letter_terms/allocation_letter_terms.py` | Empty single controller |
| `dantata_town/dantata_town/doctype/allocation_letter/__init__.py` | Package marker |
| `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.json` | Main submittable DocType definition |
| `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py` | Controller: validators, snapshot, approver stamping, `make_allocation_letter` helper |
| `dantata_town/dantata_town/doctype/allocation_letter/test_allocation_letter.py` | Per-doctype test stub |
| `dantata_town/dantata_town/tests/test_allocation_letter.py` | Integration tests for validators, helper, snapshot, stamping |
| `dantata_town/public/js/sales_order.js` | `Create → Allocation Letter` button on Sales Order |
| `dantata_town/public/js/allocation_letter.js` | Print guard + option-toggle behavior |

**Files modified:**

| Path | Change |
|---|---|
| `dantata_town/hooks.py` | Add Sales Order and Allocation Letter entries to `doctype_js` |

---

## Task 1: Create `Allocation Letter Installment` child doctype

**Files:**
- Create: `dantata_town/dantata_town/doctype/allocation_letter_installment/__init__.py`
- Create: `dantata_town/dantata_town/doctype/allocation_letter_installment/allocation_letter_installment.json`
- Create: `dantata_town/dantata_town/doctype/allocation_letter_installment/allocation_letter_installment.py`

- [ ] **Step 1: Create the package marker**

File: `dantata_town/dantata_town/doctype/allocation_letter_installment/__init__.py`

```python
```

(empty file)

- [ ] **Step 2: Create the child doctype JSON**

File: `dantata_town/dantata_town/doctype/allocation_letter_installment/allocation_letter_installment.json`

```json
{
 "actions": [],
 "creation": "2026-04-20 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "sequence_label",
  "amount",
  "due_date"
 ],
 "fields": [
  {
   "columns": 2,
   "fieldname": "sequence_label",
   "fieldtype": "Data",
   "in_list_view": 1,
   "label": "Sequence Label",
   "reqd": 1
  },
  {
   "columns": 3,
   "fieldname": "amount",
   "fieldtype": "Currency",
   "in_list_view": 1,
   "label": "Amount",
   "reqd": 1
  },
  {
   "columns": 3,
   "fieldname": "due_date",
   "fieldtype": "Date",
   "in_list_view": 1,
   "label": "On or before",
   "reqd": 1
  }
 ],
 "index_web_pages_for_search": 1,
 "istable": 1,
 "links": [],
 "modified": "2026-04-20 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Dantata Town",
 "name": "Allocation Letter Installment",
 "owner": "Administrator",
 "permissions": [],
 "row_format": "Dynamic",
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

- [ ] **Step 3: Create the empty controller**

File: `dantata_town/dantata_town/doctype/allocation_letter_installment/allocation_letter_installment.py`

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

from frappe.model.document import Document


class AllocationLetterInstallment(Document):
	pass
```

- [ ] **Step 4: Run migrate to register the child doctype**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`
Expected: Migration completes cleanly.

- [ ] **Step 5: Verify it registered**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com execute frappe.client.get_value --kwargs "{'doctype':'DocType','filters':{'name':'Allocation Letter Installment'},'fieldname':['istable','module']}"`
Expected: `{"istable": 1, "module": "Dantata Town"}`

- [ ] **Step 6: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/doctype/allocation_letter_installment/
git commit -m "feat: add Allocation Letter Installment child doctype"
```

---

## Task 2: Create `Allocation Letter Terms` single doctype

**Files:**
- Create: `dantata_town/dantata_town/doctype/allocation_letter_terms/__init__.py`
- Create: `dantata_town/dantata_town/doctype/allocation_letter_terms/allocation_letter_terms.json`
- Create: `dantata_town/dantata_town/doctype/allocation_letter_terms/allocation_letter_terms.py`

- [ ] **Step 1: Create the package marker**

File: `dantata_town/dantata_town/doctype/allocation_letter_terms/__init__.py`

```python
```

(empty file)

- [ ] **Step 2: Create the single doctype JSON**

File: `dantata_town/dantata_town/doctype/allocation_letter_terms/allocation_letter_terms.json`

```json
{
 "actions": [],
 "creation": "2026-04-20 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "conditions_text",
  "withdrawal_clause_text",
  "signatory_section",
  "default_chairman_name",
  "default_company_name"
 ],
 "fields": [
  {
   "fieldname": "conditions_text",
   "fieldtype": "Text Editor",
   "label": "Conditions Text"
  },
  {
   "fieldname": "withdrawal_clause_text",
   "fieldtype": "Text Editor",
   "label": "Withdrawal Clause Text"
  },
  {
   "fieldname": "signatory_section",
   "fieldtype": "Section Break",
   "label": "Signatory Defaults"
  },
  {
   "fieldname": "default_chairman_name",
   "fieldtype": "Data",
   "label": "Default Chairman Name"
  },
  {
   "fieldname": "default_company_name",
   "fieldtype": "Data",
   "label": "Default Company Name"
  }
 ],
 "index_web_pages_for_search": 1,
 "issingle": 1,
 "links": [],
 "modified": "2026-04-20 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Dantata Town",
 "name": "Allocation Letter Terms",
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
   "role": "Sales Manager",
   "share": 1,
   "write": 1
  }
 ],
 "row_format": "Dynamic",
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

- [ ] **Step 3: Create the empty controller**

File: `dantata_town/dantata_town/doctype/allocation_letter_terms/allocation_letter_terms.py`

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

from frappe.model.document import Document


class AllocationLetterTerms(Document):
	pass
```

- [ ] **Step 4: Run migrate**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`
Expected: Clean migration.

- [ ] **Step 5: Verify**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com execute frappe.client.get_value --kwargs "{'doctype':'DocType','filters':{'name':'Allocation Letter Terms'},'fieldname':['issingle','module']}"`
Expected: `{"issingle": 1, "module": "Dantata Town"}`

- [ ] **Step 6: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/doctype/allocation_letter_terms/
git commit -m "feat: add Allocation Letter Terms single doctype"
```

---

## Task 3: Create `Allocation Letter` main doctype (shell only)

**Files:**
- Create: `dantata_town/dantata_town/doctype/allocation_letter/__init__.py`
- Create: `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.json`
- Create: `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py`
- Create: `dantata_town/dantata_town/doctype/allocation_letter/test_allocation_letter.py`

- [ ] **Step 1: Create the package marker**

File: `dantata_town/dantata_town/doctype/allocation_letter/__init__.py`

```python
```

(empty file)

- [ ] **Step 2: Create the main doctype JSON**

File: `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.json`

```json
{
 "actions": [],
 "allow_rename": 0,
 "autoname": "naming_series:",
 "creation": "2026-04-20 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "naming_series",
  "letter_date",
  "column_break_header",
  "sales_order",
  "customer",
  "customer_name",
  "addressee_section",
  "addressee_name",
  "addressee_address",
  "property_section",
  "property_type",
  "property_description",
  "location_scheme",
  "plot_number",
  "column_break_property",
  "purchase_price_option",
  "cost_of_property",
  "payment_duration",
  "schedule_section",
  "installment_schedule",
  "approval_section",
  "approved_by",
  "approved_on",
  "column_break_approval",
  "terms_snapshot",
  "signature_section",
  "chairman_name",
  "company_name",
  "amend_section",
  "amended_from"
 ],
 "fields": [
  {
   "fieldname": "naming_series",
   "fieldtype": "Select",
   "label": "Series",
   "options": "ALL-.YYYY.-.#####",
   "reqd": 1,
   "set_only_once": 1
  },
  {
   "default": "Today",
   "fieldname": "letter_date",
   "fieldtype": "Date",
   "in_list_view": 1,
   "label": "Letter Date",
   "reqd": 1
  },
  {
   "fieldname": "column_break_header",
   "fieldtype": "Column Break"
  },
  {
   "fieldname": "sales_order",
   "fieldtype": "Link",
   "in_list_view": 1,
   "label": "Sales Order",
   "options": "Sales Order",
   "reqd": 1
  },
  {
   "fetch_from": "sales_order.customer",
   "fieldname": "customer",
   "fieldtype": "Link",
   "in_list_view": 1,
   "label": "Customer",
   "options": "Customer",
   "read_only": 1,
   "reqd": 1
  },
  {
   "fetch_from": "customer.customer_name",
   "fieldname": "customer_name",
   "fieldtype": "Data",
   "label": "Customer Name",
   "read_only": 1
  },
  {
   "fieldname": "addressee_section",
   "fieldtype": "Section Break",
   "label": "Addressee"
  },
  {
   "fieldname": "addressee_name",
   "fieldtype": "Data",
   "label": "Addressee Name",
   "reqd": 1
  },
  {
   "fieldname": "addressee_address",
   "fieldtype": "Small Text",
   "label": "Addressee Address"
  },
  {
   "fieldname": "property_section",
   "fieldtype": "Section Break",
   "label": "Property"
  },
  {
   "fieldname": "property_type",
   "fieldtype": "Select",
   "label": "Type",
   "options": "\nResidential\nCommercial",
   "reqd": 1
  },
  {
   "fieldname": "property_description",
   "fieldtype": "Data",
   "label": "Description",
   "reqd": 1
  },
  {
   "fieldname": "location_scheme",
   "fieldtype": "Small Text",
   "label": "Location / Scheme",
   "reqd": 1
  },
  {
   "fieldname": "plot_number",
   "fieldtype": "Data",
   "label": "House / Plot Number",
   "reqd": 1
  },
  {
   "fieldname": "column_break_property",
   "fieldtype": "Column Break"
  },
  {
   "fieldname": "purchase_price_option",
   "fieldtype": "Select",
   "label": "Purchase Price Option",
   "options": "\nInstallment\nOutright",
   "reqd": 1
  },
  {
   "fieldname": "cost_of_property",
   "fieldtype": "Currency",
   "label": "Cost of Property",
   "reqd": 1
  },
  {
   "depends_on": "eval:doc.purchase_price_option === 'Installment'",
   "fieldname": "payment_duration",
   "fieldtype": "Data",
   "label": "Payment Duration"
  },
  {
   "depends_on": "eval:doc.purchase_price_option === 'Installment'",
   "fieldname": "schedule_section",
   "fieldtype": "Section Break",
   "label": "Payment Schedule"
  },
  {
   "depends_on": "eval:doc.purchase_price_option === 'Installment'",
   "fieldname": "installment_schedule",
   "fieldtype": "Table",
   "label": "Installment Schedule",
   "options": "Allocation Letter Installment"
  },
  {
   "fieldname": "approval_section",
   "fieldtype": "Section Break",
   "label": "Approval"
  },
  {
   "fieldname": "approved_by",
   "fieldtype": "Link",
   "label": "Approved By",
   "options": "User",
   "read_only": 1
  },
  {
   "fieldname": "approved_on",
   "fieldtype": "Datetime",
   "label": "Approved On",
   "read_only": 1
  },
  {
   "fieldname": "column_break_approval",
   "fieldtype": "Column Break"
  },
  {
   "fieldname": "terms_snapshot",
   "fieldtype": "Text Editor",
   "label": "Terms Snapshot",
   "read_only": 1
  },
  {
   "fieldname": "signature_section",
   "fieldtype": "Section Break",
   "label": "Signature"
  },
  {
   "fieldname": "chairman_name",
   "fieldtype": "Data",
   "label": "Chairman Name"
  },
  {
   "default": "Dantata Town Developers Ltd",
   "fieldname": "company_name",
   "fieldtype": "Data",
   "label": "Company Name"
  },
  {
   "fieldname": "amend_section",
   "fieldtype": "Section Break",
   "label": "Amendment"
  },
  {
   "fieldname": "amended_from",
   "fieldtype": "Link",
   "label": "Amended From",
   "no_copy": 1,
   "options": "Allocation Letter",
   "print_hide": 1,
   "read_only": 1
  }
 ],
 "index_web_pages_for_search": 1,
 "is_submittable": 1,
 "links": [],
 "modified": "2026-04-20 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Dantata Town",
 "name": "Allocation Letter",
 "naming_rule": "By \"Naming Series\" field",
 "owner": "Administrator",
 "permissions": [
  {
   "amend": 1,
   "cancel": 1,
   "create": 1,
   "delete": 1,
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "System Manager",
   "share": 1,
   "submit": 1,
   "write": 1
  },
  {
   "amend": 1,
   "cancel": 1,
   "create": 1,
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "Sales Manager",
   "share": 1,
   "submit": 1,
   "write": 1
  },
  {
   "create": 1,
   "email": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "Sales User",
   "share": 1,
   "write": 1
  }
 ],
 "row_format": "Dynamic",
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
```

- [ ] **Step 3: Create the controller with empty hooks**

File: `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py`

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class AllocationLetter(Document):
	def validate(self):
		pass

	def on_update(self):
		pass

	def before_submit(self):
		pass
```

- [ ] **Step 4: Create the test stub**

File: `dantata_town/dantata_town/doctype/allocation_letter/test_allocation_letter.py`

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase


class TestAllocationLetter(FrappeTestCase):
	pass
```

- [ ] **Step 5: Run migrate**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`
Expected: Clean migration.

- [ ] **Step 6: Verify**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com execute frappe.client.get_value --kwargs "{'doctype':'DocType','filters':{'name':'Allocation Letter'},'fieldname':['is_submittable','autoname','module']}"`
Expected: `{"is_submittable": 1, "autoname": "naming_series:", "module": "Dantata Town"}`

- [ ] **Step 7: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/doctype/allocation_letter/
git commit -m "feat: add Allocation Letter main doctype shell"
```

---

## Task 4: `make_allocation_letter` helper — TDD

**Files:**
- Modify: `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py`
- Create: `dantata_town/dantata_town/tests/test_allocation_letter.py`

- [ ] **Step 1: Write the failing test**

File: `dantata_town/dantata_town/tests/test_allocation_letter.py`

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


def _ensure_terms(chairman="Alhassan A. Dantata", company="Dantata Town Developers Ltd", conditions="<p>1. Conditions go here.</p>"):
	terms = frappe.get_single("Allocation Letter Terms")
	terms.default_chairman_name = chairman
	terms.default_company_name = company
	terms.conditions_text = conditions
	terms.withdrawal_clause_text = ""
	terms.save(ignore_permissions=True)


def _pick_submitted_sales_order():
	so = frappe.get_all(
		"Sales Order",
		filters={"docstatus": 1},
		fields=["name", "customer", "customer_name", "grand_total"],
		limit=1,
	)
	return so[0] if so else None


class TestAllocationLetter(FrappeTestCase):
	def test_make_allocation_letter_prefills_from_sales_order(self):
		_ensure_terms()
		so = _pick_submitted_sales_order()
		if not so:
			self.skipTest("No submitted Sales Order on this site")

		from dantata_town.dantata_town.doctype.allocation_letter.allocation_letter import (
			make_allocation_letter,
		)
		target = make_allocation_letter(so.name)

		self.assertEqual(target.doctype, "Allocation Letter")
		self.assertEqual(target.sales_order, so.name)
		self.assertEqual(target.customer, so.customer)
		self.assertEqual(target.customer_name, so.customer_name)
		self.assertEqual(target.cost_of_property, so.grand_total)
		self.assertEqual(target.addressee_name, so.customer_name)
		self.assertEqual(target.chairman_name, "Alhassan A. Dantata")
		self.assertEqual(target.company_name, "Dantata Town Developers Ltd")
		self.assertEqual(target.letter_date, frappe.utils.today())
```

- [ ] **Step 2: Create the tests package marker if missing**

File: `dantata_town/dantata_town/tests/__init__.py`
Already exists (created for the Project Type refactor). Skip if present.

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`
Expected: ImportError (`cannot import name 'make_allocation_letter'`).

- [ ] **Step 4: Implement the helper**

File: `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py`

Replace the file with:

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, now, today


class AllocationLetter(Document):
	def validate(self):
		pass

	def on_update(self):
		pass

	def before_submit(self):
		pass


@frappe.whitelist()
def make_allocation_letter(source_name, target_doc=None):
	"""Create an Allocation Letter pre-filled from a Sales Order."""

	def set_defaults(source, target, source_parent):
		target.letter_date = today()
		target.addressee_name = source.customer_name
		primary_addr = frappe.db.get_value(
			"Address",
			{
				"link_doctype": "Customer",
				"link_name": source.customer,
				"is_primary_address": 1,
			},
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

	return get_mapped_doc(
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
```

- [ ] **Step 5: Re-run the test**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`
Expected: PASS (or skipped if no submitted SO — acceptable).

- [ ] **Step 6: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py dantata_town/dantata_town/tests/test_allocation_letter.py
git commit -m "feat: add make_allocation_letter helper that pre-fills from Sales Order"
```

---

## Task 5: Outright clears schedule + duration (validate)

**Files:**
- Modify: `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py`
- Modify: `dantata_town/dantata_town/tests/test_allocation_letter.py`

- [ ] **Step 1: Add the failing test**

Append to `dantata_town/dantata_town/tests/test_allocation_letter.py` inside `TestAllocationLetter`:

```python
	def _new_draft_letter(self, so, **overrides):
		"""Helper to build a new AL in memory with sensible defaults."""
		_ensure_terms()
		doc = frappe.get_doc({
			"doctype": "Allocation Letter",
			"letter_date": frappe.utils.today(),
			"sales_order": so.name,
			"customer": so.customer,
			"addressee_name": so.customer_name,
			"property_type": "Residential",
			"property_description": "4-bedrooms Semi-Detached Duplex - DPC",
			"location_scheme": "Dantata City Estate, F01 Kubwa, Abuja",
			"plot_number": "DCB-001",
			"purchase_price_option": "Installment",
			"cost_of_property": 1000,
			"payment_duration": "4 months",
			"installment_schedule": [
				{"sequence_label": "First", "amount": 250, "due_date": frappe.utils.today()},
				{"sequence_label": "Second", "amount": 250, "due_date": frappe.utils.today()},
				{"sequence_label": "Third", "amount": 250, "due_date": frappe.utils.today()},
				{"sequence_label": "Fourth", "amount": 250, "due_date": frappe.utils.today()},
			],
		})
		doc.update(overrides)
		return doc

	def test_outright_clears_schedule_and_duration(self):
		so = _pick_submitted_sales_order()
		if not so:
			self.skipTest("No submitted Sales Order on this site")
		doc = self._new_draft_letter(so, purchase_price_option="Outright")
		# At this point the in-memory doc still has installment_schedule and payment_duration.
		doc.insert(ignore_permissions=True)
		doc.reload()
		self.assertEqual(len(doc.installment_schedule or []), 0)
		self.assertIn(doc.payment_duration, (None, ""))
```

- [ ] **Step 2: Run the test to see it fail**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`
Expected: the new test FAILS (rows or duration still present).

- [ ] **Step 3: Implement the Outright-clears behavior in `validate`**

In `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py`, replace the `validate` method body:

```python
	def validate(self):
		if self.purchase_price_option == "Outright":
			self.installment_schedule = []
			self.payment_duration = None
```

- [ ] **Step 4: Re-run the test**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py dantata_town/dantata_town/tests/test_allocation_letter.py
git commit -m "feat: clear schedule and duration when purchase option is Outright"
```

---

## Task 6: Installment validators (sum, duration, rows)

**Files:**
- Modify: `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py`
- Modify: `dantata_town/dantata_town/tests/test_allocation_letter.py`

- [ ] **Step 1: Add the three failing tests**

Append inside `TestAllocationLetter`:

```python
	def test_installment_schedule_sum_mismatch_rejected(self):
		so = _pick_submitted_sales_order()
		if not so:
			self.skipTest("No submitted Sales Order on this site")
		doc = self._new_draft_letter(so)
		doc.installment_schedule[0].amount = 100  # total now 850, not 1000
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_installment_without_payment_duration_rejected(self):
		so = _pick_submitted_sales_order()
		if not so:
			self.skipTest("No submitted Sales Order on this site")
		doc = self._new_draft_letter(so, payment_duration="")
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_installment_without_schedule_rows_rejected(self):
		so = _pick_submitted_sales_order()
		if not so:
			self.skipTest("No submitted Sales Order on this site")
		doc = self._new_draft_letter(so, installment_schedule=[])
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`
Expected: The three new tests FAIL (no ValidationError raised).

- [ ] **Step 3: Extend `validate` with the installment checks**

Replace the `validate` method in `allocation_letter.py`:

```python
	def validate(self):
		if self.purchase_price_option == "Outright":
			self.installment_schedule = []
			self.payment_duration = None
			return

		if self.purchase_price_option == "Installment":
			if not self.payment_duration:
				frappe.throw(_("Payment Duration is required for installment offers."))
			if not self.installment_schedule:
				frappe.throw(_("Add at least one installment row for installment offers."))
			total = sum(flt(row.amount) for row in self.installment_schedule)
			if flt(total) != flt(self.cost_of_property):
				frappe.throw(_(
					"Installment schedule total ({0}) does not match Cost of Property ({1})."
				).format(
					frappe.utils.fmt_money(total, currency=frappe.defaults.get_global_default("currency")),
					frappe.utils.fmt_money(self.cost_of_property, currency=frappe.defaults.get_global_default("currency")),
				))
```

- [ ] **Step 4: Re-run all tests**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py dantata_town/dantata_town/tests/test_allocation_letter.py
git commit -m "feat: enforce installment schedule sum, duration, and non-empty rows"
```

---

## Task 7: Terms snapshot at submit

**Files:**
- Modify: `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py`
- Modify: `dantata_town/dantata_town/tests/test_allocation_letter.py`

- [ ] **Step 1: Add failing tests**

Append inside `TestAllocationLetter`:

```python
	def test_terms_snapshot_populated_at_submit(self):
		so = _pick_submitted_sales_order()
		if not so:
			self.skipTest("No submitted Sales Order on this site")
		_ensure_terms(conditions="<p>Known conditions v1.</p>")
		doc = self._new_draft_letter(so).insert(ignore_permissions=True)
		doc.submit()
		doc.reload()
		self.assertIn("Known conditions v1.", doc.terms_snapshot or "")

		# Editing the single does not change the submitted doc's snapshot.
		_ensure_terms(conditions="<p>Updated conditions v2.</p>")
		doc.reload()
		self.assertIn("Known conditions v1.", doc.terms_snapshot or "")
		self.assertNotIn("Updated conditions v2.", doc.terms_snapshot or "")

	def test_submit_rejected_when_terms_not_configured(self):
		so = _pick_submitted_sales_order()
		if not so:
			self.skipTest("No submitted Sales Order on this site")
		_ensure_terms(conditions="")
		doc = self._new_draft_letter(so).insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			doc.submit()
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`
Expected: the two new tests FAIL (snapshot empty and submit permitted).

- [ ] **Step 3: Implement `before_submit`**

Replace the `before_submit` method in `allocation_letter.py`:

```python
	def before_submit(self):
		terms = frappe.get_single("Allocation Letter Terms")
		if not (terms.conditions_text or "").strip():
			frappe.throw(_(
				"Please configure Allocation Letter Terms → Conditions Text before submitting."
			))
		snapshot = terms.conditions_text
		if terms.withdrawal_clause_text:
			snapshot += "\n\n" + terms.withdrawal_clause_text
		self.terms_snapshot = snapshot
```

- [ ] **Step 4: Re-run tests**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py dantata_town/dantata_town/tests/test_allocation_letter.py
git commit -m "feat: snapshot Allocation Letter Terms at submit and require configured terms"
```

---

## Task 8: Approver stamping on workflow transition to Approved

**Files:**
- Modify: `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.json`
- Modify: `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py`
- Modify: `dantata_town/dantata_town/tests/test_allocation_letter.py`

- [ ] **Step 1: Add the `workflow_state` field to the doctype JSON**

In `dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.json`:

1. In `field_order`, add `"workflow_state"` between `"approved_on"` and `"column_break_approval"`.
2. In `fields`, add this entry between the `approved_on` and `column_break_approval` entries:

```json
  {
   "fieldname": "workflow_state",
   "fieldtype": "Link",
   "label": "Workflow State",
   "no_copy": 1,
   "options": "Workflow State",
   "read_only": 1
  },
```

Frappe normally adds this field automatically when a workflow is applied to the doctype. We pre-create it so the test works without the workflow being configured yet.

- [ ] **Step 2: Run migrate so the column exists**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`
Expected: Clean migration.

- [ ] **Step 3: Add the failing test**

Append inside `TestAllocationLetter`:

```python
	def test_approved_stamps_set_on_transition_to_approved(self):
		so = _pick_submitted_sales_order()
		if not so:
			self.skipTest("No submitted Sales Order on this site")
		_ensure_terms()
		doc = self._new_draft_letter(so).insert(ignore_permissions=True)
		# Simulate workflow moving to Approved.
		doc.workflow_state = "Approved"
		doc.save(ignore_permissions=True)
		doc.reload()
		self.assertEqual(doc.approved_by, frappe.session.user)
		self.assertIsNotNone(doc.approved_on)
```

- [ ] **Step 4: Run the test to see it fail**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`
Expected: the new test FAILS — `approved_by` stays None because `on_update` is still a no-op.

- [ ] **Step 5: Implement `on_update` stamping**

Replace the `on_update` method in `allocation_letter.py`:

```python
	def on_update(self):
		prev = self.get_doc_before_save()
		prev_state = prev.workflow_state if prev else None
		if self.workflow_state == "Approved" and prev_state != "Approved":
			frappe.db.set_value(
				"Allocation Letter",
				self.name,
				{
					"approved_by": frappe.session.user,
					"approved_on": now(),
				},
				update_modified=False,
			)
			self.approved_by = frappe.session.user
			self.approved_on = now()
```

Using `frappe.db.set_value` avoids re-triggering validate/save in a recursion; setting the in-memory fields keeps the current `self` consistent so the reload in tests sees the values.

- [ ] **Step 6: Re-run tests**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.json dantata_town/dantata_town/doctype/allocation_letter/allocation_letter.py dantata_town/dantata_town/tests/test_allocation_letter.py
git commit -m "feat: stamp approved_by and approved_on on workflow transition to Approved"
```

---

## Task 9: Sales Order client script — `Create → Allocation Letter` button

**Files:**
- Create: `dantata_town/public/js/sales_order.js`
- Modify: `dantata_town/hooks.py`

- [ ] **Step 1: Write the client script**

File: `dantata_town/public/js/sales_order.js`

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

- [ ] **Step 2: Wire `doctype_js` in hooks.py**

In `dantata_town/hooks.py`, find this line:

```python
doctype_js = {"Project": "public/js/project.js"}
```

Replace it with:

```python
doctype_js = {
	"Project": "public/js/project.js",
	"Sales Order": "public/js/sales_order.js",
	"Allocation Letter": "public/js/allocation_letter.js",
}
```

(The Allocation Letter entry pre-references the file created in Task 10; Frappe tolerates a missing file until the form is loaded, so adding it here is safe.)

- [ ] **Step 3: Build assets**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench build --app dantata_town`
Expected: Build completes without errors.

- [ ] **Step 4: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/public/js/sales_order.js dantata_town/hooks.py
git commit -m "feat: add Create → Allocation Letter button on Sales Order"
```

---

## Task 10: Allocation Letter client script (option toggle + print guard)

**Files:**
- Create: `dantata_town/public/js/allocation_letter.js`

- [ ] **Step 1: Write the client script**

File: `dantata_town/public/js/allocation_letter.js`

```javascript
frappe.ui.form.on("Allocation Letter", {
	refresh(frm) {
		const state = frm.doc.workflow_state;
		const can_print = state === "Approved" || state === "Submitted";
		// Hide the toolbar Print button until the letter is approved.
		if (frm.page.btn_print_action) {
			frm.page.btn_print_action.toggle(can_print);
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

- [ ] **Step 2: Build assets**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench build --app dantata_town`
Expected: Build completes.

- [ ] **Step 3: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/public/js/allocation_letter.js
git commit -m "feat: Allocation Letter client script — print guard and option toggle"
```

---

## Task 11: Full migrate + test suite + smoke check

**Files:** none (verification)

- [ ] **Step 1: Full migrate**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`
Expected: Clean output ending with `Queued rebuilding of search index`.

- [ ] **Step 2: Run the full Allocation Letter test module**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_allocation_letter`
Expected: All tests PASS (or the ones requiring a submitted SO are skipped — note whether any were skipped).

- [ ] **Step 3: Run the full dantata_town test suite**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town`
Expected: All tests across all modules PASS.

- [ ] **Step 4: Clear cache and rebuild**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com clear-cache && bench build --app dantata_town`
Expected: Both commands clean.

- [ ] **Step 5: Manual UI smoke test (reported, not executed here)**

In the browser as a user with Sales Manager or System Manager role:

1. Navigate to `Allocation Letter Terms` single. Fill `conditions_text` with the 17 clauses, `default_chairman_name = "Alhassan A. Dantata"`, `default_company_name = "Dantata Town Developers Ltd"`. Save.
2. Create the Role `Allocation Letter Approver` (Role List → New).
3. Create the workflow `Allocation Letter Approval` on the `Allocation Letter` doctype with the 4 states and 5 transitions per the spec.
4. Create a Print Format named `Allocation Letter` (Jinja) and paste the reference HTML from the spec.
5. Pick any submitted Sales Order → `Create → Allocation Letter` — verify the pre-filled fields match the SO.
6. Fill property block, choose Installment, add 4 schedule rows summing to `cost_of_property`, set payment_duration, save.
7. Walk through Submit for Approval → Approve → Finalize. Verify `approved_by`/`approved_on` fill in at Approve, `terms_snapshot` at Finalize, and Print button only visible from Approve onwards.
8. Print the letter — layout matches the sample PDF.
9. Open the Sales Order → Connections panel → Allocation Letter appears.

- [ ] **Step 6: No additional commit unless a manual-test follow-up fix is needed.**
