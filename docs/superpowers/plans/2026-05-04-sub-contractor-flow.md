# Sub Contractor Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the sub-contractor payment workflow: BOQ classifies lines as Company / Sub Contractor; a button on a submitted BOQ creates a Sub Contractor Payment Request via a modal picker; the request shows an at-submit diff modal when qty/rate changed; an Approved request creates a draft Purchase Invoice with `expense_account` resolved from the Site.

**Architecture:** New `Sub Contractor Payment Request` parent + child doctypes (custom-owned). Cross-cutting helpers (`make_request_from_boq`, `make_purchase_invoice`, diff helpers) in a shared module `sub_contractor.py`. Doctype controller stays thin (validate recomputes amounts). Form-script extensions for the BOQ button + modal picker, and for the request's diff prompt + PI button. Tests use docstatus only — workflow is admin-managed and not part of the test path; the server's `workflow_state == "Approved"` gate is conditional (`if req.workflow_state and req.workflow_state != "Approved"`) so tests pass with empty `workflow_state`.

**Tech Stack:** Frappe v15 / ERPNext, Python 3.11, MariaDB, Frappe form-script (vanilla JS + `frappe.ui.Dialog`), `frappe.tests.utils.FrappeTestCase`.

**Spec:** `docs/superpowers/specs/2026-05-04-sub-contractor-flow-design.md`

---

## File Structure

**Created files:**

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

**Edited files:**

```
dantata_town/dantata_town/setup.py                                     # +BOQ Items.assignment_type, +PI.site, +PI.sub_contractor_payment_request
dantata_town/dantata_town/doctype/site/site.json                       # +expense_account
dantata_town/public/js/bill_of_quantities.js                           # +Create Sub Contractor Payment Request button + modal
```

**Module responsibilities:**
- `sub_contractor.py` — `make_request_from_boq`, `make_purchase_invoice`, `_resolve_stage_label`, `_ensure_boq_submitted`. Whitelisted methods called from JS.
- `sub_contractor_payment_request.py` — controller with `validate` recomputing row `amount` and parent `total_amount`.
- `sub_contractor_payment_request.js` — `before_submit` diff modal, `refresh` PI button (conditionally shown).
- `sub_contractor_payment_request_item.py` — minimal child controller (no logic).

---

## Pre-flight

- [ ] **Step 0.1: Confirm clean working tree on `develop`**

```bash
git status
git log --oneline -3
```
Expected: working tree clean (only the pre-existing untracked `dantata_town/dantata_town/print_format/` directory), latest commit is `7b2a113 docs: design spec for sub contractor payment flow`.

- [ ] **Step 0.2: Confirm bench is reachable**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com list-apps
```
Expected: dantata_town listed.

---

## Task 1: Site `expense_account` JSON edit

**Files:**
- Modify: `dantata_town/dantata_town/doctype/site/site.json`

- [ ] **Step 1.1: Read current `site.json`**

```bash
cat dantata_town/dantata_town/doctype/site/site.json
```
Confirm the existing `field_order` is `["site_name", "column_break_lflt", "expected_start_date", "expected_end_date", "section_break_diyy", "project_units", "total_units", "notes_section", "notes"]`.

- [ ] **Step 1.2: Edit `site.json`**

Update `field_order` to insert `expense_account` after `expected_end_date`:

```json
"field_order": [
  "site_name",
  "column_break_lflt",
  "expected_start_date",
  "expected_end_date",
  "expense_account",
  "section_break_diyy",
  "project_units",
  "total_units",
  "notes_section",
  "notes"
]
```

In the `fields` array, insert this block after the `expected_end_date` field (before `section_break_diyy`):

```json
{
  "fieldname": "expense_account",
  "fieldtype": "Link",
  "label": "Expense Account",
  "options": "Account"
}
```

- [ ] **Step 1.3: Validate JSON parses**

```bash
python3 -c "import json; json.load(open('dantata_town/dantata_town/doctype/site/site.json'))"
```
Expected: no output, exit 0.

- [ ] **Step 1.4: Migrate**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate
```
Expected: success; `expense_account` column appears on `tabSite`.

- [ ] **Step 1.5: Verify column exists**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com mariadb -e "SHOW COLUMNS FROM \`tabSite\` LIKE 'expense_account'" 2>/dev/null
```
Expected: one row showing `expense_account` varchar(140).

- [ ] **Step 1.6: Commit**

```bash
git add dantata_town/dantata_town/doctype/site/site.json
git commit -m "feat: add expense_account Link to Site doctype"
```

---

## Task 2: BOQ Items `assignment_type` + Purchase Invoice custom fields

Adds three custom fields registered through `setup.py`.

**Files:**
- Modify: `dantata_town/dantata_town/setup.py`
- Create: `dantata_town/dantata_town/tests/test_sub_contractor_flow.py`

- [ ] **Step 2.1: Write failing field-existence tests**

Create `dantata_town/dantata_town/tests/test_sub_contractor_flow.py`:

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from dantata_town.dantata_town.setup import create_boq_custom_fields


class TestSubContractorFieldsInstalled(FrappeTestCase):
	def test_assignment_type_field_on_boq_items(self):
		create_boq_custom_fields()
		field = frappe.db.get_value(
			"Custom Field",
			{"dt": "BOQ Items", "fieldname": "assignment_type"},
			["fieldtype", "options", "default", "allow_on_submit", "in_list_view"],
			as_dict=True,
		)
		self.assertIsNotNone(field, "assignment_type missing on BOQ Items")
		self.assertEqual(field.fieldtype, "Select")
		self.assertEqual(field.options, "Company\nSub Contractor")
		self.assertEqual(field.default, "Company")
		self.assertEqual(field.allow_on_submit, 1)
		self.assertEqual(field.in_list_view, 1)

	def test_site_field_on_purchase_invoice(self):
		create_boq_custom_fields()
		field = frappe.db.get_value(
			"Custom Field",
			{"dt": "Purchase Invoice", "fieldname": "site"},
			["fieldtype", "options"],
			as_dict=True,
		)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "Site")

	def test_sub_contractor_payment_request_field_on_purchase_invoice(self):
		create_boq_custom_fields()
		field = frappe.db.get_value(
			"Custom Field",
			{"dt": "Purchase Invoice", "fieldname": "sub_contractor_payment_request"},
			["fieldtype", "options", "read_only"],
			as_dict=True,
		)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "Sub Contractor Payment Request")
		self.assertEqual(field.read_only, 1)

	def test_expense_account_field_on_site(self):
		"""Site.expense_account is JSON-defined, not a Custom Field — verify via meta."""
		meta = frappe.get_meta("Site")
		field = meta.get_field("expense_account")
		self.assertIsNotNone(field, "expense_account missing on Site")
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "Account")
```

