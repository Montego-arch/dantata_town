# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from dantata_town.dantata_town.setup import create_boq_custom_fields


class TestProjectUnitItemSchema(FrappeTestCase):
	def test_template_item_field_exists(self):
		meta = frappe.get_meta("Project Unit Item")
		fieldnames = {f.fieldname for f in meta.fields}
		self.assertIn("template_item", fieldnames)
		template = next(f for f in meta.fields if f.fieldname == "template_item")
		self.assertEqual(template.fieldtype, "Data")
		self.assertEqual(template.reqd, 1)
		# Label is intentionally retained as "Template Item" even though type changed.
		self.assertEqual(template.label, "Template Item")

	def test_sellable_unit_field_exists(self):
		meta = frappe.get_meta("Project Unit Item")
		fieldnames = {f.fieldname for f in meta.fields}
		self.assertIn("sellable_unit", fieldnames)
		sellable = next(f for f in meta.fields if f.fieldname == "sellable_unit")
		self.assertEqual(sellable.fieldtype, "Float")
		self.assertEqual(sellable.read_only, 1)
		self.assertEqual(sellable.label, "Sellable")
		self.assertEqual(sellable.in_list_view, 1)

	def test_reserved_unit_field_exists(self):
		meta = frappe.get_meta("Project Unit Item")
		fieldnames = {f.fieldname for f in meta.fields}
		self.assertIn("reserved_unit", fieldnames)
		reserved = next(f for f in meta.fields if f.fieldname == "reserved_unit")
		self.assertEqual(reserved.fieldtype, "Float")

	def test_building_type_is_read_only(self):
		meta = frappe.get_meta("Project Unit Item")
		bt = next(f for f in meta.fields if f.fieldname == "building_type")
		self.assertEqual(bt.read_only, 1)

	def test_unit_label_is_total_units(self):
		meta = frappe.get_meta("Project Unit Item")
		unit_field = next(f for f in meta.fields if f.fieldname == "unit")
		self.assertEqual(unit_field.label, "Total Units")


class TestSiteAutoCreatesItems(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		from dantata_town.dantata_town.tests._helpers import (
			get_test_expense_account,
			ensure_site_preconditions,
		)
		self.expense_account = get_test_expense_account()
		ensure_site_preconditions()
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


class TestItemReservedUnitSync(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		from dantata_town.dantata_town.tests._helpers import (
			get_test_expense_account,
			ensure_site_preconditions,
		)
		self.expense_account = get_test_expense_account()
		ensure_site_preconditions()
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
