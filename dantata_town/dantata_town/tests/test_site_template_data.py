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