- [ ] **Step 2.2: Run tests — expect 3 failures, 1 pass**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_sub_contractor_flow
```
Expected: `test_expense_account_field_on_site` passes (Task 1 already shipped this); the three Custom Field tests fail.

- [ ] **Step 2.3: Extend `setup.py` — add BOQ Items `assignment_type`**

In `dantata_town/dantata_town/setup.py`, in `_create_custom_fields()`, find the `"BOQ Items"` entry (added in Spec 1 Task 7) and append the new field dict after `completed`:

```python
		"BOQ Items": [
			# ... existing 'completed' entry unchanged ...
			{
				"fieldname": "assignment_type",
				"fieldtype": "Select",
				"label": "Assignment Type",
				"options": "Company\nSub Contractor",
				"default": "Company",
				"insert_after": "completed",
				"allow_on_submit": 1,
				"in_list_view": 1,
				"module": "Dantata Town",
			},
		],
```

- [ ] **Step 2.4: Extend `setup.py` — add Purchase Invoice custom fields**

In the same `custom_fields` dict, add a new top-level `"Purchase Invoice"` key:

```python
		"Purchase Invoice": [
			{
				"fieldname": "site",
				"fieldtype": "Link",
				"label": "Site",
				"options": "Site",
				"insert_after": "company",
				"module": "Dantata Town",
			},
			{
				"fieldname": "sub_contractor_payment_request",
				"fieldtype": "Link",
				"label": "Sub Contractor Payment Request",
				"options": "Sub Contractor Payment Request",
				"insert_after": "site",
				"read_only": 1,
				"module": "Dantata Town",
			},
		],
```

NOTE: `Sub Contractor Payment Request` doctype doesn't exist yet (Task 4 creates it). The Link's `options` is just a string — `create_custom_fields` will register it without checking existence. Once Task 4 lands, the Link resolves correctly.

- [ ] **Step 2.5: Run install hook**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate
```
Expected: success. The `sub_contractor_payment_request` Link field on PI will be flagged by Frappe as having a missing target doctype — that's expected; it'll resolve after Task 4.

- [ ] **Step 2.6: Run tests — expect 4 pass**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_sub_contractor_flow
```
Expected: 4/4 pass.

- [ ] **Step 2.7: Commit**

```bash
git add dantata_town/dantata_town/setup.py \
        dantata_town/dantata_town/tests/test_sub_contractor_flow.py
git commit -m "feat: register BOQ Items.assignment_type and PI site/sub_contractor_payment_request"
```

---

## Task 3: Sub Contractor Payment Request Item child doctype

**Files:**
- Create: `dantata_town/dantata_town/doctype/sub_contractor_payment_request_item/__init__.py`
- Create: `dantata_town/dantata_town/doctype/sub_contractor_payment_request_item/sub_contractor_payment_request_item.json`
- Create: `dantata_town/dantata_town/doctype/sub_contractor_payment_request_item/sub_contractor_payment_request_item.py`

- [ ] **Step 3.1: Create `__init__.py`**

Create empty `dantata_town/dantata_town/doctype/sub_contractor_payment_request_item/__init__.py`:

```python
```

- [ ] **Step 3.2: Create the child doctype JSON**

Create `dantata_town/dantata_town/doctype/sub_contractor_payment_request_item/sub_contractor_payment_request_item.json`:

```json
{
 "actions": [],
 "allow_rename": 1,
 "creation": "2026-05-04 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "stage_label",
  "description",
  "unit",
  "quantity",
  "rate",
  "amount",
  "original_quantity",
  "original_rate",
  "boq_item"
 ],
 "fields": [
  {
   "columns": 2,
   "fieldname": "stage_label",
   "fieldtype": "Data",
   "in_list_view": 1,
   "label": "Stage",
   "read_only": 1
  },
  {
   "columns": 3,
   "fieldname": "description",
   "fieldtype": "Link",
   "in_list_view": 1,
   "label": "Description",
   "options": "BOQ Item Detail",
   "reqd": 1
  },
  {
   "columns": 1,
   "fetch_from": "description.unit",
   "fieldname": "unit",
   "fieldtype": "Data",
   "in_list_view": 1,
   "label": "Unit",
   "read_only": 1
  },
  {
   "columns": 1,
   "fieldname": "quantity",
   "fieldtype": "Float",
   "in_list_view": 1,
   "label": "Quantity",
   "reqd": 1
  },
  {
   "columns": 1,
   "fieldname": "rate",
   "fieldtype": "Currency",
   "in_list_view": 1,
   "label": "Rate",
   "reqd": 1
  },
  {
   "columns": 2,
   "fieldname": "amount",
   "fieldtype": "Currency",
   "in_list_view": 1,
   "label": "Amount",
   "read_only": 1
  },
  {
   "fieldname": "original_quantity",
   "fieldtype": "Float",
   "hidden": 1,
   "label": "Original Quantity",
   "read_only": 1
  },
  {
   "fieldname": "original_rate",
   "fieldtype": "Currency",
   "hidden": 1,
   "label": "Original Rate",
   "read_only": 1
  },
  {
   "fieldname": "boq_item",
   "fieldtype": "Data",
   "hidden": 1,
   "label": "BOQ Item Reference",
   "read_only": 1
  }
 ],
 "grid_page_length": 50,
 "index_web_pages_for_search": 1,
 "istable": 1,
 "links": [],
 "modified": "2026-05-04 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Dantata Town",
 "name": "Sub Contractor Payment Request Item",
 "owner": "Administrator",
 "permissions": [],
 "row_format": "Dynamic",
 "rows_threshold_for_grid_search": 20,
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

- [ ] **Step 3.3: Create the controller**

Create `dantata_town/dantata_town/doctype/sub_contractor_payment_request_item/sub_contractor_payment_request_item.py`:

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

from frappe.model.document import Document


class SubContractorPaymentRequestItem(Document):
	pass
