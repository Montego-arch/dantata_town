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
		from dantata_town.dantata_town.tests._helpers import get_test_expense_account
		site_name = frappe.generate_hash(length=8)
		site = frappe.get_doc({
			"doctype": "Site",
			"site_name": f"Test-{site_name}",
			"expense_account": get_test_expense_account(),
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
