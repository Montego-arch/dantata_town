# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from dantata_town.dantata_town.setup import create_boq_custom_fields


class TestProjectUnitItemSchema(FrappeTestCase):
	def test_template_item_field_exists(self):
		meta = frappe.get_meta("Project Unit Item")
		fieldnames = {f.fieldname for f in meta.fields}
		self.assertIn("template_item", fieldnames)
		template = next(f for f in meta.fields if f.fieldname == "template_item")
		self.assertEqual(template.fieldtype, "Link")
		self.assertEqual(template.options, "Item")
		self.assertEqual(template.reqd, 1)

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
		from dantata_town.dantata_town.tests._helpers import get_test_expense_account
		self.expense_account = get_test_expense_account()
		# Ensure a template Item exists.
		self.template = "TPL Apartments"
		if not frappe.db.exists("Item", self.template):
			item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
			frappe.get_doc({
				"doctype": "Item",
				"item_code": self.template,
				"item_name": self.template,
				"item_group": item_group,
				"is_stock_item": 0,
				"stock_uom": "Nos",
			}).insert(ignore_permissions=True)

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
			"uom": "Nos",
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
			"uom": "Nos",
			"rate": 1000,
		})
		site.insert(ignore_permissions=True)
		# Re-save: building_type should remain identical, no duplicate Item.
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
			"uom": "Nos",
			"rate": 100,
		})
		site.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			frappe.rename_doc("Site", site.name, f"{site.site_name}-renamed")

	def test_msgprint_fires_on_auto_create(self):
		"""When a new per-site Item is created, a msgprint should fire announcing it."""
		import frappe.utils.response
		# Clear messages.
		frappe.local.message_log = []
		site = self._make_site()
		site.append("project_units", {
			"template_item": self.template,
			"unit": 1,
			"uom": "Nos",
			"rate": 100,
		})
		site.insert(ignore_permissions=True)
		messages = frappe.local.message_log
		# At least one message mentions "Created Item".
		texts = [str(m) for m in messages]
		self.assertTrue(
			any("Created Item" in t for t in texts),
			f"No 'Created Item' message in {texts}",
		)