```

- [ ] **Step 3.4: Validate JSON parses**

```bash
python3 -c "import json; json.load(open('dantata_town/dantata_town/doctype/sub_contractor_payment_request_item/sub_contractor_payment_request_item.json'))"
```
Expected: exit 0.

- [ ] **Step 3.5: Commit**

```bash
git add dantata_town/dantata_town/doctype/sub_contractor_payment_request_item/
git commit -m "feat: add Sub Contractor Payment Request Item child doctype"
```

(Migration happens in Task 4 along with the parent; can't `bench migrate` mid-creation since the parent's options reference the child.)

---

## Task 4: Sub Contractor Payment Request parent doctype + controller

**Files:**
- Create: `dantata_town/dantata_town/doctype/sub_contractor_payment_request/__init__.py`
- Create: `dantata_town/dantata_town/doctype/sub_contractor_payment_request/sub_contractor_payment_request.json`
- Create: `dantata_town/dantata_town/doctype/sub_contractor_payment_request/sub_contractor_payment_request.py`
- Create: `dantata_town/dantata_town/doctype/sub_contractor_payment_request/test_sub_contractor_payment_request.py`

- [ ] **Step 4.1: Create `__init__.py`**

Create empty `dantata_town/dantata_town/doctype/sub_contractor_payment_request/__init__.py`:

```python
```

- [ ] **Step 4.2: Create the parent doctype JSON**

Create `dantata_town/dantata_town/doctype/sub_contractor_payment_request/sub_contractor_payment_request.json`:

```json
{
 "actions": [],
 "allow_rename": 1,
 "autoname": "naming_series:",
 "creation": "2026-05-04 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "naming_series",
  "section_break_top",
  "amended_from",
  "date",
  "site",
  "project",
  "column_break_top",
  "boq",
  "supplier",
  "section_break_items",
  "items",
  "section_break_total",
  "total_amount"
 ],
 "fields": [
  {
   "default": "SCPR-.YYYY.-.#####",
   "fieldname": "naming_series",
   "fieldtype": "Select",
   "label": "Naming Series",
   "options": "SCPR-.YYYY.-.#####",
   "set_only_once": 1
  },
  {
   "fieldname": "section_break_top",
   "fieldtype": "Section Break"
  },
  {
   "fieldname": "amended_from",
   "fieldtype": "Link",
   "label": "Amended From",
   "no_copy": 1,
   "options": "Sub Contractor Payment Request",
   "print_hide": 1,
   "read_only": 1,
   "search_index": 1
  },
  {
   "fieldname": "date",
   "fieldtype": "Date",
   "in_list_view": 1,
   "label": "Date",
   "reqd": 1
  },
  {
   "fieldname": "site",
   "fieldtype": "Link",
   "in_list_view": 1,
   "label": "Site",
   "options": "Site",
   "read_only": 1,
   "reqd": 1
  },
  {
   "fieldname": "project",
   "fieldtype": "Link",
   "label": "Project",
   "options": "Project",
   "read_only": 1,
   "reqd": 1
  },
  {
   "fieldname": "column_break_top",
   "fieldtype": "Column Break"
  },
  {
   "fieldname": "boq",
   "fieldtype": "Link",
   "label": "Bill of Quantities",
   "options": "Bill of Quantities",
   "read_only": 1,
   "reqd": 1
  },
  {
   "fieldname": "supplier",
   "fieldtype": "Link",
   "in_list_view": 1,
   "label": "Supplier",
   "options": "Supplier",
   "read_only": 1,
   "reqd": 1
  },
  {
   "fieldname": "section_break_items",
   "fieldtype": "Section Break",
   "label": "Items"
  },
  {
   "fieldname": "items",
   "fieldtype": "Table",
   "label": "Items",
   "options": "Sub Contractor Payment Request Item",
   "reqd": 1
  },
  {
   "fieldname": "section_break_total",
   "fieldtype": "Section Break"
  },
  {
   "fieldname": "total_amount",
   "fieldtype": "Currency",
   "in_list_view": 1,
   "label": "Total Amount",
   "read_only": 1
  }
 ],
 "grid_page_length": 50,
 "index_web_pages_for_search": 1,
 "is_submittable": 1,
 "links": [
  {
   "link_doctype": "Purchase Invoice",
   "link_fieldname": "sub_contractor_payment_request"
  }
 ],
 "modified": "2026-05-04 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Dantata Town",
 "name": "Sub Contractor Payment Request",
 "naming_rule": "By \"Naming Series\" field",
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
   "submit": 1,
   "cancel": 1,
   "amend": 1,
   "write": 1
  }
 ],
 "row_format": "Dynamic",
 "rows_threshold_for_grid_search": 20,
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
```

- [ ] **Step 4.3: Create the controller**

Create `dantata_town/dantata_town/doctype/sub_contractor_payment_request/sub_contractor_payment_request.py`:

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

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

- [ ] **Step 4.4: Write controller tests**

Create `dantata_town/dantata_town/doctype/sub_contractor_payment_request/test_sub_contractor_payment_request.py`:

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today

from dantata_town.dantata_town.setup import create_boq_custom_fields


def _make_site_and_project_minimal():
	"""Build a minimal Site + Project pair for tests in this module."""
	create_boq_custom_fields()
	uom = frappe.db.get_value("UOM", {}, "name")
	item = frappe.db.get_value("Item", {"disabled": 0}, "name")
	customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
	company = frappe.db.get_single_value("Global Defaults", "default_company") \
		or frappe.db.get_value("Company", {}, "name")
	site = frappe.get_doc({
		"doctype": "Site",
		"site_name": f"SCPR-Site-{frappe.generate_hash(length=6)}",
		"project_units": [{"building_type": item, "unit": 1, "uom": uom, "rate": 1}],
	}).insert(ignore_permissions=True)
	project = frappe.get_doc({
		"doctype": "Project",
		"project_name": f"SCPR-Proj-{frappe.generate_hash(length=6)}",
		"customer": customer,
		"company": company,
		"site": site.name,
		"project_type": "Building",
		"project_subtype": "PLOT",
	}).insert(ignore_permissions=True)
	return site.name, project.name


def _detail_name():
	existing = frappe.db.get_value("BOQ Item Detail", {}, "name")
	if existing:
		return existing
	return frappe.get_doc({
		"doctype": "BOQ Item Detail",
		"description": f"Detail-{frappe.generate_hash(length=6)}",
		"description_type": "Material",
		"unit": "Nos",
	}).insert(ignore_permissions=True).name


def _make_boq(site, project):
	"""Insert and submit a BOQ with a single Sub Contractor row in stage 1."""
	doc = frappe.new_doc("Bill of Quantities")
	doc.site = site
	doc.project = project
	doc.date = today()
	doc.append("table_txao", {
		"description": _detail_name(),
		"planned_quantity": 5,
		"rate": 1000,
		"assignment_type": "Sub Contractor",
	})
	doc.stage_1_start_date = today()
	doc.stage_1_end_date = frappe.utils.add_days(today(), 10)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


class TestSubContractorPaymentRequestDoctype(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()

	def _new_request(self, supplier=None, items=None):
		site, project = _make_site_and_project_minimal()
		boq = _make_boq(site, project)
		supplier = supplier or frappe.db.get_value("Supplier", {"disabled": 0}, "name")
		req = frappe.new_doc("Sub Contractor Payment Request")
		req.date = today()
		req.site = site
		req.project = project
		req.boq = boq
		req.supplier = supplier
		for r in (items or [{"description": _detail_name(), "quantity": 2, "rate": 500,
		                     "original_quantity": 2, "original_rate": 500,
		                     "stage_label": "Stage 1"}]):
			req.append("items", r)
		return req

	def test_validate_recomputes_row_amount(self):
		req = self._new_request(items=[{
			"description": _detail_name(),
			"quantity": 3, "rate": 250,
			"original_quantity": 3, "original_rate": 250,
			"stage_label": "Stage 1",
		}])
		req.insert(ignore_permissions=True)
		self.assertEqual(flt(req.items[0].amount), 750)

	def test_validate_recomputes_total_amount(self):
		req = self._new_request(items=[
			{"description": _detail_name(), "quantity": 2, "rate": 500,
			 "original_quantity": 2, "original_rate": 500, "stage_label": "Stage 1"},
			{"description": _detail_name(), "quantity": 1, "rate": 100,
			 "original_quantity": 1, "original_rate": 100, "stage_label": "Stage 1"},
		])
		req.insert(ignore_permissions=True)
		self.assertEqual(flt(req.total_amount), 1100)

	def test_submit_lifecycle(self):
		req = self._new_request()
		req.insert(ignore_permissions=True)
		self.assertEqual(req.docstatus, 0)
		req.submit()
		self.assertEqual(req.docstatus, 1)
		req.cancel()
		self.assertEqual(req.docstatus, 2)

	def test_doctype_field_metadata(self):
		meta = frappe.get_meta("Sub Contractor Payment Request")
		self.assertTrue(meta.is_submittable)
		for fieldname in ["naming_series", "date", "site", "project", "boq",
		                  "supplier", "items", "total_amount", "amended_from"]:
			self.assertIsNotNone(meta.get_field(fieldname), f"{fieldname} missing on parent")
		child_meta = frappe.get_meta("Sub Contractor Payment Request Item")
		for fieldname in ["stage_label", "description", "unit", "quantity", "rate",
		                  "amount", "original_quantity", "original_rate", "boq_item"]:
			self.assertIsNotNone(child_meta.get_field(fieldname), f"{fieldname} missing on child")
```

