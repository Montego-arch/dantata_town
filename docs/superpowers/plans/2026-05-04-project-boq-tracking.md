# Project & BOQ Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface real cost/revenue totals on Project and per-stage progress tracking on BOQ, plus rename Project Unit Item fields to match construction terminology.

**Architecture:** Custom fields registered in `setup.py` (idempotent on every `bench migrate`); Python aggregation logic split into focused modules (`project_aggregations.py`, `boq_progress.py`); doc-event hooks recalculate totals on submit/cancel of Purchase Invoice / Expense Claim / Journal Entry / Payment Entry; BOQ stage progress derived count-based from a new `completed` checkbox on `BOQ Items`; rename of `Project Unit Item.unit_type` → `building_type` and `projected_quantity` → `unit` performed by an idempotent SQL patch.

**Tech Stack:** Frappe v15 / ERPNext, Python 3.11, MariaDB, Frappe form-script (vanilla JS), `frappe.tests.utils.FrappeTestCase`.

**Spec:** `docs/superpowers/specs/2026-05-04-project-boq-tracking-design.md`

---

## File Structure

**Created files:**
```
dantata_town/dantata_town/project_aggregations.py
dantata_town/dantata_town/boq_progress.py
dantata_town/patches/__init__.py
dantata_town/patches/rename_project_unit_item_fields.py
dantata_town/public/js/bill_of_quantities.js
dantata_town/dantata_town/tests/test_project_aggregations.py
dantata_town/dantata_town/tests/test_boq_progress.py
dantata_town/dantata_town/tests/test_rename_project_unit_item_fields.py
```

**Modified files:**
```
dantata_town/dantata_town/setup.py                                     # extend create_boq_custom_fields
dantata_town/dantata_town/doctype/project_unit_item/project_unit_item.json
dantata_town/hooks.py                                                  # +doc_events + doctype_js
dantata_town/public/js/project.js                                      # building_type set_query
dantata_town/patches.txt                                               # register patch
```

**Module responsibilities:**
- `project_aggregations.py` — `recalc_project_totals(project)`, `recalc_for_doc(doc, method)`, `_projects_touched_by(doc)`, `_sum_*` helpers, whitelisted `get_site_building_types`.
- `boq_progress.py` — `validate_stage_dates(doc, method)`, `recalc_boq_progress(doc, method)`, `STAGE_TABLES` map.
- `setup.py` — extends existing `create_boq_custom_fields()` to register the new Project / BOQ / BOQ Items fields and property setters. Function name kept (consider rename in a follow-up).
- `bill_of_quantities.js` — purely UX (live recompute); server-side `validate` is the source of truth.

---

## Pre-flight

- [ ] **Step 0.1: Confirm clean working tree on `develop`**

```bash
git status
git log --oneline -3
```
Expected: `working tree clean`, latest commit is `9ec712e docs: design spec for project & BOQ tracking enhancements`.

- [ ] **Step 0.2: Confirm bench is reachable and tests can run**

Frappe app tests are run from the bench directory, not the app directory. Path:
```
/home/okeke/clients/graceco/frappe-bench
```
Verify:
```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com list-apps
```
Expected: dantata_town listed. (If a different site name is used in this dev env, substitute it in every `bench --site` command below.)

---

## Task 1: Site rename — doctype JSON

**Files:**
- Modify: `dantata_town/dantata_town/doctype/project_unit_item/project_unit_item.json`

- [ ] **Step 1.1: Read current JSON**

```bash
cat dantata_town/dantata_town/doctype/project_unit_item/project_unit_item.json
```
Confirm two fields to rename: `unit_type` (Link, label "Unit Type") and `projected_quantity` (Float, label "Projected Quantity").

- [ ] **Step 1.2: Edit `project_unit_item.json`**

Change `field_order` from `["unit_type", "projected_quantity", "column_break_lomr", "uom", "rate", "amount"]` to `["building_type", "unit", "column_break_lomr", "uom", "rate", "amount"]`.

Replace the `unit_type` field block with:
```json
{
 "columns": 3,
 "fieldname": "building_type",
 "fieldtype": "Link",
 "in_list_view": 1,
 "label": "Building Type",
 "options": "Item"
}
```

Replace the `projected_quantity` field block with:
```json
{
 "columns": 2,
 "fieldname": "unit",
 "fieldtype": "Float",
 "in_list_view": 1,
 "label": "Unit"
}
```

- [ ] **Step 1.3: Validate JSON parses**

```bash
python -c "import json; json.load(open('dantata_town/dantata_town/doctype/project_unit_item/project_unit_item.json'))"
```
Expected: no output, exit 0.

- [ ] **Step 1.4: Commit**

```bash
git add dantata_town/dantata_town/doctype/project_unit_item/project_unit_item.json
git commit -m "refactor: rename Project Unit Item fields (unit_type→building_type, projected_quantity→unit)"
```

---

## Task 2: Site rename — migration patch

**Files:**
- Create: `dantata_town/patches/__init__.py`
- Create: `dantata_town/patches/rename_project_unit_item_fields.py`
- Create: `dantata_town/dantata_town/tests/test_rename_project_unit_item_fields.py`
- Modify: `dantata_town/patches.txt`

- [ ] **Step 2.1: Write failing patch test**

