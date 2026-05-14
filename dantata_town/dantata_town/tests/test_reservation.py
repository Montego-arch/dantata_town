# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days

from dantata_town.dantata_town.setup import create_boq_custom_fields


class TestReservation(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		# Ensure a stable template item.
		self.template = "TPL-Reserve"
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
		self.customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
		if not self.customer:
			self.skipTest("No customer")
		self.company = frappe.db.get_single_value("Global Defaults", "default_company")
		self.cost_center = frappe.db.get_value(
			"Cost Center", {"company": self.company, "is_group": 0}, "name"
		)

	def _make_site_with_units(self, total=10, reserved=3):
		from dantata_town.dantata_town.tests._helpers import get_test_expense_account
		site = frappe.get_doc({
			"doctype": "Site",
			"site_name": f"Reserve-{frappe.generate_hash(length=6)}",
			"expense_account": get_test_expense_account(),
			"project_units": [{
				"template_item": self.template,
				"unit": total,
				"reserved_unit": reserved,
				"uom": "Nos",
				"rate": 1000,
			}],
		}).insert(ignore_permissions=True)
		return site

	def _make_project(self, site):
		return frappe.get_doc({
			"doctype": "Project",
			"project_name": f"ResProj-{frappe.generate_hash(length=6)}",
			"customer": self.customer,
			"company": self.company,
			"site": site.name,
			"project_type": "Building",
			"project_subtype": "PLOT",
		}).insert(ignore_permissions=True)

	def _make_so(self, project, item_code, qty):
		so = frappe.new_doc("Sales Order")
		so.customer = self.customer
		so.company = self.company
		so.cost_center = self.cost_center
		so.project = project.name
		so.transaction_date = today()
		so.delivery_date = add_days(today(), 7)
		so.append("items", {
			"item_code": item_code,
			"qty": qty,
			"rate": 1000,
			"delivery_date": add_days(today(), 7),
			"cost_center": self.cost_center,
		})
		return so

	def test_within_cap_succeeds(self):
		site = self._make_site_with_units(total=10, reserved=3)  # cap = 7
		item_code = site.project_units[0].building_type
		project = self._make_project(site)
		so = self._make_so(project, item_code, qty=7)
		so.insert(ignore_permissions=True)

	def test_above_cap_blocked(self):
		site = self._make_site_with_units(total=10, reserved=3)  # cap = 7
		item_code = site.project_units[0].building_type
		project = self._make_project(site)
		so = self._make_so(project, item_code, qty=8)
		with self.assertRaisesRegex(frappe.ValidationError, "remain available"):
			so.insert(ignore_permissions=True)

	def test_second_so_pushing_over_cap_blocked(self):
		site = self._make_site_with_units(total=10, reserved=3)  # cap = 7
		item_code = site.project_units[0].building_type
		# Two projects on this site (each project needs its own SO).
		p1 = self._make_project(site)
		so1 = self._make_so(p1, item_code, qty=5)
		so1.insert(ignore_permissions=True)
		so1.submit()
		p2 = self._make_project(site)
		so2 = self._make_so(p2, item_code, qty=3)  # 5 + 3 = 8 > 7
		with self.assertRaisesRegex(frappe.ValidationError, "remain available"):
			so2.insert(ignore_permissions=True)

	def test_item_not_in_any_site_bypasses_check(self):
		# A standalone Item that no Site.project_units references.
		freestanding = "Standalone-Item-NoSite"
		if not frappe.db.exists("Item", freestanding):
			item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
			frappe.get_doc({
				"doctype": "Item",
				"item_code": freestanding,
				"item_name": freestanding,
				"item_group": item_group,
				"is_stock_item": 0,
				"stock_uom": "Nos",
			}).insert(ignore_permissions=True)
		site = self._make_site_with_units(total=10, reserved=0)
		project = self._make_project(site)
		so = self._make_so(project, freestanding, qty=999)
		so.insert(ignore_permissions=True)