- [ ] **Step 4.5: Migrate to install both doctypes**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate
```
Expected: success; both doctypes (`Sub Contractor Payment Request`, `Sub Contractor Payment Request Item`) installed; `tabSub Contractor Payment Request` and `tabSub Contractor Payment Request Item` tables created.

- [ ] **Step 4.6: Run tests — expect pass**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.doctype.sub_contractor_payment_request.test_sub_contractor_payment_request
```
Expected: 4/4 pass.

- [ ] **Step 4.7: Commit**

```bash
git add dantata_town/dantata_town/doctype/sub_contractor_payment_request/
git commit -m "feat: add Sub Contractor Payment Request submittable parent doctype"
```

---

## Task 5: `make_request_from_boq` server method + tests

**Files:**
- Create: `dantata_town/dantata_town/sub_contractor.py`
- Modify: `dantata_town/dantata_town/tests/test_sub_contractor_flow.py`

- [ ] **Step 5.1: Append failing tests to `test_sub_contractor_flow.py`**

Append to the existing test file (at the bottom, after `TestSubContractorFieldsInstalled`):

```python
from frappe.utils import today, add_days, flt

from dantata_town.dantata_town.sub_contractor import (
	make_request_from_boq,
)


def _make_site_and_project_for_flow():
	create_boq_custom_fields()
	uom = frappe.db.get_value("UOM", {}, "name")
	item = frappe.db.get_value("Item", {"disabled": 0}, "name")
	customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
	company = frappe.db.get_single_value("Global Defaults", "default_company") \
		or frappe.db.get_value("Company", {}, "name")
	site = frappe.get_doc({
		"doctype": "Site",
		"site_name": f"Flow-Site-{frappe.generate_hash(length=6)}",
		"project_units": [{"building_type": item, "unit": 1, "uom": uom, "rate": 1}],
	}).insert(ignore_permissions=True)
	project = frappe.get_doc({
		"doctype": "Project",
		"project_name": f"Flow-Proj-{frappe.generate_hash(length=6)}",
		"customer": customer,
		"company": company,
		"site": site.name,
		"project_type": "Building",
		"project_subtype": "PLOT",
	}).insert(ignore_permissions=True)
	return site.name, project.name


def _detail_for_flow():
	existing = frappe.db.get_value("BOQ Item Detail", {}, "name")
	if existing:
		return existing
	return frappe.get_doc({
		"doctype": "BOQ Item Detail",
		"description": f"Detail-{frappe.generate_hash(length=6)}",
		"description_type": "Material",
		"unit": "Nos",
	}).insert(ignore_permissions=True).name


def _make_submitted_boq(site, project, sub_count=1, company_count=1, stage=1):
	"""Create + submit a BOQ with N sub-contractor rows and M company rows in stage."""
	stage_table = {
		1: "table_txao", 2: "description2", 3: "description3",
		4: "description4", 5: "description5", 6: "description6", 7: "description7",
	}[stage]
	detail = _detail_for_flow()
	doc = frappe.new_doc("Bill of Quantities")
	doc.site = site
	doc.project = project
	doc.date = today()
	for _ in range(sub_count):
		doc.append(stage_table, {
			"description": detail, "planned_quantity": 5, "rate": 1000,
			"assignment_type": "Sub Contractor",
		})
	for _ in range(company_count):
		doc.append(stage_table, {
			"description": detail, "planned_quantity": 5, "rate": 1000,
			"assignment_type": "Company",
		})
	doc.set(f"stage_{stage}_start_date", today())
	doc.set(f"stage_{stage}_end_date", add_days(today(), 10))
	doc.set(f"stage_{stage}", f"Test Stage {stage}")
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


class TestMakeRequestFromBOQ(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		self.supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")

	def test_creates_draft_request_with_snapshots(self):
		site, project = _make_site_and_project_for_flow()
		boq_name = _make_submitted_boq(site, project, sub_count=1, company_count=1)
		boq = frappe.get_doc("Bill of Quantities", boq_name)
		# Pick the Sub Contractor row from stage 1
		sub_row = next(r for r in boq.table_txao if r.assignment_type == "Sub Contractor")
		import json
		req_name = make_request_from_boq(
			boq=boq_name,
			supplier=self.supplier,
			date=today(),
			selected=json.dumps([{
				"stage_label": "Stage 1 — Test Stage 1",
				"boq_item_name": sub_row.name,
				"description": sub_row.description,
				"unit": sub_row.unit,
				"quantity": sub_row.planned_quantity,
				"rate": sub_row.rate,
			}]),
		)
		req = frappe.get_doc("Sub Contractor Payment Request", req_name)
		self.assertEqual(req.docstatus, 0)
		self.assertEqual(req.boq, boq_name)
		self.assertEqual(req.site, site)
		self.assertEqual(req.project, project)
		self.assertEqual(req.supplier, self.supplier)
		self.assertEqual(len(req.items), 1)
		row = req.items[0]
		self.assertEqual(flt(row.original_quantity), 5)
		self.assertEqual(flt(row.original_rate), 1000)
		self.assertEqual(flt(row.quantity), 5)
		self.assertEqual(flt(row.rate), 1000)
		self.assertEqual(row.boq_item, sub_row.name)

	def test_empty_selection_raises(self):
		import json
		site, project = _make_site_and_project_for_flow()
		boq_name = _make_submitted_boq(site, project)
		with self.assertRaises(frappe.ValidationError):
			make_request_from_boq(
				boq=boq_name, supplier=self.supplier, date=today(),
				selected=json.dumps([]),
			)

	def test_draft_boq_raises(self):
		import json
		site, project = _make_site_and_project_for_flow()
		# Create a BOQ but DON'T submit it
		stage_table = "table_txao"
		detail = _detail_for_flow()
		doc = frappe.new_doc("Bill of Quantities")
		doc.site = site
		doc.project = project
		doc.date = today()
		doc.append(stage_table, {
			"description": detail, "planned_quantity": 5, "rate": 1000,
			"assignment_type": "Sub Contractor",
		})
		doc.stage_1_start_date = today()
		doc.stage_1_end_date = add_days(today(), 10)
		doc.insert(ignore_permissions=True)  # docstatus = 0
		with self.assertRaises(frappe.ValidationError):
			make_request_from_boq(
				boq=doc.name, supplier=self.supplier, date=today(),
				selected=json.dumps([{
					"stage_label": "Stage 1",
					"boq_item_name": doc.table_txao[0].name,
					"description": detail,
					"unit": "Nos",
					"quantity": 1,
					"rate": 100,
				}]),
			)

	def test_unknown_boq_raises(self):
		import json
		with self.assertRaises(frappe.ValidationError):
			make_request_from_boq(
				boq="DOES-NOT-EXIST", supplier=self.supplier, date=today(),
				selected=json.dumps([{"stage_label": "X", "boq_item_name": "Y",
				                     "description": "Z", "unit": "Nos",
				                     "quantity": 1, "rate": 1}]),
			)
```