Create `dantata_town/dantata_town/tests/test_rename_project_unit_item_fields.py`:
```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from dantata_town.patches.rename_project_unit_item_fields import execute as run_patch


class TestRenameProjectUnitItemFields(FrappeTestCase):
	def test_patch_is_idempotent(self):
		run_patch()
		run_patch()
		cols = frappe.db.get_table_columns("Project Unit Item")
		self.assertIn("building_type", cols)
		self.assertIn("unit", cols)
		self.assertNotIn("unit_type", cols)
		self.assertNotIn("projected_quantity", cols)

	def test_patch_preserves_data(self):
		"""If a row exists with new fieldnames, patch is a no-op and data survives."""
		site_name = frappe.generate_hash(length=8)
		site = frappe.get_doc({
			"doctype": "Site",
			"site_name": f"Test-{site_name}",
			"project_units": [{
				"building_type": frappe.db.get_value("Item", {"disabled": 0}, "name"),
				"unit": 7,
				"uom": frappe.db.get_value("UOM", {"name": "Nos"}) or frappe.db.get_value("UOM", {}, "name"),
				"rate": 1000,
			}],
		}).insert(ignore_permissions=True)

		run_patch()

		reloaded = frappe.get_doc("Site", site.name)
		self.assertEqual(reloaded.project_units[0].unit, 7)
		self.assertTrue(reloaded.project_units[0].building_type)
```

- [ ] **Step 2.2: Run test — expect ImportError or ModuleNotFoundError**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_rename_project_unit_item_fields
```
Expected: failure on `from dantata_town.patches.rename_project_unit_item_fields import execute` because the module doesn't exist yet.

- [ ] **Step 2.3: Create patches package**

Create `dantata_town/patches/__init__.py` as an empty file:
```python
```

- [ ] **Step 2.4: Implement the patch**

Create `dantata_town/patches/rename_project_unit_item_fields.py`:
```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.model.rename_field import rename_field


def execute():
	"""Rename Project Unit Item fields to match construction terminology.

	unit_type -> building_type
	projected_quantity -> unit

	Idempotent: guarded by column-existence checks.
	"""
	cols = frappe.db.get_table_columns("Project Unit Item")
	if "unit_type" in cols and "building_type" not in cols:
		rename_field("Project Unit Item", "unit_type", "building_type")
	if "projected_quantity" in cols and "unit" not in cols:
		rename_field("Project Unit Item", "projected_quantity", "unit")

	frappe.clear_cache(doctype="Project Unit Item")
	frappe.clear_cache(doctype="Site")
```

- [ ] **Step 2.5: Register patch in `patches.txt`**

Append to `dantata_town/patches.txt` under `[post_model_sync]`:
```
dantata_town.patches.rename_project_unit_item_fields
```

- [ ] **Step 2.6: Run the patch once against the dev site**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate
```
Expected: migrate runs, the new patch executes, no errors. (If the site already had data on the old fieldnames, those rows now read under the new fieldnames.)

- [ ] **Step 2.7: Run tests — expect pass**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_rename_project_unit_item_fields
```
Expected: 2 tests pass.

- [ ] **Step 2.8: Commit**

```bash
git add dantata_town/patches/__init__.py \
        dantata_town/patches/rename_project_unit_item_fields.py \
        dantata_town/patches.txt \
        dantata_town/dantata_town/tests/test_rename_project_unit_item_fields.py
git commit -m "feat: idempotent patch renaming Project Unit Item fields"
```

---

## Task 3: Register Project custom fields & property setters

Adds `building_type`, `dt_financials_section`, `project_expenses`, `dt_financials_col`, `project_payment` on Project; surfaces and relabels `total_sales_amount`.

**Files:**
- Modify: `dantata_town/dantata_town/setup.py`
- Create: `dantata_town/dantata_town/tests/test_project_aggregations.py` (just the field-existence tests for now; runtime tests added in Task 5)

- [ ] **Step 3.1: Write failing field-existence tests**

Create `dantata_town/dantata_town/tests/test_project_aggregations.py`:
```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from dantata_town.dantata_town.setup import create_boq_custom_fields


class TestProjectFinancialFields(FrappeTestCase):
	def test_building_type_field_exists_on_project(self):
		create_boq_custom_fields()
		field = frappe.db.get_value(
			"Custom Field",
			{"dt": "Project", "fieldname": "building_type"},
			["fieldtype", "options", "depends_on"],
			as_dict=True,
		)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "Item")
		self.assertEqual(field.depends_on, "eval:doc.site")

	def test_financials_fields_exist_on_project(self):
		create_boq_custom_fields()
		for fieldname, fieldtype in [
			("dt_financials_section", "Section Break"),
			("project_expenses", "Currency"),
			("dt_financials_col", "Column Break"),
			("project_payment", "Currency"),
		]:
			field = frappe.db.get_value(
				"Custom Field",
				{"dt": "Project", "fieldname": fieldname},
				["fieldtype", "read_only"],
				as_dict=True,
			)
			self.assertIsNotNone(field, f"{fieldname} not found")
			self.assertEqual(field.fieldtype, fieldtype)
			if fieldtype == "Currency":
				self.assertEqual(field.read_only, 1)

	def test_total_sales_amount_relabeled_and_unhidden(self):
		create_boq_custom_fields()
		label = frappe.db.get_value(
			"Property Setter",
			{"doc_type": "Project", "field_name": "total_sales_amount", "property": "label"},
			"value",
		)
		hidden = frappe.db.get_value(
			"Property Setter",
			{"doc_type": "Project", "field_name": "total_sales_amount", "property": "hidden"},
			"value",
		)
		self.assertEqual(label, "Sales Order Amount")
		self.assertEqual(hidden, "0")
```

- [ ] **Step 3.2: Run tests — expect failures**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_project_aggregations
```
Expected: 3 failures — `building_type`, `dt_financials_section` etc., and the property setters not present.

- [ ] **Step 3.3: Extend `setup.py` — Project custom fields**

In `dantata_town/dantata_town/setup.py`, in `_create_custom_fields()`, append to the `Project` entry (after the existing `site` and `project_subtype` dicts):

