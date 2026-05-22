# Site Template Data Field, Sellable Quantity, Sales Order Amount — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `Project Unit Item.template_item` to a Data field that auto-creates Items on save with hardcoded defaults, add a Sellable Quantity column with a Quotation-level cap, wire SO submit/cancel into the Project totals recompute, reposition Sales Order Amount into the Financials section, and auto-link orphan SOs when a Project is saved with a Site link.

**Architecture:** All changes target the existing Dantata Town app under `dantata_town/dantata_town/`. Schema lives in `doctype/project_unit_item/project_unit_item.json`; business logic in `site.py`, `quotation.py`, `sales_order.py` (unchanged here), `project_aggregations.py`, and a new `project.py`. Wiring in `hooks.py`. Property setters in `setup.py:_create_property_setters`. One patch under `patches/` for existing-data backfill.

**Tech Stack:** Frappe v15 / ERPNext on MariaDB. Tests use `frappe.tests.utils.FrappeTestCase` and run via `bench --site <site> run-tests --app dantata_town`. The bench site is at `/home/okeke/clients/graceco/frappe-bench`; substitute the actual site name in commands below.

**Test command** (used throughout — substitute your dev site name):
```bash
cd /home/okeke/clients/graceco/frappe-bench
bench --site <dev-site> run-tests --app dantata_town --module <module>
```
A full migrate is required before running tests after any DocType JSON change:
```bash
bench --site <dev-site> migrate
```

---

## File Structure

**Created:**
- `dantata_town/dantata_town/project.py` — `auto_link_orphan_sales_orders` hook handler
- `dantata_town/dantata_town/tests/test_site_template_data.py` — Item-defaults + setup-precondition tests
- `dantata_town/dantata_town/tests/test_sellable_cap.py` — Quotation cap tests
- `dantata_town/patches/recalc_sales_amount_for_existing_projects.py` — one-time backfill

**Modified:**
- `dantata_town/dantata_town/doctype/project_unit_item/project_unit_item.json` — template_item Link→Data; add `sellable_unit`; reorder
- `dantata_town/dantata_town/doctype/site/site.py` — `_ensure_per_site_items` defaults; `calculate_totals` adds sellable_unit
- `dantata_town/dantata_town/quotation.py` — add `check_sellable_cap`
- `dantata_town/dantata_town/project_aggregations.py` — `_sum_sales_orders`; extend `recalc_project_totals` + `_projects_touched_by`
- `dantata_town/dantata_town/setup.py` — `_create_property_setters` adds `total_sales_amount.insert_after`
- `dantata_town/hooks.py` — register Quotation cap, Sales Order on_submit/on_cancel, Project on_update
- `dantata_town/dantata_town/tests/test_per_site_items.py` — adapt assertions to Data field
- `dantata_town/dantata_town/tests/test_project_aggregations.py` — add SO amount + auto-link tests
- `dantata_town/patches.txt` — register new patch

---

## Task 1: Schema — `Project Unit Item` Link→Data + `sellable_unit` column

**Files:**
- Modify: `dantata_town/dantata_town/doctype/project_unit_item/project_unit_item.json`
- Modify: `dantata_town/dantata_town/tests/test_per_site_items.py` (assertions only)

- [ ] **Step 1: Update the existing schema assertion in `test_per_site_items.py`**

Replace lines 12-19 of `dantata_town/dantata_town/tests/test_per_site_items.py` (the `test_template_item_field_exists` body):

```python
	def test_template_item_field_exists(self):
		meta = frappe.get_meta("Project Unit Item")
		fieldnames = {f.fieldname for f in meta.fields}
		self.assertIn("template_item", fieldnames)
		template = next(f for f in meta.fields if f.fieldname == "template_item")
		self.assertEqual(template.fieldtype, "Data")
		self.assertEqual(template.reqd, 1)
		# Label is intentionally retained as "Template Item" even though type changed.
		self.assertEqual(template.label, "Template Item")
```

Add a brand-new test method right below it:

```python
	def test_sellable_unit_field_exists(self):
		meta = frappe.get_meta("Project Unit Item")
		fieldnames = {f.fieldname for f in meta.fields}
		self.assertIn("sellable_unit", fieldnames)
		sellable = next(f for f in meta.fields if f.fieldname == "sellable_unit")
		self.assertEqual(sellable.fieldtype, "Float")
		self.assertEqual(sellable.read_only, 1)
		self.assertEqual(sellable.label, "Sellable")
		self.assertEqual(sellable.in_list_view, 1)
```

- [ ] **Step 2: Run the tests; they should fail because schema still says Link / has no sellable_unit**

```bash
cd /home/okeke/clients/graceco/frappe-bench
bench --site <dev-site> run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_per_site_items
```
Expected: two failures — `test_template_item_field_exists` (fieldtype Link != Data) and `test_sellable_unit_field_exists` (KeyError on `sellable_unit`).

- [ ] **Step 3: Update the DocType JSON**

Replace the entire contents of `dantata_town/dantata_town/doctype/project_unit_item/project_unit_item.json` with:

```json
{
 "actions": [],
 "allow_rename": 1,
 "creation": "2026-04-05 13:20:32.375657",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "template_item",
  "building_type",
  "unit",
  "reserved_unit",
  "sellable_unit",
  "column_break_lomr",
  "uom",
  "rate",
  "amount"
 ],
 "fields": [
  {
   "columns": 2,
   "fieldname": "template_item",
   "fieldtype": "Data",
   "in_list_view": 1,
   "label": "Template Item",
   "reqd": 1
  },
  {
   "columns": 2,
   "fieldname": "building_type",
   "fieldtype": "Link",
   "in_list_view": 1,
   "label": "Building Type",
   "options": "Item",
   "read_only": 1
  },
  {
   "columns": 1,
   "fieldname": "unit",
   "fieldtype": "Float",
   "in_list_view": 1,
   "label": "Total Units"
  },
  {
   "columns": 1,
   "fieldname": "reserved_unit",
   "fieldtype": "Float",
   "in_list_view": 1,
   "label": "Reserved"
  },
  {
   "columns": 1,
   "fieldname": "sellable_unit",
   "fieldtype": "Float",
   "in_list_view": 1,
   "label": "Sellable",
   "read_only": 1
  },
  {
   "fieldname": "column_break_lomr",
   "fieldtype": "Column Break"
  },
  {
   "columns": 1,
   "fieldname": "uom",
   "fieldtype": "Link",
   "in_list_view": 1,
   "label": "UOM",
   "options": "UOM"
  },
  {
   "columns": 1,
   "fieldname": "rate",
   "fieldtype": "Currency",
   "in_list_view": 1,
   "label": "Rate"
  },
  {
   "columns": 1,
   "fieldname": "amount",
   "fieldtype": "Currency",
   "in_list_view": 1,
   "label": "Amount",
   "read_only": 1
  }
 ],
 "grid_page_length": 50,
 "index_web_pages_for_search": 1,
 "istable": 1,
 "links": [],
 "modified": "2026-05-22 09:00:00.000000",
 "modified_by": "Administrator",
 "module": "Dantata Town",
 "name": "Project Unit Item",
 "owner": "Administrator",
 "permissions": [],
 "row_format": "Dynamic",
 "rows_threshold_for_grid_search": 20,
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

Key changes vs current file: `template_item.fieldtype` is now `"Data"` (no `options`); `sellable_unit` row added between `reserved_unit` and `column_break_lomr`; `field_order` includes `sellable_unit`; column widths for `unit`/`reserved_unit` reduced from 2 to 1 so the new column fits in the row's 10-column grid; `modified` bumped to `2026-05-22 09:00:00.000000`.

- [ ] **Step 4: Run `bench migrate` to apply the schema**

```bash
cd /home/okeke/clients/graceco/frappe-bench
bench --site <dev-site> migrate
```
Expected: migration succeeds. Frappe converts the DB column `template_item` from `varchar(140)` (linked) to `varchar(140)` (data) — no data loss. Adds `sellable_unit` column.

- [ ] **Step 5: Run the schema tests; both should now pass**

```bash
bench --site <dev-site> run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_per_site_items --test TestProjectUnitItemSchema
```
Expected: 4 passes (existing 2 + 2 new).

- [ ] **Step 6: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/doctype/project_unit_item/project_unit_item.json \
        dantata_town/dantata_town/tests/test_per_site_items.py
git commit -m "feat(schema): Project Unit Item template_item Link→Data; add sellable_unit column"
```

---

## Task 2: Site auto-create defaults + calculate sellable_unit

**Files:**
- Modify: `dantata_town/dantata_town/doctype/site/site.py`
- Modify: `dantata_town/dantata_town/tests/test_per_site_items.py` (rework fixtures)
- Create: `dantata_town/dantata_town/tests/test_site_template_data.py`

- [ ] **Step 1: Create the new test file** with the auto-create-defaults coverage

Create `dantata_town/dantata_town/tests/test_site_template_data.py`:

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from dantata_town.dantata_town.setup import create_boq_custom_fields
from dantata_town.dantata_town.tests._helpers import get_test_expense_account


def _ensure_item_group_properties():
	if not frappe.db.exists("Item Group", "PROPERTIES"):
		frappe.get_doc({
			"doctype": "Item Group",
			"item_group_name": "PROPERTIES",
			"parent_item_group": "All Item Groups",
			"is_group": 0,
		}).insert(ignore_permissions=True)


def _ensure_unit_uom():
	if not frappe.db.exists("UOM", "Unit"):
		frappe.get_doc({
			"doctype": "UOM",
			"uom_name": "Unit",
		}).insert(ignore_permissions=True)


def _ensure_warehouse_stores_dtd():
	"""Return the warehouse name 'Stores - DTD' if present; otherwise return
	the test site's default warehouse-equivalent and skip default_warehouse
	assertion. Tests should not invent a warehouse with a different abbr."""
	if frappe.db.exists("Warehouse", "Stores - DTD"):
		return "Stores - DTD"
	return None