- [ ] **Step 5.2: Run tests — expect ImportError**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_sub_contractor_flow
```
Expected: failure on `from dantata_town.dantata_town.sub_contractor import make_request_from_boq` — module not found.

- [ ] **Step 5.3: Implement `sub_contractor.py`**

Create `dantata_town/dantata_town/sub_contractor.py`:

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def make_request_from_boq(boq: str, supplier: str, date: str, selected) -> str:
	"""Create a draft Sub Contractor Payment Request from selected BOQ rows.

	`selected` is a JSON-serialized list of dicts:
	  [{"stage_label", "boq_item_name", "description", "unit", "quantity", "rate"}]

	The original_quantity and original_rate fields are snapshotted at creation
	so the at-submit diff has stable reference values even if the source BOQ is
	later amended.
	"""
	if not frappe.db.exists("Bill of Quantities", boq):
		frappe.throw(_("BOQ {0} does not exist").format(boq))
	if frappe.db.get_value("Bill of Quantities", boq, "docstatus") != 1:
		frappe.throw(_(
			"BOQ {0} must be submitted before generating a payment request"
		).format(boq))

	rows = frappe.parse_json(selected) if isinstance(selected, str) else (selected or [])
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
			"stage_label": r.get("stage_label"),
			"description": r["description"],
			"unit": r.get("unit"),
			"quantity": flt(r["quantity"]),
			"rate": flt(r["rate"]),
			"original_quantity": flt(r["quantity"]),
			"original_rate": flt(r["rate"]),
			"boq_item": r.get("boq_item_name"),
		})
	req.insert(ignore_permissions=False)
	return req.name
```

- [ ] **Step 5.4: Run tests — expect pass**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_sub_contractor_flow
```
Expected: 4 (existing) + 4 (new) = 8 tests pass.

- [ ] **Step 5.5: Commit**

```bash
git add dantata_town/dantata_town/sub_contractor.py \
        dantata_town/dantata_town/tests/test_sub_contractor_flow.py
git commit -m "feat: sub_contractor.make_request_from_boq with snapshots"
```

---

## Task 6: BOQ form-script extension — modal picker

**Files:**
- Modify: `dantata_town/public/js/bill_of_quantities.js`

- [ ] **Step 6.1: Read current `bill_of_quantities.js`**

```bash
cat dantata_town/public/js/bill_of_quantities.js
```

- [ ] **Step 6.2: Append the new button + modal logic**

Add this block at the end of the file (after the existing `BOQ Items.completed` handler):

```javascript
// ---------------------------------------------------------------------------
// Sub Contractor Payment Request — modal picker on submitted BOQs.
// ---------------------------------------------------------------------------

frappe.ui.form.on("Bill of Quantities", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Create Sub Contractor Payment Request"), () => {
				open_sub_contractor_modal(frm);
			});
		}
	},
});

function open_sub_contractor_modal(frm) {
	const sub_rows = collect_sub_contractor_rows(frm);
	if (sub_rows.length === 0) {
		frappe.msgprint(__("No sub-contractor lines on this BOQ."));
		return;
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Create Sub Contractor Payment Request"),
		fields: [
			{
				fieldtype: "Link",
				fieldname: "supplier",
				label: __("Supplier"),
				options: "Supplier",
				reqd: 1,
			},
			{
				fieldtype: "Date",
				fieldname: "date",
				label: __("Date"),
				default: frappe.datetime.get_today(),
				reqd: 1,
			},
			{ fieldtype: "Section Break", label: __("Items") },
			{ fieldtype: "HTML", fieldname: "items_html" },
		],
		primary_action_label: __("Create"),
		primary_action: (values) => {
			const selected = collect_checked_rows(dialog, sub_rows);
			if (selected.length === 0) {
				frappe.msgprint(__("Select at least one item."));
				return;
			}
			frappe.call({
				method: "dantata_town.dantata_town.sub_contractor.make_request_from_boq",
				args: {
					boq: frm.doc.name,
					supplier: values.supplier,
					date: values.date,
					selected: JSON.stringify(selected),
				},
				freeze: true,
				freeze_message: __("Creating request..."),
				callback: (r) => {
					if (r.message) {
						dialog.hide();
						frappe.set_route("Form", "Sub Contractor Payment Request", r.message);
					}
				},
			});
		},
	});
	dialog.fields_dict.items_html.$wrapper.html(render_picker_grid(sub_rows));
	dialog.show();
}

function collect_sub_contractor_rows(frm) {
	const STAGE_TABLES = {
		1: "table_txao",
		2: "description2",
		3: "description3",
		4: "description4",
		5: "description5",
		6: "description6",
		7: "description7",
	};
	const out = [];
	for (const [stage_no, fieldname] of Object.entries(STAGE_TABLES)) {
		const stage_title = frm.doc[`stage_${stage_no}`] || "";
		const stage_label = stage_title
			? `Stage ${stage_no} — ${stage_title}`
			: `Stage ${stage_no}`;
		for (const row of frm.doc[fieldname] || []) {
			if (row.assignment_type === "Sub Contractor") {
				out.push({
					stage_label,
					boq_item_name: row.name,
					description: row.description,
					unit: row.unit || "",
					quantity: row.planned_quantity,
					rate: row.rate,
					amount: row.amount,
				});
			}
		}
	}
	return out;
}

function render_picker_grid(rows) {
	const fmt_money = (v) => format_currency(v);
	const lines = rows
		.map(
			(r, i) => `
			<tr>
				<td><input type="checkbox" data-idx="${i}" checked></td>
				<td>${frappe.utils.escape_html(r.stage_label)}</td>
				<td>${frappe.utils.escape_html(r.description)}</td>
				<td>${frappe.utils.escape_html(r.unit)}</td>
				<td class="text-right">${r.quantity}</td>
				<td class="text-right">${fmt_money(r.rate)}</td>
				<td class="text-right">${fmt_money(r.amount)}</td>
			</tr>`
		)
		.join("");
	return `
		<div class="table-responsive">
			<table class="table table-bordered scpr-picker">
				<thead>
					<tr>
						<th></th>
						<th>${__("Stage")}</th>
						<th>${__("Description")}</th>
						<th>${__("Unit")}</th>
						<th class="text-right">${__("Qty")}</th>
						<th class="text-right">${__("Rate")}</th>
						<th class="text-right">${__("Amount")}</th>
					</tr>
				</thead>
				<tbody>${lines}</tbody>
			</table>
		</div>
	`;
}

function collect_checked_rows(dialog, all_rows) {
	const checks = dialog.$wrapper.find(".scpr-picker input[type=checkbox]");
	const selected = [];
	checks.each(function () {
		if (this.checked) {
			const idx = parseInt($(this).data("idx"), 10);
			selected.push(all_rows[idx]);
		}
	});
	return selected;
}
```

- [ ] **Step 6.3: Clear cache so the new JS loads**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com clear-cache
```