```python
		"Project": [
			# ... existing site and project_subtype entries unchanged ...
			{
				"fieldname": "building_type",
				"fieldtype": "Link",
				"label": "Building Type",
				"options": "Item",
				"insert_after": "site",
				"depends_on": "eval:doc.site",
				"module": "Dantata Town",
			},
			{
				"fieldname": "dt_financials_section",
				"fieldtype": "Section Break",
				"label": "Financials",
				"insert_after": "project_subtype",
				"module": "Dantata Town",
			},
			{
				"fieldname": "project_expenses",
				"fieldtype": "Currency",
				"label": "Project Expenses",
				"insert_after": "dt_financials_section",
				"read_only": 1,
				"module": "Dantata Town",
			},
			{
				"fieldname": "dt_financials_col",
				"fieldtype": "Column Break",
				"insert_after": "project_expenses",
				"module": "Dantata Town",
			},
			{
				"fieldname": "project_payment",
				"fieldtype": "Currency",
				"label": "Project Payment",
				"insert_after": "dt_financials_col",
				"read_only": 1,
				"module": "Dantata Town",
			},
		],
```

- [ ] **Step 3.4: Extend `_create_property_setters()`**

In the same file, append to the `property_setters` list:
```python
		("Project", "total_sales_amount", "hidden", "0", "Check"),
		("Project", "total_sales_amount", "label", "Sales Order Amount", "Data"),
```

- [ ] **Step 3.5: Run install hook against the dev site**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate
```
Expected: success; the new fields and property setters are created.

- [ ] **Step 3.6: Run tests — expect pass**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_project_aggregations
```
Expected: 3 tests pass.

- [ ] **Step 3.7: Commit**

```bash
git add dantata_town/dantata_town/setup.py \
        dantata_town/dantata_town/tests/test_project_aggregations.py
git commit -m "feat: register Project building_type and Financials custom fields"
```

---

## Task 4: `project_aggregations.py` — recalc_project_totals + helpers

Pure-Python summation logic. No hooks wired yet; that's Task 5.

**Files:**
- Create: `dantata_town/dantata_town/project_aggregations.py`
- Modify: `dantata_town/dantata_town/tests/test_project_aggregations.py`

- [ ] **Step 4.1: Write failing tests for `recalc_project_totals`**

Append to `test_project_aggregations.py`:
```python
from dantata_town.dantata_town.project_aggregations import (
	recalc_project_totals,
	recalc_for_doc,
)
from dantata_town.dantata_town.setup import create_boq_custom_fields


def _make_site_and_project():
	"""Create a minimal Site + Project pair, return their names."""
	create_boq_custom_fields()
	uom = frappe.db.get_value("UOM", {}, "name")
	item = frappe.db.get_value("Item", {"disabled": 0, "is_sales_item": 1}, "name") \
	       or frappe.db.get_value("Item", {"disabled": 0}, "name")
	customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")

	site = frappe.get_doc({
		"doctype": "Site",
		"site_name": f"AggSite-{frappe.generate_hash(length=6)}",
		"project_units": [{"building_type": item, "unit": 1, "uom": uom, "rate": 1}],
	}).insert(ignore_permissions=True)

	project = frappe.get_doc({
		"doctype": "Project",
		"project_name": f"AggProj-{frappe.generate_hash(length=6)}",
		"customer": customer,
		"site": site.name,
		"project_type": "Building",
		"project_subtype": "PLOT",
	}).insert(ignore_permissions=True)
	return site.name, project.name


class TestRecalcProjectTotals(FrappeTestCase):
	def test_no_documents_yields_zero(self):
		_, project = _make_site_and_project()
		recalc_project_totals(project)
		expenses = frappe.db.get_value("Project", project, "project_expenses")
		payment = frappe.db.get_value("Project", project, "project_payment")
		self.assertEqual(expenses, 0)
		self.assertEqual(payment, 0)

	def test_unknown_project_is_noop(self):
		recalc_project_totals(None)  # must not raise
		recalc_project_totals("DOES-NOT-EXIST")  # must not raise; just a no-op or write to nothing
```

- [ ] **Step 4.2: Run tests — expect ImportError**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_project_aggregations
```
Expected: failure on `from dantata_town.dantata_town.project_aggregations import recalc_project_totals` — module not found.

- [ ] **Step 4.3: Implement `project_aggregations.py`**

Create `dantata_town/dantata_town/project_aggregations.py`:
```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

from typing import Iterable

import frappe
from frappe.utils import flt


def recalc_project_totals(project: str | None) -> None:
	"""Recompute project_expenses and project_payment from submitted docs.

	Re-sums from docstatus=1 rows so cancellation/amendment is naturally consistent.
	No-op if project is falsy or does not exist.
	"""
	if not project:
		return
	if not frappe.db.exists("Project", project):
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
		"Project",
		project,
		{"project_expenses": expenses, "project_payment": payment},
		update_modified=False,
	)


def recalc_for_doc(doc, method=None) -> None:
	"""Doc-event hook entrypoint. Recalculates each Project the doc touches."""
	for project in _projects_touched_by(doc):
		recalc_project_totals(project)