class TestSiteAutoCreateDefaults(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		_ensure_item_group_properties()
		_ensure_unit_uom()
		self.expense_account = get_test_expense_account()
		self.warehouse = _ensure_warehouse_stores_dtd()

	def _make_site(self, template_name):
		return frappe.get_doc({
			"doctype": "Site",
			"site_name": f"DefaultsSite-{frappe.generate_hash(length=6)}",
			"expense_account": self.expense_account,
			"project_units": [{
				"template_item": template_name,
				"unit": 10,
				"reserved_unit": 0,
				"uom": "Unit",
				"rate": 1000,
			}],
		})

	def test_auto_created_item_has_hardcoded_defaults(self):
		site = self._make_site("3-Bedroom Bungalow")
		site.insert(ignore_permissions=True)
		expected_item = f"{site.site_name} - 3-Bedroom Bungalow"

		self.assertTrue(frappe.db.exists("Item", expected_item))
		item = frappe.get_doc("Item", expected_item)
		self.assertEqual(item.item_group, "PROPERTIES")
		self.assertEqual(item.stock_uom, "Unit")
		self.assertEqual(item.is_stock_item, 1)
		self.assertEqual(item.is_purchase_item, 1)
		self.assertEqual(item.is_sales_item, 1)
		self.assertEqual(item.grant_commission, 1)
		# At least one item_defaults row with the default company.
		self.assertGreater(len(item.item_defaults), 0)
		default_company = frappe.db.get_single_value("Global Defaults", "default_company")
		self.assertEqual(item.item_defaults[0].company, default_company)
		if self.warehouse:
			self.assertEqual(item.item_defaults[0].default_warehouse, self.warehouse)

	def test_idempotent_save_does_not_duplicate_item(self):
		site = self._make_site("Studio")
		site.insert(ignore_permissions=True)
		expected_item = f"{site.site_name} - Studio"
		self.assertEqual(frappe.db.count("Item", {"item_code": expected_item}), 1)
		site.save(ignore_permissions=True)
		self.assertEqual(frappe.db.count("Item", {"item_code": expected_item}), 1)

	def test_sellable_unit_computed_on_save(self):
		site = frappe.get_doc({
			"doctype": "Site",
			"site_name": f"SellSite-{frappe.generate_hash(length=6)}",
			"expense_account": self.expense_account,
			"project_units": [{
				"template_item": "Penthouse",
				"unit": 10,
				"reserved_unit": 3,
				"uom": "Unit",
				"rate": 1000,
			}],
		})
		site.insert(ignore_permissions=True)
		self.assertEqual(flt(site.project_units[0].sellable_unit), 7.0)

	def test_missing_item_group_properties_throws(self):
		# Temporarily remove the group; restore in tearDown.
		if frappe.db.exists("Item Group", "PROPERTIES"):
			frappe.delete_doc("Item Group", "PROPERTIES", ignore_permissions=True, force=True)
		try:
			site = self._make_site("Loft")
			with self.assertRaises(frappe.ValidationError) as cm:
				site.insert(ignore_permissions=True)
			self.assertIn("PROPERTIES", str(cm.exception))
		finally:
			_ensure_item_group_properties()
```

- [ ] **Step 2: Update existing tests in `test_per_site_items.py` that depend on a linked template Item**

In `dantata_town/dantata_town/tests/test_per_site_items.py`, the `TestSiteAutoCreatesItems.setUp` and `TestItemReservedUnitSync.setUp` both insert a template Item record fixture. After this change, `template_item` is just typed text — no Item lookup happens. Replace both `setUp` methods plus calls to `self.template` with literal strings.

Replace the `TestSiteAutoCreatesItems` class (lines 39-126) with:

```python
class TestSiteAutoCreatesItems(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		from dantata_town.dantata_town.tests._helpers import get_test_expense_account
		self.expense_account = get_test_expense_account()
		# Ensure setup preconditions for the new Data-field auto-create path.
		if not frappe.db.exists("Item Group", "PROPERTIES"):
			frappe.get_doc({
				"doctype": "Item Group",
				"item_group_name": "PROPERTIES",
				"parent_item_group": "All Item Groups",
				"is_group": 0,
			}).insert(ignore_permissions=True)
		if not frappe.db.exists("UOM", "Unit"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "Unit"}).insert(ignore_permissions=True)
		self.template = "TPL Apartments"  # typed string, not an Item record

	def _make_site(self, name=None):
		name = name or f"AutoSite-{frappe.generate_hash(length=6)}"
		return frappe.get_doc({
			"doctype": "Site",
			"site_name": name,
			"expense_account": self.expense_account,
		})

	def test_validate_creates_per_site_item(self):
		site = self._make_site()
		site.append("project_units", {
			"template_item": self.template,
			"unit": 10,
			"reserved_unit": 0,
			"uom": "Unit",
			"rate": 1000,
		})
		site.insert(ignore_permissions=True)
		expected_item = f"{site.site_name} - {self.template}"
		self.assertTrue(frappe.db.exists("Item", expected_item))
		self.assertEqual(site.project_units[0].building_type, expected_item)

	def test_validate_is_idempotent(self):
		site = self._make_site()
		site.append("project_units", {
			"template_item": self.template,
			"unit": 5,
			"uom": "Unit",
			"rate": 1000,
		})
		site.insert(ignore_permissions=True)
		first_item = site.project_units[0].building_type
		site.save(ignore_permissions=True)
		self.assertEqual(site.project_units[0].building_type, first_item)
		count = frappe.db.count("Item", {"item_code": first_item})
		self.assertEqual(count, 1)

	def test_rename_blocked(self):
		site = self._make_site()
		site.append("project_units", {
			"template_item": self.template,
			"unit": 1,
			"uom": "Unit",
			"rate": 100,
		})
		site.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			frappe.rename_doc("Site", site.name, f"{site.site_name}-renamed")

	def test_msgprint_fires_on_auto_create(self):
		frappe.local.message_log = []
		site = self._make_site()
		site.append("project_units", {
			"template_item": self.template,
			"unit": 1,
			"uom": "Unit",
			"rate": 100,
		})
		site.insert(ignore_permissions=True)
		texts = [str(m) for m in frappe.local.message_log]
		self.assertTrue(
			any("Created Item" in t for t in texts),
			f"No 'Created Item' message in {texts}",
		)
```

Replace `TestItemReservedUnitSync` (lines 129-193) with:

```python
class TestItemReservedUnitSync(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		from dantata_town.dantata_town.tests._helpers import get_test_expense_account
		self.expense_account = get_test_expense_account()
		if not frappe.db.exists("Item Group", "PROPERTIES"):
			frappe.get_doc({
				"doctype": "Item Group",
				"item_group_name": "PROPERTIES",
				"parent_item_group": "All Item Groups",
				"is_group": 0,
			}).insert(ignore_permissions=True)
		if not frappe.db.exists("UOM", "Unit"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "Unit"}).insert(ignore_permissions=True)
		self.template = "TPL-Sync"

	def test_item_doctype_has_reserved_unit_field(self):
		meta = frappe.get_meta("Item")
		fieldnames = {f.fieldname for f in meta.fields}
		self.assertIn("reserved_unit", fieldnames)
		field = next(f for f in meta.fields if f.fieldname == "reserved_unit")
		self.assertEqual(field.fieldtype, "Float")

	def test_site_save_propagates_reserved_unit_to_item(self):
		site = frappe.get_doc({
			"doctype": "Site",
			"site_name": f"SyncSite-{frappe.generate_hash(length=6)}",
			"expense_account": self.expense_account,
		})
		site.append("project_units", {
			"template_item": self.template,
			"unit": 10,
			"reserved_unit": 3,
			"uom": "Unit",
			"rate": 1000,
		})
		site.insert(ignore_permissions=True)
		per_site_item = site.project_units[0].building_type
		item_reserved = frappe.db.get_value("Item", per_site_item, "reserved_unit")
		self.assertEqual(flt(item_reserved), 3.0)

	def test_reserved_unit_change_updates_item(self):
		site = frappe.get_doc({
			"doctype": "Site",
			"site_name": f"SyncSite2-{frappe.generate_hash(length=6)}",
			"expense_account": self.expense_account,
		})
		site.append("project_units", {
			"template_item": self.template,
			"unit": 10,
			"reserved_unit": 0,
			"uom": "Unit",
			"rate": 1000,
		})
		site.insert(ignore_permissions=True)
		per_site_item = site.project_units[0].building_type
		self.assertEqual(flt(frappe.db.get_value("Item", per_site_item, "reserved_unit")), 0.0)
		site.project_units[0].reserved_unit = 5
		site.save(ignore_permissions=True)
		self.assertEqual(flt(frappe.db.get_value("Item", per_site_item, "reserved_unit")), 5.0)
```

- [ ] **Step 3: Run the new + existing site tests; they should fail because site.py still does template Item lookup**

```bash
bench --site <dev-site> run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_site_template_data
bench --site <dev-site> run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_per_site_items
```
Expected: `test_site_template_data.TestSiteAutoCreateDefaults.test_auto_created_item_has_hardcoded_defaults` fails because the current code calls `frappe.get_doc("Item", row.template_item)` which throws DoesNotExistError for a typed string like `"3-Bedroom Bungalow"`. `test_sellable_unit_computed_on_save` fails because `calculate_totals` doesn't set it.

- [ ] **Step 4: Rewrite `Site._ensure_per_site_items` and extend `calculate_totals`**

Replace the entirety of `dantata_town/dantata_town/doctype/site/site.py` with:

```python
# Copyright (c) 2026, Montego-arch and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


PER_SITE_ITEM_GROUP = "PROPERTIES"
PER_SITE_STOCK_UOM = "Unit"
PER_SITE_DEFAULT_WAREHOUSE = "Stores - DTD"


class Site(Document):
	def validate(self):
		self._check_setup_preconditions()
		self._ensure_per_site_items()
		self.calculate_totals()

	def before_rename(self, old, new, merge=False):
		frappe.throw(_(
			"Site renaming is blocked because per-site Items embed the Site name. "
			"Create a new Site instead and migrate data manually if needed."
		))

	def on_trash(self):
		item_codes = [row.building_type for row in (self.project_units or []) if row.building_type]
		if not item_codes:
			return
		referenced = frappe.db.sql(
			"""
			select distinct soi.item_code
			from `tabSales Order Item` soi
			join `tabSales Order` so on so.name = soi.parent
			where so.docstatus = 1 and soi.item_code in %(items)s
			""",
			{"items": tuple(item_codes)},
		)
		if referenced:
			items = ", ".join(r[0] for r in referenced)
			frappe.throw(_(
				"Cannot delete Site: per-site Items still referenced on submitted Sales Orders: {0}"
			).format(items))

	def _check_setup_preconditions(self):
		"""Surface a clear error if hardcoded defaults for per-site Item creation
		are missing, instead of letting Frappe throw a generic link-broken error
		deep inside Item.insert()."""
		if not self.get("project_units"):
			return
		if not frappe.db.exists("Item Group", PER_SITE_ITEM_GROUP):
			frappe.throw(_(
				"Item Group '{0}' must exist before saving a Site with project_units. "
				"Create it under Stock > Item Group."
			).format(PER_SITE_ITEM_GROUP))
		if not frappe.db.exists("UOM", PER_SITE_STOCK_UOM):
			frappe.throw(_(
				"UOM '{0}' must exist before saving a Site with project_units."
			).format(PER_SITE_STOCK_UOM))

	def _ensure_per_site_items(self):
		"""For each project_units row, ensure a per-site Item exists and link it.

		`template_item` is now a Data field — the typed string becomes part of the
		per-site Item name directly. No template Item lookup is performed.
		"""
		default_company = (
			frappe.defaults.get_user_default("company")
			or frappe.db.get_single_value("Global Defaults", "default_company")
		)
		warehouse_exists = frappe.db.exists("Warehouse", PER_SITE_DEFAULT_WAREHOUSE)
		for row in self.get("project_units") or []:
			if not row.template_item:
				continue
			target_name = f"{self.site_name} - {row.template_item}"
			if not frappe.db.exists("Item", target_name):
				new_item = frappe.new_doc("Item")
				new_item.item_code = target_name
				new_item.item_name = target_name
				new_item.item_group = PER_SITE_ITEM_GROUP
				new_item.stock_uom = PER_SITE_STOCK_UOM
				new_item.is_stock_item = 1
				new_item.is_purchase_item = 1
				new_item.is_sales_item = 1
				new_item.grant_commission = 1
				defaults_row = {"company": default_company}
				if warehouse_exists:
					defaults_row["default_warehouse"] = PER_SITE_DEFAULT_WAREHOUSE
				new_item.append("item_defaults", defaults_row)
				new_item.insert(ignore_permissions=True)
				frappe.msgprint(
					_("Created Item: {0}").format(
						frappe.utils.get_link_to_form("Item", target_name)
					),
					alert=True,
					indicator="blue",
				)
			row.building_type = target_name
			frappe.db.set_value(
				"Item", target_name, "reserved_unit", flt(row.reserved_unit),
				update_modified=False,
			)

	def calculate_totals(self):
		total = 0
		for row in self.get("project_units") or []:
			row.amount = flt(row.unit) * flt(row.rate)
			row.sellable_unit = flt(row.unit) - flt(row.reserved_unit)
			total += flt(row.unit)
		self.total_units = total
```

- [ ] **Step 5: Run all Site tests; expect green**

```bash
bench --site <dev-site> run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_site_template_data
bench --site <dev-site> run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_per_site_items
```
Expected: all pass. If `Warehouse "Stores - DTD"` doesn't exist on the dev site, `test_auto_created_item_has_hardcoded_defaults` will skip the warehouse assertion (the test guards for that). The setup-precondition test deletes/restores `Item Group PROPERTIES`.

- [ ] **Step 6: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/doctype/site/site.py \
        dantata_town/dantata_town/tests/test_site_template_data.py \
        dantata_town/dantata_town/tests/test_per_site_items.py
git commit -m "feat(site): auto-create per-site Item from typed template_item with hardcoded defaults; compute sellable_unit"
```

---

## Task 3: Quotation Sellable cap

**Files:**
- Modify: `dantata_town/dantata_town/quotation.py` (extend, do not replace)
- Modify: `dantata_town/hooks.py` (extend Quotation entry)
- Create: `dantata_town/dantata_town/tests/test_sellable_cap.py`

- [ ] **Step 1: Write the failing test file**

Create `dantata_town/dantata_town/tests/test_sellable_cap.py`:

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today

from dantata_town.dantata_town.setup import create_boq_custom_fields
from dantata_town.dantata_town.tests._helpers import get_test_expense_account


def _ensure_setup():
	create_boq_custom_fields()
	if not frappe.db.exists("Item Group", "PROPERTIES"):
		frappe.get_doc({
			"doctype": "Item Group",
			"item_group_name": "PROPERTIES",
			"parent_item_group": "All Item Groups",
			"is_group": 0,
		}).insert(ignore_permissions=True)
	if not frappe.db.exists("UOM", "Unit"):
		frappe.get_doc({"doctype": "UOM", "uom_name": "Unit"}).insert(ignore_permissions=True)


def _make_site_with_cap(template, unit, reserved):
	"""Make a Site with one project_unit row and return (site_name, per_site_item_code)."""
	site = frappe.get_doc({
		"doctype": "Site",
		"site_name": f"CapSite-{frappe.generate_hash(length=6)}",
		"expense_account": get_test_expense_account(),
		"project_units": [{
			"template_item": template,
			"unit": unit,
			"reserved_unit": reserved,
			"uom": "Unit",
			"rate": 1000,
		}],
	}).insert(ignore_permissions=True)
	return site.name, site.project_units[0].building_type


def _make_quotation(item_code, qty, save=True, submit=False):
	customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
	q = frappe.get_doc({
		"doctype": "Quotation",
		"quotation_to": "Customer",
		"party_name": customer,
		"transaction_date": today(),
		"valid_till": today(),
		"payment_type": "Outright",
		"items": [{
			"item_code": item_code,
			"qty": qty,
			"rate": 1000,
		}],
	})
	if save:
		q.insert(ignore_permissions=True)
	if submit:
		q.submit()
	return q


class TestSellableCap(FrappeTestCase):
	def setUp(self):
		_ensure_setup()

	def test_quotation_within_cap_saves(self):
		_, item = _make_site_with_cap("Cap-A", unit=10, reserved=2)  # sellable=8
		q = _make_quotation(item, qty=5)
		self.assertTrue(frappe.db.exists("Quotation", q.name))

	def test_quotation_exceeding_cap_throws(self):
		_, item = _make_site_with_cap("Cap-B", unit=10, reserved=2)  # sellable=8
		_make_quotation(item, qty=5)
		with self.assertRaises(frappe.ValidationError) as cm:
			_make_quotation(item, qty=4)  # 5 + 4 = 9 > 8
		self.assertIn("sellable", str(cm.exception).lower())

	def test_cancelling_quotation_frees_cap(self):
		_, item = _make_site_with_cap("Cap-C", unit=10, reserved=2)  # sellable=8
		q1 = _make_quotation(item, qty=5, submit=True)
		# Now cancel q1; cap should free up.
		q1.cancel()
		q2 = _make_quotation(item, qty=8)
		self.assertTrue(frappe.db.exists("Quotation", q2.name))

	def test_submitted_quotation_counts(self):
		_, item = _make_site_with_cap("Cap-D", unit=10, reserved=2)  # sellable=8
		_make_quotation(item, qty=5, submit=True)
		with self.assertRaises(frappe.ValidationError):
			_make_quotation(item, qty=4)

	def test_non_site_item_skipped(self):
		# Item exists but is not referenced on any Site row → cap does not apply.
		other = frappe.db.get_value("Item", {"is_sales_item": 1, "disabled": 0}, "name")
		if not other:
			self.skipTest("No sales-enabled Item available")
		q = _make_quotation(other, qty=99999)
		self.assertTrue(frappe.db.exists("Quotation", q.name))
```

- [ ] **Step 2: Run; expect failures because `check_sellable_cap` doesn't exist and hook isn't wired**

```bash
bench --site <dev-site> run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_sellable_cap
```
Expected: `test_quotation_exceeding_cap_throws` and `test_submitted_quotation_counts` fail (quotation 2 saves successfully because no cap is enforced yet).

- [ ] **Step 3: Add `check_sellable_cap` to `quotation.py`**

Append to `dantata_town/dantata_town/quotation.py` (after the existing `_validate_installment_inputs` function):

```python
def check_sellable_cap(doc, method=None):
	"""Block save when sum of qty across non-cancelled Quotation Items
	(excluding this Quotation) plus this Quotation's qty would exceed the
	Sellable cap on the matching Site row.

	Quotation Items whose item_code is not a building_type on any Site row
	are silently skipped (not site-tracked).
	"""
	this_qty: dict[str, float] = {}
	for row in doc.items:
		this_qty[row.item_code] = this_qty.get(row.item_code, 0) + flt(row.qty)

	for item_code, qty_on_this in this_qty.items():
		site_row = frappe.db.sql(
			"""
			select parent as site, sellable_unit
			from `tabProject Unit Item`
			where parenttype = 'Site' and building_type = %s
			limit 1
			""",
			(item_code,),
			as_dict=True,
		)
		if not site_row:
			continue
		cap = flt(site_row[0].sellable_unit)

		other = frappe.db.sql(
			"""
			select coalesce(sum(qi.qty), 0)
			from `tabQuotation Item` qi
			join `tabQuotation` q on q.name = qi.parent
			where q.docstatus != 2
			  and q.name != %s
			  and qi.item_code = %s
			""",
			(doc.name or "", item_code),
		)
		other_qty = flt(other[0][0] if other else 0)

		if (other_qty + qty_on_this) > cap:
			available = cap - other_qty
			frappe.throw(_(
				"Cannot quote {0} of {1}: only {2} sellable on {3} "
				"(already on other quotations: {4})."
			).format(
				qty_on_this, item_code, available, site_row[0].site, other_qty
			))
```

- [ ] **Step 4: Wire the hook in `hooks.py`**

In `dantata_town/hooks.py`, find the existing Quotation entry (around lines 157-159):

```python
	"Quotation": {
		"validate": "dantata_town.dantata_town.quotation.validate_quotation_payment_type",
	},
```

Replace with:

```python
	"Quotation": {
		"validate": [
			"dantata_town.dantata_town.quotation.validate_quotation_payment_type",
			"dantata_town.dantata_town.quotation.check_sellable_cap",
		],
	},
```

- [ ] **Step 5: Run tests; expect green**

```bash
bench --site <dev-site> run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_sellable_cap
```
Expected: 5 passes.

- [ ] **Step 6: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/quotation.py \
        dantata_town/hooks.py \
        dantata_town/dantata_town/tests/test_sellable_cap.py
git commit -m "feat(quotation): cap total qty per item against Site Sellable Quantity"
```

---

## Task 4: Sales Order Amount recompute on SO submit/cancel

**Files:**
- Modify: `dantata_town/dantata_town/project_aggregations.py`
- Modify: `dantata_town/hooks.py` (extend Sales Order entry)
- Modify: `dantata_town/dantata_town/tests/test_project_aggregations.py`

- [ ] **Step 1: Add a failing test for SO submit/cancel updating `total_sales_amount`**

Append a new test class to `dantata_town/dantata_town/tests/test_project_aggregations.py` (after `TestProjectAggregationHooks` and before `TestProjectCompletion`):

```python
class TestSalesOrderAmountRecompute(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		from dantata_town.dantata_town.tests._helpers import get_test_expense_account
		self.expense_account = get_test_expense_account()
		if not frappe.db.exists("Item Group", "PROPERTIES"):
			frappe.get_doc({
				"doctype": "Item Group",
				"item_group_name": "PROPERTIES",
				"parent_item_group": "All Item Groups",
				"is_group": 0,
			}).insert(ignore_permissions=True)
		if not frappe.db.exists("UOM", "Unit"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "Unit"}).insert(ignore_permissions=True)

	def _make_site_project_and_so(self, qty: float = 1, rate: float = 1000000):
		"""Build Site (with auto-created per-site Item), Project linked to Site, and
		one submitted SO that quotes the per-site Item with project field SET."""
		template = "SO-Amt"
		site = frappe.get_doc({
			"doctype": "Site",
			"site_name": f"SOAmtSite-{frappe.generate_hash(length=6)}",
			"expense_account": self.expense_account,
			"project_units": [{
				"template_item": template,
				"unit": 10,
				"uom": "Unit",
				"rate": rate,
			}],
		}).insert(ignore_permissions=True)
		per_site_item = site.project_units[0].building_type
		customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
		company = frappe.db.get_single_value("Global Defaults", "default_company")
		project = frappe.get_doc({
			"doctype": "Project",
			"project_name": f"SOAmtProj-{frappe.generate_hash(length=6)}",
			"customer": customer,
			"company": company,
			"site": site.name,
			"project_type": "Building",
			"project_subtype": "PLOT",
		}).insert(ignore_permissions=True)
		so = frappe.get_doc({
			"doctype": "Sales Order",
			"customer": customer,
			"company": company,
			"transaction_date": today(),
			"delivery_date": add_days(today(), 7),
			"project": project.name,
			"items": [{
				"item_code": per_site_item,
				"qty": qty,
				"rate": rate,
				"delivery_date": add_days(today(), 7),
			}],
		})
		so.set_missing_values()
		so.insert(ignore_permissions=True)
		so.submit()
		return site.name, project.name, so.name

	def test_so_submit_updates_total_sales_amount(self):
		_, project, _so = self._make_site_project_and_so(qty=1, rate=2_500_000)
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "total_sales_amount")),
			2_500_000,
		)

	def test_so_cancel_zeros_total_sales_amount(self):
		_, project, so_name = self._make_site_project_and_so(qty=1, rate=1_500_000)
		frappe.get_doc("Sales Order", so_name).cancel()
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "total_sales_amount")),
			0,
		)
```

- [ ] **Step 2: Run; expect failures because no recompute fires on SO events**

```bash
bench --site <dev-site> run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_project_aggregations --test TestSalesOrderAmountRecompute
```
Expected: both tests fail (total_sales_amount stays at 0).

- [ ] **Step 3: Extend `project_aggregations.py`**

In `dantata_town/dantata_town/project_aggregations.py`, replace the `recalc_project_totals` function body (lines 10-34) with:

```python
def recalc_project_totals(project: str | None) -> None:
	"""Recompute project_expenses, project_payment, and total_sales_amount from submitted docs.

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
	sales = _sum_sales_orders(project)
	frappe.db.set_value(
		"Project",
		project,
		{
			"project_expenses": expenses,
			"project_payment": payment,
			"total_sales_amount": sales,
		},
		update_modified=False,
	)
```

Add a new helper near the other `_sum_*` functions (immediately above `recalc_project_completion`):

```python
def _sum_sales_orders(project: str) -> float:
	rows = frappe.db.sql(
		"""
		select coalesce(sum(base_net_total), 0)
		from `tabSales Order`
		where project = %s and docstatus = 1
		""",
		(project,),
	)
	return flt(rows[0][0]) if rows else 0
```

Extend `_projects_touched_by` — add this branch before the closing `return projects` line:

```python
	elif dt == "Sales Order":
		if doc.get("project"):
			projects.add(doc.project)
```

- [ ] **Step 4: Wire the Sales Order on_submit / on_cancel hook**

In `dantata_town/hooks.py`, replace the existing Sales Order doc_events block (lines 205-211):

```python
	"Sales Order": {
		"before_validate": "dantata_town.dantata_town.sales_order.fetch_from_project",
		"validate": [
			"dantata_town.dantata_town.sales_order.enforce_one_so_per_project",
			"dantata_town.dantata_town.sales_order.check_reservations",
		],
	},
```

With:

```python
	"Sales Order": {
		"before_validate": "dantata_town.dantata_town.sales_order.fetch_from_project",
		"validate": [
			"dantata_town.dantata_town.sales_order.enforce_one_so_per_project",
			"dantata_town.dantata_town.sales_order.check_reservations",
		],
		"on_submit": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
		"on_cancel": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
	},
```

- [ ] **Step 5: Run tests**

```bash
bench --site <dev-site> run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_project_aggregations
```
Expected: all tests pass — both new SO tests and the existing project_aggregations tests (no regression).

- [ ] **Step 6: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/project_aggregations.py \
        dantata_town/hooks.py \
        dantata_town/dantata_town/tests/test_project_aggregations.py
git commit -m "feat(project): recompute total_sales_amount on SO submit/cancel"
```

---

## Task 5: Reposition `total_sales_amount` into the Financials section

**Files:**
- Modify: `dantata_town/dantata_town/setup.py` (extend `_create_property_setters`)

- [ ] **Step 1: Add the `insert_after` property setter**

In `dantata_town/dantata_town/setup.py:_create_property_setters`, find the `property_setters` list (starts at line 314). Add a new tuple after the existing `total_sales_amount` entries (after line 324):

```python
		("Project", "total_sales_amount", "insert_after", "dt_financials_section", "Data"),
```

The list should now read (around that block):

```python
		("Project", "total_sales_amount", "hidden", "0", "Check"),
		("Project", "total_sales_amount", "label", "Sales Order Amount", "Data"),
		("Project", "total_sales_amount", "insert_after", "dt_financials_section", "Data"),
		("Project", "project_name", "unique", "0", "Check"),
```

- [ ] **Step 2: Apply the property setter via migrate**

```bash
bench --site <dev-site> migrate
```
Expected: migrate succeeds; the new Property Setter row appears in `tabProperty Setter`.

- [ ] **Step 3: Verify the position visually (manual check, recorded as a TODO in the commit)**

Open the Project form in the dev site, scroll to the Financials section. `Sales Order Amount` should appear immediately under the section header, before `Project Expenses`. If Frappe's `insert_after` property setter does not move the field at runtime for a core ERPNext field, fall back by adding an `idx` property setter:

```python
		("Project", "total_sales_amount", "idx", <one less than project_expenses.idx>, "Int"),
```
(read `idx` from `tabDocField` for `Project.project_expenses` first; this is a runtime check, not a step to run unconditionally).

- [ ] **Step 4: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/setup.py
git commit -m "feat(project): move Sales Order Amount to top of Financials section"
```

---

## Task 6: Backfill patch for existing Projects' `total_sales_amount`

**Files:**
- Create: `dantata_town/patches/recalc_sales_amount_for_existing_projects.py`
- Modify: `dantata_town/patches.txt`

- [ ] **Step 1: Create the patch file**

`dantata_town/patches/recalc_sales_amount_for_existing_projects.py`:

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from dantata_town.dantata_town.project_aggregations import recalc_project_totals


def execute():
	"""One-time backfill: recompute Project.total_sales_amount for every Project
	that has at least one submitted Sales Order linked. Phase-4 added the field
	display but never wired a recompute trigger, so existing data never refreshed."""
	projects = frappe.db.sql_list(
		"""
		select distinct project from `tabSales Order`
		where docstatus = 1 and ifnull(project, '') != ''
		"""
	)
	for p in projects:
		recalc_project_totals(p)
	frappe.db.commit()
```

- [ ] **Step 2: Register the patch in `patches.txt`**

Open `dantata_town/patches.txt`. Under the `[post_model_sync]` section, append a new line below the existing `rename_project_unit_item_fields` entry:

```
dantata_town.patches.recalc_sales_amount_for_existing_projects
```

So the section reads:

```
[post_model_sync]
# Patches added in this section will be executed after doctypes are migrated
dantata_town.patches.rename_project_unit_item_fields
dantata_town.patches.recalc_sales_amount_for_existing_projects
```

- [ ] **Step 3: Run migrate to execute the patch**

```bash
bench --site <dev-site> migrate
```
Expected: patch runs; any pre-existing Project with a submitted SO now shows its amount.

- [ ] **Step 4: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/patches/recalc_sales_amount_for_existing_projects.py \
        dantata_town/patches.txt
git commit -m "feat(patch): backfill total_sales_amount for existing Projects with submitted SOs"
```

---

## Task 7: Auto-link orphan SOs on Project save

**Files:**
- Create: `dantata_town/dantata_town/project.py`
- Modify: `dantata_town/hooks.py` (extend Project entry)
- Modify: `dantata_town/dantata_town/tests/test_project_aggregations.py`

- [ ] **Step 1: Write failing tests for the auto-link behavior**

Append to `dantata_town/dantata_town/tests/test_project_aggregations.py` (after the `TestSalesOrderAmountRecompute` class added in Task 4):

```python
class TestAutoLinkOrphanSO(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		from dantata_town.dantata_town.tests._helpers import get_test_expense_account
		self.expense_account = get_test_expense_account()
		if not frappe.db.exists("Item Group", "PROPERTIES"):
			frappe.get_doc({
				"doctype": "Item Group",
				"item_group_name": "PROPERTIES",
				"parent_item_group": "All Item Groups",
				"is_group": 0,
			}).insert(ignore_permissions=True)
		if not frappe.db.exists("UOM", "Unit"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "Unit"}).insert(ignore_permissions=True)

	def _make_site(self, template="AutoLink"):
		return frappe.get_doc({
			"doctype": "Site",
			"site_name": f"LinkSite-{frappe.generate_hash(length=6)}",
			"expense_account": self.expense_account,
			"project_units": [{
				"template_item": template,
				"unit": 10,
				"uom": "Unit",
				"rate": 1000000,
			}],
		}).insert(ignore_permissions=True)

	def _submit_orphan_so(self, site_doc, qty=1, rate=1_000_000):
		"""Submit an SO citing the Site's per-site Item with NO project link."""
		customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
		company = frappe.db.get_single_value("Global Defaults", "default_company")
		per_site_item = site_doc.project_units[0].building_type
		so = frappe.get_doc({
			"doctype": "Sales Order",
			"customer": customer,
			"company": company,
			"transaction_date": today(),
			"delivery_date": add_days(today(), 7),
			"items": [{
				"item_code": per_site_item,
				"qty": qty,
				"rate": rate,
				"delivery_date": add_days(today(), 7),
			}],
		})
		so.set_missing_values()
		so.insert(ignore_permissions=True)
		so.submit()
		return so.name

	def _make_project(self, site_name):
		customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
		company = frappe.db.get_single_value("Global Defaults", "default_company")
		return frappe.get_doc({
			"doctype": "Project",
			"project_name": f"LinkProj-{frappe.generate_hash(length=6)}",
			"customer": customer,
			"company": company,
			"site": site_name,
			"project_type": "Building",
			"project_subtype": "PLOT",
		}).insert(ignore_permissions=True)

	def test_single_orphan_so_gets_linked_on_project_save(self):
		site = self._make_site("AutoLink-Solo")
		so_name = self._submit_orphan_so(site, qty=1, rate=1_500_000)
		project = self._make_project(site.name)
		self.assertEqual(
			frappe.db.get_value("Sales Order", so_name, "project"),
			project.name,
		)
		self.assertEqual(
			flt(frappe.db.get_value("Project", project.name, "total_sales_amount")),
			1_500_000,
		)

	def test_multiple_orphans_throw_on_project_save(self):
		site = self._make_site("AutoLink-Multi")
		so_a = self._submit_orphan_so(site, qty=1, rate=1_000_000)
		so_b = self._submit_orphan_so(site, qty=1, rate=2_000_000)
		with self.assertRaises(frappe.ValidationError) as cm:
			self._make_project(site.name)
		msg = str(cm.exception)
		self.assertIn(so_a, msg)
		self.assertIn(so_b, msg)

	def test_orphan_on_different_site_is_not_linked(self):
		site_a = self._make_site("AutoLink-A")
		site_b = self._make_site("AutoLink-B")
		so_a = self._submit_orphan_so(site_a, qty=1, rate=1_000_000)
		# Save a Project on Site B → SO on Site A must NOT be linked.
		project_b = self._make_project(site_b.name)
		self.assertIsNone(frappe.db.get_value("Sales Order", so_a, "project"))
		self.assertEqual(
			flt(frappe.db.get_value("Project", project_b.name, "total_sales_amount")),
			0,
		)
```

- [ ] **Step 2: Run; expect failures (`project.py` doesn't exist, no hook)**

```bash
bench --site <dev-site> run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_project_aggregations --test TestAutoLinkOrphanSO
```
Expected: 3 failures — SO stays unlinked; Project save doesn't throw on multi-orphans.

- [ ] **Step 3: Create the `project.py` module**

Create `dantata_town/dantata_town/project.py`:

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _

from dantata_town.dantata_town.project_aggregations import recalc_project_totals


def auto_link_orphan_sales_orders(doc, method=None):
	"""When a Project is saved with a Site link, find submitted Sales Orders
	whose items belong to that Site and that have no project link, and:
	  - If exactly one matches → set SO.project = this Project, recompute totals.
	  - If multiple match → throw with the candidate list (user must link manually).
	  - If none match → no-op.

	Idempotent: already-linked SOs are excluded by the `so.project IS NULL`
	filter, so repeated saves do not re-link anything.
	"""
	if not doc.site:
		return
	candidates = frappe.db.sql(
		"""
		select distinct so.name
		from `tabSales Order` so
		join `tabSales Order Item` soi on soi.parent = so.name
		join `tabProject Unit Item` pui
		     on pui.building_type = soi.item_code
		    and pui.parenttype = 'Site'
		    and pui.parent = %(site)s
		where so.docstatus = 1
		  and (so.project is null or so.project = '')
		""",
		{"site": doc.site},
		as_dict=True,
	)
	if not candidates:
		return
	if len(candidates) > 1:
		names = ", ".join(c.name for c in candidates)
		frappe.throw(_(
			"Multiple unlinked Sales Orders match Site {0}: {1}. "
			"Open the correct one and set its Project field manually."
		).format(doc.site, names))

	so_name = candidates[0].name
	frappe.db.set_value(
		"Sales Order", so_name, "project", doc.name, update_modified=False
	)
	recalc_project_totals(doc.name)
	frappe.msgprint(
		_("Linked Sales Order {0} to this Project.").format(
			frappe.utils.get_link_to_form("Sales Order", so_name)
		),
		alert=True,
		indicator="blue",
	)
```

- [ ] **Step 4: Wire the Project on_update hook**

In `dantata_town/hooks.py`, the existing Project entry (around lines 151-156) reads:

```python
	"Project": {
		"validate": [
			"dantata_town.dantata_town.utils.validate_project_has_site",
			"dantata_town.dantata_town.utils.validate_project_subtype_matches_type",
		],
	},
```

Replace with:

```python
	"Project": {
		"validate": [
			"dantata_town.dantata_town.utils.validate_project_has_site",
			"dantata_town.dantata_town.utils.validate_project_subtype_matches_type",
		],
		"on_update": "dantata_town.dantata_town.project.auto_link_orphan_sales_orders",
	},
```

- [ ] **Step 5: Run tests**

```bash
bench --site <dev-site> run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_project_aggregations --test TestAutoLinkOrphanSO
```
Expected: 3 passes.

- [ ] **Step 6: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/project.py \
        dantata_town/hooks.py \
        dantata_town/dantata_town/tests/test_project_aggregations.py
git commit -m "feat(project): auto-link orphan SO to Project on save when Site matches"
```

---

## Task 8: Full test suite + manual smoke + discussion log

**Files:**
- No code changes; verification + documentation only.

- [ ] **Step 1: Run the full app test suite**

```bash
cd /home/okeke/clients/graceco/frappe-bench
bench --site <dev-site> run-tests --app dantata_town
```
Expected: at least the 128 prior tests + the new tests from Tasks 1–7 pass (total ≥ 140-ish). 5 skips from prior runs may remain.

- [ ] **Step 2: Manual smoke test (record outcome in the discussion log)**

1. In the dev site, create a new Site `Smoke Block X` with one project_unit row: `template_item="2-Bed Flat"`, unit=5, reserved=1, uom="Unit", rate=1,000,000.
2. Save → verify the Item `Smoke Block X - 2-Bed Flat` was created with item_group=PROPERTIES, stock_uom=Unit, is_stock_item=1, default_warehouse=Stores - DTD. The Site grid shows Sellable = 4.
3. Draft Quotation A for 3 units of `Smoke Block X - 2-Bed Flat` → saves. Draft Quotation B for 2 units → save throws ("Cannot quote 2 of … only 1 sellable …").
4. Reduce Quotation B to qty=1 → saves. Submit Quotation A.
5. Create Sales Order from Quotation A (project blank), submit it.
6. From the Site dashboard, create a new Project with `site=Smoke Block X` and a project_type → on save, you see "Linked Sales Order X to this Project." message. Open the Project: Financials section shows Sales Order Amount = 3,000,000 above Project Expenses.

- [ ] **Step 3: Write the discussion log**

Create `~/my-second-brain/docs/discussions/dantata-template-data-sellable-implementation.md`:

```markdown
# Dantata Town: template_item Data field, Sellable Quantity, SO amount refresh

## What was built (2026-05-22)

1. `Project Unit Item.template_item`: Link→Data. Users type the property type name; system auto-creates `{site} - {typed}` Item with hardcoded defaults (item_group=PROPERTIES, stock_uom=Unit, is_stock_item=1, is_purchase_item=1, is_sales_item=1, grant_commission=1, default_warehouse=Stores - DTD).
2. `Project Unit Item.sellable_unit`: new stored Float column = unit - reserved_unit.
3. Quotation cap: sum(qty on all non-cancelled Quotation Items) per item must not exceed `sellable_unit` on the matching Site row.
4. `Project.total_sales_amount`: recomputes on SO submit/cancel + on Project save; backfill patch ran once on migrate to refresh existing data.
5. `Sales Order Amount` moved to top of Project's Financials section (left column, above Project Expenses).
6. Auto-link: when a Project is saved with `site=X`, the system finds a single submitted SO on Site X with `project IS NULL` and links it. If multiple orphans exist, it throws with the candidate list.

## Files changed
- doctype/project_unit_item/project_unit_item.json
- doctype/site/site.py
- quotation.py (extended)
- project_aggregations.py (extended)
- project.py (new)
- setup.py (property setter)
- hooks.py
- patches/recalc_sales_amount_for_existing_projects.py (+ patches.txt)
- tests/test_per_site_items.py (adapted to Data field)
- tests/test_site_template_data.py (new)
- tests/test_sellable_cap.py (new)
- tests/test_project_aggregations.py (extended)

## TODO if anything regresses
- If property setter `insert_after` does not move `total_sales_amount` at runtime on this Frappe build, switch to an `idx` property setter (see Task 5 fallback note).
- If the "Stores - DTD" warehouse is renamed in production, the constant in `site.py` (`PER_SITE_DEFAULT_WAREHOUSE`) must be updated.
- Customer History (Phase 2 remaining item) is still pending and out of scope here.
```

- [ ] **Step 4: Final commit (no code, just docs if relevant)**

If the discussion log lives in `~/my-second-brain/` (separate from this repo), no commit needed in the app repo. Otherwise:

```bash
git add docs/superpowers/plans/2026-05-22-site-template-sellable.md
git status  # confirm nothing else is staged
git commit -m "docs: discussion log for template Data field + Sellable + SO amount work"
```

---

## Self-Review

**Spec coverage check:**
- Spec §1 (Schema) → Task 1 ✓
- Spec §2 (Per-site Item defaults) → Task 2 ✓
- Spec §3 (Sellable stored) → Task 2 (calculate_totals) ✓
- Spec §4 (Quotation cap) → Task 3 ✓
- Spec §5 (SO recompute + reposition + backfill) → Tasks 4, 5, 6 ✓
- Spec §6 (Auto-link) → Task 7 ✓
- Spec testing section → Tasks 1–7 inline TDD + Task 8 manual smoke ✓

**Placeholder scan:** No "TBD" / "TODO inside steps" / unspecified handlers / hand-waved error handling. Task 5 explicitly flags `idx` as a runtime fallback contingency, with the read-then-set procedure spelled out.

**Type consistency check:**
- `template_item` referenced consistently as Data (fieldtype) and string (in tests).
- `sellable_unit` referenced consistently as Float / read_only / stored.
- `auto_link_orphan_sales_orders(doc, method=None)` signature matches Frappe hook convention everywhere it's invoked.
- `recalc_project_totals(project: str | None)` signature unchanged from prior code; new `_sum_sales_orders(project: str)` follows same shape as `_sum_*` peers.
- Hardcoded constants `PER_SITE_ITEM_GROUP`, `PER_SITE_STOCK_UOM`, `PER_SITE_DEFAULT_WAREHOUSE` used in `site.py` only — tests reference the same literal strings, so no symbol mismatch.