- [ ] **Step 6.4: Verify JS parses**

```bash
node --check dantata_town/public/js/bill_of_quantities.js
```
Expected: exit 0.

- [ ] **Step 6.5: Manual browser smoke (user)**

User opens a submitted BOQ that has at least one Sub Contractor line; confirms:
- "Create Sub Contractor Payment Request" button appears.
- Modal lists only Sub Contractor lines, grouped by stage label, with checkboxes pre-checked.
- Picking Supplier + Date + clicking Create routes to a fresh draft request with the right rows.

(Implementer doesn't need to do this themselves; just clear-cache and commit.)

- [ ] **Step 6.6: Commit**

```bash
git add dantata_town/public/js/bill_of_quantities.js
git commit -m "feat: BOQ button + modal picker for Sub Contractor Payment Request"
```

---

## Task 7: `make_purchase_invoice` server method + tests

**Files:**
- Modify: `dantata_town/dantata_town/sub_contractor.py`
- Modify: `dantata_town/dantata_town/tests/test_sub_contractor_flow.py`

- [ ] **Step 7.1: Append failing tests to `test_sub_contractor_flow.py`**

Append a new class to `test_sub_contractor_flow.py`:

```python
from dantata_town.dantata_town.sub_contractor import (
	make_request_from_boq,
	make_purchase_invoice,
)


def _ensure_subcon_cost_item():
	if frappe.db.exists("Item", "Sub Contractor Cost"):
		return
	item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") \
		or frappe.db.get_value("Item Group", {}, "name")
	stock_uom = frappe.db.get_value("UOM", {"name": "Nos"}, "name") \
		or frappe.db.get_value("UOM", {}, "name")
	frappe.get_doc({
		"doctype": "Item",
		"item_code": "Sub Contractor Cost",
		"item_name": "Sub Contractor Cost",
		"item_group": item_group,
		"stock_uom": stock_uom,
		"is_stock_item": 0,
	}).insert(ignore_permissions=True)


def _set_site_expense_account(site):
	company = frappe.db.get_single_value("Global Defaults", "default_company") \
		or frappe.db.get_value("Company", {}, "name")
	expense = frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Expense Account", "is_group": 0},
		"name",
	) or frappe.db.get_value(
		"Account", {"company": company, "is_group": 0, "root_type": "Expense"}, "name"
	)
	frappe.db.set_value("Site", site, "expense_account", expense)
	return expense


def _make_approved_request(site, project, supplier):
	"""Build, submit, and return the name of a request.

	On dev sites without a Workflow installed, `workflow_state` is None on the
	submitted doc; the server-side `make_purchase_invoice` gate
	`if req.workflow_state and req.workflow_state != "Approved"` correctly
	treats None as "not blocked", so the PI gets created. Tests don't need to
	stage a workflow.
	"""
	import json
	boq = _make_submitted_boq(site, project, sub_count=1, company_count=0)
	sub_row = frappe.get_doc("Bill of Quantities", boq).table_txao[0]
	req_name = make_request_from_boq(
		boq=boq, supplier=supplier, date=today(),
		selected=json.dumps([{
			"stage_label": "Stage 1",
			"boq_item_name": sub_row.name,
			"description": sub_row.description,
			"unit": sub_row.unit,
			"quantity": sub_row.planned_quantity,
			"rate": sub_row.rate,
		}]),
	)
	req = frappe.get_doc("Sub Contractor Payment Request", req_name)
	req.submit()
	return req.name


class TestMakePurchaseInvoice(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		_ensure_subcon_cost_item()
		self.supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")

	def test_creates_draft_pi_with_correct_fields(self):
		site, project = _make_site_and_project_for_flow()
		_set_site_expense_account(site)
		req_name = _make_approved_request(site, project, self.supplier)
		pi_name = make_purchase_invoice(req_name)
		pi = frappe.get_doc("Purchase Invoice", pi_name)
		self.assertEqual(pi.docstatus, 0)
		self.assertEqual(pi.supplier, self.supplier)
		self.assertEqual(pi.site, site)
		self.assertEqual(pi.sub_contractor_payment_request, req_name)
		self.assertEqual(len(pi.items), 1)
		row = pi.items[0]
		self.assertEqual(row.item_code, "Sub Contractor Cost")
		self.assertEqual(flt(row.qty), 1)
		self.assertEqual(flt(row.rate), 5000)  # 5 × 1000 from the source BOQ row
		self.assertEqual(row.project, project)

	def test_missing_expense_account_errors(self):
		site, project = _make_site_and_project_for_flow()
		# Deliberately do NOT set expense_account on the Site
		req_name = _make_approved_request(site, project, self.supplier)
		with self.assertRaises(frappe.ValidationError):
			make_purchase_invoice(req_name)

	def test_missing_subcon_cost_item_errors(self):
		# Delete the Item; FrappeTestCase's transactional rollback restores it
		# at the end of the test. If the delete itself fails on this dev site
		# (e.g., ledger entries reference the item from a prior unrelated
		# session), skipTest with the reason — this is environment, not logic.
		site, project = _make_site_and_project_for_flow()
		_set_site_expense_account(site)
		req_name = _make_approved_request(site, project, self.supplier)
		try:
			frappe.delete_doc("Item", "Sub Contractor Cost",
			                  ignore_permissions=True, force=True)
		except Exception as e:
			self.skipTest(f"Cannot delete Sub Contractor Cost item on this site: {e}")
		with self.assertRaises(frappe.ValidationError):
			make_purchase_invoice(req_name)

	def test_draft_request_errors(self):
		import json
		site, project = _make_site_and_project_for_flow()
		_set_site_expense_account(site)
		boq = _make_submitted_boq(site, project, sub_count=1, company_count=0)
		sub_row = frappe.get_doc("Bill of Quantities", boq).table_txao[0]
		req_name = make_request_from_boq(
			boq=boq, supplier=self.supplier, date=today(),
			selected=json.dumps([{
				"stage_label": "Stage 1",
				"boq_item_name": sub_row.name,
				"description": sub_row.description,
				"unit": sub_row.unit,
				"quantity": sub_row.planned_quantity,
				"rate": sub_row.rate,
			}]),
		)
		# Do NOT submit; leave as draft (docstatus = 0).
		with self.assertRaises(frappe.ValidationError):
			make_purchase_invoice(req_name)

	def test_pi_submit_increases_project_expenses(self):
		"""Regression: the Spec 1 hooks pick up the generated PI's contribution."""
		site, project = _make_site_and_project_for_flow()
		_set_site_expense_account(site)
		req_name = _make_approved_request(site, project, self.supplier)
		pi_name = make_purchase_invoice(req_name)
		pi = frappe.get_doc("Purchase Invoice", pi_name)
		# Fill anything else PI submit needs (cost_center / company already set
		# by set_missing_values).
		company = pi.company
		if not pi.due_date:
			pi.due_date = add_days(today(), 30)
		if not pi.bill_no:
			pi.bill_no = frappe.generate_hash(length=6)
			pi.bill_date = today()
		pi.items[0].cost_center = frappe.db.get_value(
			"Cost Center", {"company": company, "is_group": 0}, "name"
		)
		pi.save(ignore_permissions=True)
		pi.submit()
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_expenses")),
			5000,
		)
```

- [ ] **Step 7.2: Run tests — expect ImportError**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_sub_contractor_flow
```
Expected: failure on `from dantata_town.dantata_town.sub_contractor import make_purchase_invoice`.

- [ ] **Step 7.3: Implement `make_purchase_invoice` in `sub_contractor.py`**

Append to `dantata_town/dantata_town/sub_contractor.py`:

```python
from frappe.utils import today, add_days


@frappe.whitelist()
def make_purchase_invoice(request_name: str) -> str:
	"""Create a draft Purchase Invoice from an approved Sub Contractor Payment Request.

	Validates:
	- request is submitted (docstatus = 1)
	- workflow_state is "Approved" (when set; tests with no workflow leave it empty)
	- Site has an expense_account configured
	- "Sub Contractor Cost" Item exists

	Returns the name of the created (draft) Purchase Invoice.
	"""
	if not frappe.db.exists("Sub Contractor Payment Request", request_name):
		frappe.throw(_("Sub Contractor Payment Request {0} does not exist").format(request_name))

	req = frappe.get_doc("Sub Contractor Payment Request", request_name)

	if req.docstatus != 1:
		frappe.throw(_("Request must be submitted to create a Purchase Invoice"))

	if req.workflow_state and req.workflow_state != "Approved":
		frappe.throw(_(
			"Request must be in Approved state to create a Purchase Invoice "
			"(currently {0})"
		).format(req.workflow_state))

	expense_account = frappe.db.get_value("Site", req.site, "expense_account")
	if not expense_account:
		frappe.throw(_(
			"Set Expense Account on Site '{0}' before creating a Purchase Invoice"
		).format(req.site))

	if not frappe.db.exists("Item", "Sub Contractor Cost"):
		frappe.throw(_(
			"Create an Item named 'Sub Contractor Cost' before using this feature"
		))

	pi = frappe.new_doc("Purchase Invoice")
	pi.supplier = req.supplier
	pi.posting_date = today()
	pi.due_date = add_days(today(), 30)
	pi.site = req.site
	pi.sub_contractor_payment_request = req.name
	pi.append("items", {
		"item_code": "Sub Contractor Cost",
		"qty": 1,
		"rate": flt(req.total_amount),
		"project": req.project,
		"expense_account": expense_account,
	})
	pi.set_missing_values()
	pi.insert(ignore_permissions=False)
	return pi.name
```

- [ ] **Step 7.4: Run tests — expect pass**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_sub_contractor_flow
```
Expected: 4 (existing field tests) + 4 (Task 5 tests) + 5 (new) = 13 tests pass (or 12 pass + 1 skip if `test_missing_subcon_cost_item_errors` cannot delete the Item on this dev site). If `test_pi_submit_increases_project_expenses` fails because of cost-center / account chain issues on the dev site, mirror the workaround pattern from `test_project_aggregations.py` (see `_submit_purchase_invoice` in that file for the standard PI-submit fields the dev site needs).

- [ ] **Step 7.5: Commit**

```bash
git add dantata_town/dantata_town/sub_contractor.py \
        dantata_town/dantata_town/tests/test_sub_contractor_flow.py
git commit -m "feat: sub_contractor.make_purchase_invoice with workflow_state gate"
```

---

## Task 8: Sub Contractor Payment Request form script — diff prompt + PI button

**Files:**
- Create: `dantata_town/dantata_town/doctype/sub_contractor_payment_request/sub_contractor_payment_request.js`

- [ ] **Step 8.1: Create the form script**

Create `dantata_town/dantata_town/doctype/sub_contractor_payment_request/sub_contractor_payment_request.js`:

```javascript
// Copyright (c) 2026, Montego-arch and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sub Contractor Payment Request", {
	refresh(frm) {
		set_pi_button(frm);
	},

	before_submit(frm) {
		const diffs = collect_row_diffs(frm.doc);
		if (diffs.length === 0) return;
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

frappe.ui.form.on("Sub Contractor Payment Request Item", {
	quantity(frm, cdt, cdn) {
		recalc_amount(frm, cdt, cdn);
	},
	rate(frm, cdt, cdn) {
		recalc_amount(frm, cdt, cdn);
	},
});

function recalc_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const amount = flt(row.quantity) * flt(row.rate);
	frappe.model.set_value(cdt, cdn, "amount", amount);
	const total = (frm.doc.items || []).reduce(
		(s, r) => s + flt(r.amount), 0
	);
	frm.set_value("total_amount", total);
}

function set_pi_button(frm) {
	if (frm.doc.docstatus !== 1) return;
	if (frm.doc.workflow_state && frm.doc.workflow_state !== "Approved") return;
	if (!frm.doc.workflow_state) {
		// No workflow installed → still allow PI creation only when explicitly Approved
		// is set, or fall back to docstatus=1. For production sites, the workflow
		// will populate workflow_state. For dev/test sites without a workflow, the
		// button is hidden by default to avoid bypassing the gate accidentally.
		return;
	}
	frm.add_custom_button(__("Create Purchase Invoice"), () => create_pi(frm));
}

function create_pi(frm) {
	frappe.call({
		method: "dantata_town.dantata_town.sub_contractor.make_purchase_invoice",
		args: { request_name: frm.doc.name },
		freeze: true,
		freeze_message: __("Creating Purchase Invoice..."),
		callback: (r) => {
			if (r.message) {
				frappe.set_route("Form", "Purchase Invoice", r.message);
			}
		},
	});
}

function collect_row_diffs(doc) {
	const diffs = [];
	for (const row of doc.items || []) {
		const orig_q = flt(row.original_quantity);
		const orig_r = flt(row.original_rate);
		const new_q = flt(row.quantity);
		const new_r = flt(row.rate);
		const qty_changed = orig_q !== new_q
			? { from: orig_q, to: new_q }
			: null;
		const rate_changed = orig_r !== new_r
			? { from: orig_r, to: new_r }
			: null;
		if (qty_changed || rate_changed) {
			diffs.push({
				stage_label: row.stage_label || "",
				description: row.description || "",
				qty_changed,
				rate_changed,
			});
		}
	}
	return diffs;
}

function render_diff_html(diffs) {
	const fmt = (v) => format_currency(v);
	const lines = diffs
		.map((d) => {
			const parts = [];
			if (d.qty_changed) {
				parts.push(`Qty ${d.qty_changed.from} → ${d.qty_changed.to}`);
			}
			if (d.rate_changed) {
				parts.push(
					`Rate ${fmt(d.rate_changed.from)} → ${fmt(d.rate_changed.to)}`
				);
			}
			return `
				<tr>
					<td>${frappe.utils.escape_html(d.stage_label)}</td>
					<td>${frappe.utils.escape_html(d.description)}</td>
					<td>${parts.join("<br>")}</td>
				</tr>`;
		})
		.join("");
	return `
		<p>${__("These rows changed since the request was generated:")}</p>
		<div class="table-responsive">
			<table class="table table-bordered">
				<thead>
					<tr>
						<th>${__("Stage")}</th>
						<th>${__("Description")}</th>
						<th>${__("Changes")}</th>
					</tr>
				</thead>
				<tbody>${lines}</tbody>
			</table>
		</div>
	`;
}
```

- [ ] **Step 8.2: Verify JS parses**

```bash
node --check dantata_town/dantata_town/doctype/sub_contractor_payment_request/sub_contractor_payment_request.js
```
Expected: exit 0.

- [ ] **Step 8.3: Clear cache**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com clear-cache
```

- [ ] **Step 8.4: Manual browser smoke (user)**

User opens a draft Sub Contractor Payment Request, edits qty on one row, hits Submit:
- Diff modal appears listing the change.
- Cancel → submit blocked, doc still draft, edit preserved.
- Submit again → Proceed → request submits.
- After approval (manually setting `workflow_state = "Approved"` via Console for dev sites without workflow), "Create Purchase Invoice" button appears and creates a draft PI.

- [ ] **Step 8.5: Commit**

```bash
git add dantata_town/dantata_town/doctype/sub_contractor_payment_request/sub_contractor_payment_request.js
git commit -m "feat: Sub Contractor Payment Request form script (diff prompt + PI button)"
```

---

## Task 9: Final verification

**Files:** none changed; verification only.

- [ ] **Step 9.1: Confirm clean working tree**

```bash
git status
git log --oneline -10
```
Expected: clean tree (only the pre-existing `print_format/` untracked dir), 9 implementation commits since `7b2a113`.

- [ ] **Step 9.2: Run all dantata_town test modules**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_sub_contractor_flow
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.doctype.sub_contractor_payment_request.test_sub_contractor_payment_request
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_project_aggregations
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_boq_progress
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_rename_project_unit_item_fields
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_project_type_setup
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_quotation_installments
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_allocation_letter
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_customer_payment_report
```
Expected: all pass; no regressions.

- [ ] **Step 9.3: Sanity check the new doctypes are installed**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com mariadb -e "SELECT name, is_submittable, istable FROM \`tabDocType\` WHERE name IN ('Sub Contractor Payment Request', 'Sub Contractor Payment Request Item')" 2>/dev/null
```
Expected: 2 rows. Sub Contractor Payment Request: is_submittable=1, istable=0. Sub Contractor Payment Request Item: is_submittable=0, istable=1.

- [ ] **Step 9.4: Sanity check custom fields**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com mariadb -e "SELECT dt, fieldname, fieldtype FROM \`tabCustom Field\` WHERE (dt='BOQ Items' AND fieldname='assignment_type') OR (dt='Purchase Invoice' AND fieldname IN ('site', 'sub_contractor_payment_request')) ORDER BY dt, fieldname" 2>/dev/null
```
Expected: 3 rows.

- [ ] **Step 9.5: Manual verification (user)**

User exercises the full flow in the browser:

1. **Site `expense_account`**: open a Site → "Expense Account" field visible → set to a valid Account.
2. **BOQ assignment_type**: open a BOQ → in any stage's items table → "Assignment Type" column shows with default "Company"; switch one row to "Sub Contractor"; save and submit.
3. **BOQ button + modal**: on the submitted BOQ, click "Create Sub Contractor Payment Request" → modal lists only Sub Contractor lines → pick supplier, click Create → routed to draft request.
4. **Diff prompt**: edit a qty on the request → click Submit → modal lists the diff → Cancel → still draft → Submit again → Proceed → submits.
5. **PI button**: with workflow installed, transition request to Approved (via workflow action) → "Create Purchase Invoice" appears → click → routed to draft PI with: supplier set, items[0] = (Sub Contractor Cost, qty=1, rate=total_amount, project=request.project, expense_account=Site.expense_account), parent.site = request.site.
6. **Spec 1 regression**: submit the PI → on the project, `Project Expenses` increases by total_amount.
7. **Workflow setup (admin one-time)**: per spec Section 6, create role `Sub Contractor Approver`, create a Workflow on `Sub Contractor Payment Request` with the 5 states (Draft, Pending Approval, Approved, Rejected, Paid) and 4 transitions.

---

## Spec coverage check

| Spec section | Implemented by |
|--------------|----------------|
| 1. Site `expense_account` | Task 1 |
| 1. BOQ Items `assignment_type` | Task 2 |
| 2. Sub Contractor Payment Request Item child | Task 3 |
| 2. Sub Contractor Payment Request parent + controller | Task 4 |
| 3. BOQ modal picker form-script | Task 6 |
| 3. `make_request_from_boq` server method | Task 5 |
| 4. At-submit diff prompt (form script) | Task 8 |
| 4. Live amount/total recompute (UX) | Task 8 |
| 5. PI custom fields (`site`, `sub_contractor_payment_request`) | Task 2 |
| 5. `make_purchase_invoice` server method | Task 7 |
| 5. PI button (form script) | Task 8 |
| 6. Workflow shape | Documented in spec; admin-managed; Task 9 manual setup |
| 7. Code organization | Tasks 3–8 |
| 7. Migration | All tasks via `bench migrate` after each |
| 8. Doctype tests | Task 4 |
| 8. Cross-cutting flow tests | Tasks 2, 5, 7 |
| 8. Manual verification | Task 9 |

No spec requirements are missing.

---

## Risks during execution

- **PI submit dev-site fixture chain**: tests in `test_pi_submit_increases_project_expenses` need the same chain of accounts/cost centers that `test_project_aggregations._submit_purchase_invoice` sets up. The plan reuses that pattern; if the dev site has additional mandatory custom fields on PI (e.g., `matter_id`-like quirks similar to Expense Claim), the implementer may need to set them via `frappe.db.set_value` before submit, or `skipTest` if they're environment-specific. Flag in DONE_WITH_CONCERNS if so.
- **`workflow_state` field**: Frappe creates this field only when a Workflow record exists. Tests intentionally avoid setting `workflow_state`; on a dev site without a workflow installed, the server method's `if req.workflow_state and req.workflow_state != "Approved"` correctly treats `None` as "not blocked", so PI creation succeeds in tests. The Approved-state gate is exercised manually on production sites where the admin has installed the workflow (Section 9 manual checklist).
- **`Sub Contractor Cost` Item creation in tests**: `_ensure_subcon_cost_item()` creates the item once and leaves it. Transactional rollback should clean it up; if it persists across test runs, the second run's `frappe.db.exists` check will short-circuit safely.
- **`set_missing_values` on PI**: ERPNext's `set_missing_values` may overwrite `pi.due_date`, `pi.posting_date` etc. with company defaults. The plan sets these explicitly before/after as needed; `set_missing_values` for new docs is generally idempotent.
- **`bench migrate` between Task 3 and Task 4**: Task 3 creates the child doctype but not the parent. The parent in Task 4 references the child via `options: "Sub Contractor Payment Request Item"`. We deliberately don't migrate after Task 3 — the parent's reference resolves cleanly only after both JSONs are in place. The plan migrates once after Task 4.
- **JS escape**: the modal HTML uses `frappe.utils.escape_html` for user-supplied values (description, stage_label) — guards against XSS if a user types HTML into a BOQ Item Detail description.