def _projects_touched_by(doc) -> Iterable[str]:
	"""Return the unique set of Project names linked from `doc`.

	Different shape per doctype:
	- Purchase Invoice: items[].project
	- Expense Claim: parent.project
	- Journal Entry: accounts[].project
	- Payment Entry: references[] -> resolve project from the referenced Sales Invoice / Purchase Invoice
	"""
	projects: set[str] = set()
	dt = doc.doctype

	if dt == "Purchase Invoice":
		for row in doc.get("items") or []:
			if row.get("project"):
				projects.add(row.project)
	elif dt == "Expense Claim":
		if doc.get("project"):
			projects.add(doc.project)
	elif dt == "Journal Entry":
		for row in doc.get("accounts") or []:
			if row.get("project"):
				projects.add(row.project)
	elif dt == "Payment Entry":
		# Direct project field if present on the Payment Entry parent
		if doc.get("project"):
			projects.add(doc.project)
		# Resolve via referenced invoices
		for row in doc.get("references") or []:
			ref_dt = row.get("reference_doctype")
			ref_name = row.get("reference_name")
			if not ref_dt or not ref_name:
				continue
			project = frappe.db.get_value(ref_dt, ref_name, "project")
			if project:
				projects.add(project)
	return projects


def _sum_purchase_invoice_items(project: str) -> float:
	rows = frappe.db.sql(
		"""
		select sum(pii.amount) as total
		from `tabPurchase Invoice Item` pii
		join `tabPurchase Invoice` pi on pi.name = pii.parent
		where pi.docstatus = 1 and pii.project = %s
		""",
		(project,),
		as_dict=True,
	)
	return flt(rows[0].total) if rows else 0


def _sum_expense_claims(project: str) -> float:
	total = frappe.db.get_value(
		"Expense Claim",
		filters={"project": project, "docstatus": 1},
		fieldname="sum(total_sanctioned_amount)",
	)
	return flt(total)


def _sum_journal_debits(project: str) -> float:
	rows = frappe.db.sql(
		"""
		select sum(ja.debit_in_account_currency) as total
		from `tabJournal Entry Account` ja
		join `tabJournal Entry` je on je.name = ja.parent
		where je.docstatus = 1 and ja.project = %s
		""",
		(project,),
		as_dict=True,
	)
	return flt(rows[0].total) if rows else 0


def _sum_journal_credits_to_receivable(project: str) -> float:
	rows = frappe.db.sql(
		"""
		select sum(ja.credit_in_account_currency) as total
		from `tabJournal Entry Account` ja
		join `tabJournal Entry` je on je.name = ja.parent
		join `tabAccount` acc on acc.name = ja.account
		where je.docstatus = 1
		  and ja.project = %s
		  and acc.account_type = 'Receivable'
		""",
		(project,),
		as_dict=True,
	)
	return flt(rows[0].total) if rows else 0


def _sum_payment_entry_references(project: str) -> float:
	"""Sum allocated amounts from Payment Entries that touch this project.

	A Payment Entry touches `project` if either:
	- The PE itself has `project = X`, or
	- A reference row points to a Sales/Purchase Invoice whose project is X.

	Receive payments (party_type=Customer) count as money-in.
	"""
	rows = frappe.db.sql(
		"""
		select sum(per.allocated_amount) as total
		from `tabPayment Entry Reference` per
		join `tabPayment Entry` pe on pe.name = per.parent
		where pe.docstatus = 1
		  and pe.payment_type = 'Receive'
		  and (
		    per.reference_doctype = 'Sales Invoice'
		    and exists (
		      select 1 from `tabSales Invoice` si
		      where si.name = per.reference_name and si.project = %(project)s
		    )
		  )
		""",
		{"project": project},
		as_dict=True,
	)
	return flt(rows[0].total) if rows else 0


@frappe.whitelist()
def get_site_building_types(doctype, txt, searchfield, start, page_len, filters):
	"""Search-query handler for the Project.building_type set_query.

	Returns Items present in the chosen Site's project_units.building_type.
	"""
	site = (filters or {}).get("site")
	if not site:
		return []
	return frappe.db.sql(
		"""
		select distinct pu.building_type, item.item_name
		from `tabProject Unit Item` pu
		left join `tabItem` item on item.name = pu.building_type
		where pu.parent = %(site)s
		  and pu.parenttype = 'Site'
		  and (pu.building_type like %(txt)s or item.item_name like %(txt)s)
		order by pu.building_type
		limit %(start)s, %(page_len)s
		""",
		{
			"site": site,
			"txt": f"%{txt}%",
			"start": start,
			"page_len": page_len,
		},
	)
```

- [ ] **Step 4.4: Run tests — expect pass on the two no-op tests**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_project_aggregations
```
Expected: all current tests pass (the runtime end-to-end tests come in Task 5).

- [ ] **Step 4.5: Commit**

```bash
git add dantata_town/dantata_town/project_aggregations.py \
        dantata_town/dantata_town/tests/test_project_aggregations.py
git commit -m "feat: project_aggregations module with recalc_project_totals helpers"
```

---

## Task 5: Wire hooks for PI / Expense Claim / Journal Entry / Payment Entry

**Files:**
- Modify: `dantata_town/hooks.py`
- Modify: `dantata_town/dantata_town/tests/test_project_aggregations.py`

- [ ] **Step 5.1: Write failing end-to-end tests**

Append to `test_project_aggregations.py`:
```python
class TestProjectAggregationHooks(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()

	def _submit_purchase_invoice(self, project: str | None, amount: float = 1000) -> str:
		supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
		item = frappe.db.get_value("Item", {"is_purchase_item": 1, "disabled": 0}, "name") \
		       or frappe.db.get_value("Item", {"disabled": 0}, "name")
		item_row = {"item_code": item, "qty": 1, "rate": amount}
		if project:
			item_row["project"] = project
		pi = frappe.get_doc({
			"doctype": "Purchase Invoice",
			"supplier": supplier,
			"items": [item_row],
		})
		pi.set_missing_values()
		pi.insert(ignore_permissions=True)
		pi.submit()
		return pi.name

	def test_purchase_invoice_submit_increases_project_expenses(self):
		_, project = _make_site_and_project()
		self._submit_purchase_invoice(project, amount=2500)
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_expenses")),
			2500,
		)

	def test_purchase_invoice_cancel_reverses_project_expenses(self):
		_, project = _make_site_and_project()
		pi_name = self._submit_purchase_invoice(project, amount=1500)
		pi = frappe.get_doc("Purchase Invoice", pi_name)
		pi.cancel()
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_expenses")),
			0,
		)

	def test_doc_with_no_project_is_noop(self):
		_, project = _make_site_and_project()
		# A PI without a project link must not affect the unrelated project's expenses.
		self._submit_purchase_invoice(project=None, amount=999)
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_expenses")),
			0,
		)
```

- [ ] **Step 5.2: Run tests — expect failures**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_project_aggregations
```
Expected: PI tests fail because nothing recalculates totals on submit yet (project_expenses stays 0 after a submit).

- [ ] **Step 5.3: Add hooks**

In `dantata_town/hooks.py`, extend `doc_events`:
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
Run `bench --site home.com clear-cache` so the new hooks load.

- [ ] **Step 5.4: Run tests — expect pass**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_project_aggregations
```
Expected: all tests pass.

- [ ] **Step 5.5: Commit**

```bash
git add dantata_town/hooks.py dantata_town/dantata_town/tests/test_project_aggregations.py
git commit -m "feat: hook PI/EC/JE/PE submit & cancel to recalc Project totals"
```

---

## Task 6: `building_type` set_query on Project form

**Files:**
- Modify: `dantata_town/public/js/project.js`

- [ ] **Step 6.1: Read current `project.js`**

```bash
cat dantata_town/public/js/project.js
```
Confirm current handlers: `refresh` (Create BOQ button) and `project_type` (clears `project_subtype`).

- [ ] **Step 6.2: Edit `project.js`**

Replace contents with:
```javascript
frappe.ui.form.on("Project", {
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

	refresh(frm) {
		if (!frm.is_new() && frm.doc.site) {
			frm.add_custom_button(__("Create BOQ"), () => {
				frappe.new_doc("Bill of Quantities", {
					site: frm.doc.site,
					project: frm.doc.name,
				});
			});
		}
	},

	site(frm) {
		frm.set_value("building_type", null);
	},

	project_type(frm) {
		frm.set_value("project_subtype", null);
	},
});
```

- [ ] **Step 6.3: Manual verify in browser**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com clear-cache
```
Open a draft Project, set Site → confirm Building Type dropdown shows only items present in that Site's `project_units`. Change Site → confirm Building Type clears.

- [ ] **Step 6.4: Commit**

```bash
git add dantata_town/public/js/project.js
git commit -m "feat: filter Project building_type to chosen Site's project_units"
```

---

## Task 7: Register BOQ Items `completed` + per-stage parent fields

**Files:**
- Modify: `dantata_town/dantata_town/setup.py`
- Create: `dantata_town/dantata_town/tests/test_boq_progress.py`

- [ ] **Step 7.1: Write failing field-existence tests**

Create `dantata_town/dantata_town/tests/test_boq_progress.py`:
```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, add_days, today

from dantata_town.dantata_town.setup import create_boq_custom_fields


class TestBOQStageFieldsInstalled(FrappeTestCase):
	def test_completed_checkbox_on_boq_items(self):
		create_boq_custom_fields()
		field = frappe.db.get_value(
			"Custom Field",
			{"dt": "BOQ Items", "fieldname": "completed"},
			["fieldtype", "allow_on_submit", "in_list_view"],
			as_dict=True,
		)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Check")
		self.assertEqual(field.allow_on_submit, 1)
		self.assertEqual(field.in_list_view, 1)

	def test_per_stage_fields_exist(self):
		create_boq_custom_fields()
		for stage in range(1, 8):
			for suffix, fieldtype, expect_allow_on_submit in [
				("start_date", "Date", 1),
				("end_date", "Date", 1),
				("duration", "Int", 0),
				("progress", "Percent", 0),
				("status", "Data", 0),
			]:
				fieldname = f"stage_{stage}_{suffix}"
				field = frappe.db.get_value(
					"Custom Field",
					{"dt": "Bill of Quantities", "fieldname": fieldname},
					["fieldtype", "read_only", "allow_on_submit"],
					as_dict=True,
				)
				self.assertIsNotNone(field, f"{fieldname} missing")
				self.assertEqual(field.fieldtype, fieldtype, fieldname)
				if suffix in ("duration", "progress", "status"):
					self.assertEqual(field.read_only, 1, fieldname)
				if expect_allow_on_submit:
					self.assertEqual(field.allow_on_submit, 1, fieldname)
```

- [ ] **Step 7.2: Run tests — expect failures**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_boq_progress
```
Expected: all assertions fail (fields not registered yet).

- [ ] **Step 7.3: Extend `setup.py` — add BOQ Items `completed`**

In `_create_custom_fields()`, add a new top-level entry to `custom_fields`:
```python
		"BOQ Items": [
			{
				"fieldname": "completed",
				"fieldtype": "Check",
				"label": "Completed",
				"insert_after": "actual_amount",
				"allow_on_submit": 1,
				"in_list_view": 1,
				"module": "Dantata Town",
			},
		],
```

- [ ] **Step 7.4: Extend `setup.py` — add per-stage BOQ fields via loop**

Inside `_create_custom_fields()`, after the static `custom_fields` dict is built but before `create_custom_fields(custom_fields, update=True)`, add:

```python
	# Per-stage tracking fields on Bill of Quantities (× 7 stages)
	stage_summary_fieldnames = {
		1: "stage_1_summary",
		2: "stage_2_summary",
		3: "stage_3_summary",
		4: "stage_4_summary",
		5: "stage_5_summary",
		6: "stage_6_summary",
		7: "stage_7_summary",
	}
	boq_stage_fields = []
	for stage_no, summary_fieldname in stage_summary_fieldnames.items():
		previous = summary_fieldname
		for suffix, ftype, extra in [
			("start_date", "Date", {"allow_on_submit": 1}),
			("end_date", "Date", {"allow_on_submit": 1}),
			("duration", "Int", {"read_only": 1, "label_extra": " (days)"}),
			("progress", "Percent", {"read_only": 1}),
			("status", "Data", {"read_only": 1}),
		]:
			fieldname = f"stage_{stage_no}_{suffix}"
			label_extra = extra.pop("label_extra", "")
			label = f"Stage {stage_no} {suffix.replace('_', ' ').title()}{label_extra}"
			boq_stage_fields.append({
				"fieldname": fieldname,
				"fieldtype": ftype,
				"label": label,
				"insert_after": previous,
				"module": "Dantata Town",
				**extra,
			})
			previous = fieldname
	custom_fields.setdefault("Bill of Quantities", []).extend(boq_stage_fields)
```

- [ ] **Step 7.5: Run install hook**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate
```
Expected: success; 1 + 35 = 36 new custom fields registered.

- [ ] **Step 7.6: Run tests — expect pass**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_boq_progress
```
Expected: 2 tests pass.

- [ ] **Step 7.7: Commit**

```bash
git add dantata_town/dantata_town/setup.py \
        dantata_town/dantata_town/tests/test_boq_progress.py
git commit -m "feat: register BOQ Items.completed and 35 per-stage tracking fields"
```

---

## Task 8: `boq_progress.py` — validate_stage_dates + recalc_boq_progress

**Files:**
- Create: `dantata_town/dantata_town/boq_progress.py`
- Modify: `dantata_town/dantata_town/tests/test_boq_progress.py`

- [ ] **Step 8.1: Write failing tests for the compute logic**

Append to `test_boq_progress.py`:
```python
from dantata_town.dantata_town.boq_progress import (
	STAGE_TABLES,
	validate_stage_dates,
	recalc_boq_progress,
)


def _make_site():
	create_boq_custom_fields()
	uom = frappe.db.get_value("UOM", {}, "name")
	item = frappe.db.get_value("Item", {"disabled": 0}, "name")
	site = frappe.get_doc({
		"doctype": "Site",
		"site_name": f"BOQSite-{frappe.generate_hash(length=6)}",
		"project_units": [{"building_type": item, "unit": 1, "uom": uom, "rate": 1}],
	}).insert(ignore_permissions=True)
	return site.name


def _detail_name():
	"""Return a BOQ Item Detail name to use as `description`. Create one if none exist."""
	existing = frappe.db.get_value("BOQ Item Detail", {}, "name")
	if existing:
		return existing
	return frappe.get_doc({
		"doctype": "BOQ Item Detail",
		"description": f"Detail-{frappe.generate_hash(length=6)}",
		"description_type": "Material",
		"unit": "Nos",
	}).insert(ignore_permissions=True).name


class TestRecalcBOQProgress(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()

	def _new_boq(self, stage_rows: dict[int, list[dict]]) -> "frappe.model.document.Document":
		"""Build an in-memory BOQ doc with the given stage_no -> list-of-row-dicts."""
		site = _make_site()
		project = frappe.db.get_value("Project", {}, "name")
		# Tests only need the Project link; create one if missing.
		if not project:
			project = frappe.get_doc({
				"doctype": "Project",
				"project_name": f"P-{frappe.generate_hash(length=6)}",
				"customer": frappe.db.get_value("Customer", {"disabled": 0}, "name"),
				"site": site,
				"project_type": "Building",
				"project_subtype": "PLOT",
			}).insert(ignore_permissions=True).name
		else:
			frappe.db.set_value("Project", project, "site", site)

		doc = frappe.new_doc("Bill of Quantities")
		doc.site = site
		doc.project = project
		doc.date = today()
		for stage_no, rows in stage_rows.items():
			table = STAGE_TABLES[stage_no]
			for row in rows:
				doc.append(table, {"description": _detail_name(), **row})
		return doc

	def test_empty_stage_progress_is_zero(self):
		doc = self._new_boq({})
		recalc_boq_progress(doc)
		for stage_no in STAGE_TABLES:
			self.assertEqual(doc.get(f"stage_{stage_no}_progress"), 0)
			self.assertEqual(doc.get(f"stage_{stage_no}_status"), "")

	def test_one_of_four_checked_yields_25(self):
		doc = self._new_boq({1: [
			{"completed": 0, "planned_quantity": 1, "rate": 1},
			{"completed": 1, "planned_quantity": 1, "rate": 1},
			{"completed": 0, "planned_quantity": 1, "rate": 1},
			{"completed": 0, "planned_quantity": 1, "rate": 1},
		]})
		recalc_boq_progress(doc)
		self.assertEqual(flt(doc.stage_1_progress), 25)
		self.assertEqual(doc.stage_1_status, "")

	def test_all_checked_yields_100_and_completed(self):
		doc = self._new_boq({2: [
			{"completed": 1, "planned_quantity": 1, "rate": 1},
			{"completed": 1, "planned_quantity": 1, "rate": 1},
		]})
		recalc_boq_progress(doc)
		self.assertEqual(flt(doc.stage_2_progress), 100)
		self.assertEqual(doc.stage_2_status, "Completed")

	def test_duration_computed_from_dates(self):
		doc = self._new_boq({3: [{"completed": 0, "planned_quantity": 1, "rate": 1}]})
		doc.stage_3_start_date = today()
		doc.stage_3_end_date = add_days(today(), 10)
		recalc_boq_progress(doc)
		self.assertEqual(doc.stage_3_duration, 10)


class TestValidateStageDates(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()

	def test_empty_stage_does_not_require_dates(self):
		doc = frappe.new_doc("Bill of Quantities")
		doc.site = _make_site()
		doc.project = frappe.db.get_value("Project", {}, "name")
		doc.date = today()
		# No rows in any stage; should not raise.
		validate_stage_dates(doc)

	def test_stage_with_items_requires_both_dates(self):
		site = _make_site()
		project = frappe.db.get_value("Project", {}, "name")
		doc = frappe.new_doc("Bill of Quantities")
		doc.site = site
		doc.project = project
		doc.date = today()
		doc.append("table_txao", {
			"description": _detail_name(),
			"planned_quantity": 1,
			"rate": 1,
		})
		with self.assertRaises(frappe.ValidationError):
			validate_stage_dates(doc)

	def test_end_before_start_raises(self):
		site = _make_site()
		project = frappe.db.get_value("Project", {}, "name")
		doc = frappe.new_doc("Bill of Quantities")
		doc.site = site
		doc.project = project
		doc.date = today()
		doc.append("table_txao", {
			"description": _detail_name(),
			"planned_quantity": 1,
			"rate": 1,
		})
		doc.stage_1_start_date = today()
		doc.stage_1_end_date = add_days(today(), -2)
		with self.assertRaises(frappe.ValidationError):
			validate_stage_dates(doc)
```

- [ ] **Step 8.2: Run tests — expect ImportError**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_boq_progress
```
Expected: failure on `from dantata_town.dantata_town.boq_progress import ...` — module not found.

- [ ] **Step 8.3: Implement `boq_progress.py`**

Create `dantata_town/dantata_town/boq_progress.py`:
```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.utils import flt


# Map of BOQ stage number -> the parent's child-table fieldname for that stage.
# These names are baked into the existing Bill of Quantities doctype JSON.
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
	"""Require start/end dates for any stage that has line items, and end >= start."""
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
	"""Recompute duration, progress, and status for each stage.

	Progress is count-based: 100 * checked / total.
	Status = "Completed" when progress hits 100 and the stage has at least one row.
	"""
	for stage_no, table_field in STAGE_TABLES.items():
		rows = doc.get(table_field) or []
		total = len(rows)
		done = sum(1 for r in rows if r.completed)
		progress = (100 * done / total) if total else 0
		doc.set(f"stage_{stage_no}_progress", progress)
		doc.set(
			f"stage_{stage_no}_status",
			"Completed" if total and flt(progress) == 100 else "",
		)
		start = doc.get(f"stage_{stage_no}_start_date")
		end = doc.get(f"stage_{stage_no}_end_date")
		doc.set(
			f"stage_{stage_no}_duration",
			(end - start).days if start and end else 0,
		)
```

- [ ] **Step 8.4: Run tests — expect pass**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --module dantata_town.dantata_town.tests.test_boq_progress
```
Expected: all tests pass.

- [ ] **Step 8.5: Commit**

```bash
git add dantata_town/dantata_town/boq_progress.py \
        dantata_town/dantata_town/tests/test_boq_progress.py
git commit -m "feat: BOQ stage progress validate + recalc helpers"
```

---

## Task 9: Wire BOQ hooks + form-script live recompute

**Files:**
- Modify: `dantata_town/hooks.py`
- Create: `dantata_town/public/js/bill_of_quantities.js`

- [ ] **Step 9.1: Add BOQ doc-event hook**

In `dantata_town/hooks.py`, extend `doc_events`:
```python
doc_events = {
	# ... existing entries ...
	"Bill of Quantities": {
		"validate": [
			"dantata_town.dantata_town.boq_progress.validate_stage_dates",
			"dantata_town.dantata_town.boq_progress.recalc_boq_progress",
		],
	},
}
```

- [ ] **Step 9.2: Add BOQ doctype_js entry**

In `hooks.py`, extend `doctype_js`:
```python
doctype_js = {
	# ... existing entries ...
	"Bill of Quantities": "public/js/bill_of_quantities.js",
}
```

- [ ] **Step 9.3: Implement form script**

Create `dantata_town/public/js/bill_of_quantities.js`:
```javascript
// Stage number -> parentfield map. Mirror of dantata_town.dantata_town.boq_progress.STAGE_TABLES.
const STAGE_TABLES = {
	1: "table_txao",
	2: "description2",
	3: "description3",
	4: "description4",
	5: "description5",
	6: "description6",
	7: "description7",
};
const PARENTFIELD_TO_STAGE = Object.fromEntries(
	Object.entries(STAGE_TABLES).map(([stage, field]) => [field, Number(stage)])
);

function recalc_stage(frm, stage_no) {
	const rows = frm.doc[STAGE_TABLES[stage_no]] || [];
	const total = rows.length;
	const done = rows.filter((r) => r.completed).length;
	const progress = total ? (100 * done) / total : 0;
	frm.set_value(`stage_${stage_no}_progress`, progress);
	frm.set_value(
		`stage_${stage_no}_status`,
		total && progress === 100 ? "Completed" : ""
	);
	const start = frm.doc[`stage_${stage_no}_start_date`];
	const end = frm.doc[`stage_${stage_no}_end_date`];
	if (start && end) {
		frm.set_value(
			`stage_${stage_no}_duration`,
			frappe.datetime.get_diff(end, start)
		);
	} else {
		frm.set_value(`stage_${stage_no}_duration`, 0);
	}
}

frappe.ui.form.on("Bill of Quantities", {
	refresh(frm) {
		for (const stage_no of Object.keys(STAGE_TABLES)) {
			recalc_stage(frm, Number(stage_no));
		}
	},
});

// Hook every per-stage start/end date field.
for (let stage_no = 1; stage_no <= 7; stage_no++) {
	frappe.ui.form.on("Bill of Quantities", {
		[`stage_${stage_no}_start_date`]: (frm) => recalc_stage(frm, stage_no),
		[`stage_${stage_no}_end_date`]: (frm) => recalc_stage(frm, stage_no),
	});
}

// Live recompute on the line-item completed toggle.
frappe.ui.form.on("BOQ Items", {
	completed(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		const stage_no = PARENTFIELD_TO_STAGE[row.parentfield];
		if (stage_no) {
			recalc_stage(frm, stage_no);
		}
	},
});
```

- [ ] **Step 9.4: Reload site & verify**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com clear-cache
```

Browser check:
1. Open an existing draft BOQ. Tick a Stage 1 row's `Completed` checkbox. Confirm `Stage 1 Progress` updates immediately, `Status` shows "Completed" when 100%.
2. Set Stage 1 Start Date and End Date 5 days apart. Confirm `Stage 1 Duration` shows 5 without a save.
3. Save → server `validate` runs and the same values are persisted.

- [ ] **Step 9.5: Commit**

```bash
git add dantata_town/hooks.py dantata_town/public/js/bill_of_quantities.js
git commit -m "feat: wire BOQ stage progress validate hooks + live form script"
```

---

## Task 10: Manual end-to-end verification + integration sanity

**Files:** none changed; verification commit only if any field/hook tweak surfaces.

- [ ] **Step 10.1: Run the full test module**

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town
```
Expected: all dantata_town tests pass (existing + the 3 new test files).

- [ ] **Step 10.2: Manual verification — Site renames**

1. Open any existing Site with rows in Project Units.
2. Confirm column headers read "Building Type" and "Unit".
3. Confirm row values are intact (item refs and counts).

- [ ] **Step 10.3: Manual verification — Project financials**

1. Open an existing Project that has a Site set.
2. Confirm the new "Financials" section shows `Project Expenses` and `Project Payment` (both 0 if no docs).
3. Confirm `Sales Order Amount` (relabeled) is visible.
4. Submit a Purchase Invoice referencing this project. Reopen Project → `Project Expenses` reflects the new amount.
5. Cancel the PI → `Project Expenses` returns to its previous value.

- [ ] **Step 10.4: Manual verification — Project building_type filter**

1. On a draft Project, set Site → confirm `Building Type` dropdown only shows items present in that Site's `project_units`.
2. Change Site → `Building Type` clears.

- [ ] **Step 10.5: Manual verification — BOQ progress**

1. Open an existing submitted BOQ.
2. Tick a `Completed` checkbox on a Stage 1 row. Save.
3. Confirm `Stage 1 Progress` updated; `Stage 1 Status` is "" or "Completed" as appropriate.
4. Set/clear Stage 1 dates. Confirm `Stage 1 Duration` updates.

- [ ] **Step 10.6: Final clean-tree check**

```bash
git status
git log --oneline -10
```
Expected: clean working tree, last commit is the BOQ form-script wiring.

---

## Spec coverage check

Spec sections vs. tasks:

| Spec section | Implemented by |
|--------------|----------------|
| 1. Site renames (JSON) | Task 1 |
| 1. Site renames (patch + idempotency) | Task 2 |
| 2. Project custom fields | Task 3 |
| 2. Property setters (label / hidden) | Task 3 |
| 2. `project_name` no-op note | (implicit; nothing to implement) |
| 2. `project_aggregations.py` | Task 4 |
| 2. Hooks for PI / EC / JE / PE | Task 5 |
| 2. `building_type` set_query / get_site_building_types | Task 4 (whitelisted method) + Task 6 (form script) |
| 3. BOQ Items `completed` | Task 7 |
| 3. Per-stage parent fields × 7 | Task 7 |
| 3. `boq_progress.py` | Task 8 |
| 3. BOQ doc-event + doctype_js | Task 9 |
| 3. Live form-script recompute | Task 9 |
| 4. `setup.py` extension shape | Tasks 3 & 7 |
| 5. Tests | Tasks 2, 3, 4, 5, 7, 8 |
| 5. Manual verification checklist | Task 10 |

No spec requirements are missing.

---

## Risks during execution

- **`bench migrate` order**: the rename patch (Task 2) may run on a site that already has the old fieldnames. Re-running migrate after the JSON change (Task 1) but before the patch is registered (Task 2) would make Frappe create the new fields as empty columns alongside the old ones. **Therefore Tasks 1 and 2 must land in the same batch / before the next `bench migrate`.** If anyone runs `bench migrate` between Task 1 commit and Task 2 register, the patch's column-existence guard still does the right thing — but the duplicate (now-unused) old columns will linger. To clean up, run a one-off `frappe.db.sql("ALTER TABLE \`tabProject Unit Item\` DROP COLUMN unit_type, DROP COLUMN projected_quantity")` **only after** verifying no rows hold data there.
- **Concurrency on `recalc_project_totals`**: simultaneous PI submits on the same project re-sum from `docstatus=1` rows so no drift; second writer wins on `set_value`. Acceptable at this scale.
- **`get_site_building_types` whitelist**: the method is `@frappe.whitelist()`; it accepts only the Site name and uses parameterized SQL. Safe against injection.
- **BOQ form script and `allow_on_submit` interaction**: ticking a `completed` checkbox on a submitted BOQ triggers Frappe's auto-save; server `validate` re-runs and recomputes derived fields. If the user toggles many rows quickly, multiple auto-saves queue up — Frappe handles this serially.
