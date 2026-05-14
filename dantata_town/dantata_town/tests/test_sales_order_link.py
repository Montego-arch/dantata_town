# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from dantata_town.dantata_town.setup import create_boq_custom_fields


class TestProjectNameNotUnique(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()

	def test_project_name_field_not_unique(self):
		"""Property setter must turn off `unique` on Project.project_name (or be absent if already not unique)."""
		unique = frappe.db.get_value(
			"Property Setter",
			{
				"doc_type": "Project",
				"field_name": "project_name",
				"property": "unique",
			},
			"value",
		)
		# Either a property setter explicitly sets 0, or no setter and core already has unique=0.
		self.assertIn(unique, (None, "0"))
		# Meta must agree.
		meta = frappe.get_meta("Project")
		project_name_field = next(f for f in meta.fields if f.fieldname == "project_name")
		self.assertEqual(project_name_field.unique or 0, 0)

	def test_two_projects_with_same_name_allowed(self):
		"""Inserting two Projects with the same project_name on different Sites must succeed."""
		from frappe.utils import flt
		customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
		if not customer:
			self.skipTest("No customer available")

		from dantata_town.dantata_town.tests.test_project_aggregations import _make_site_and_project

		# Use the same project_name across two sites/projects.
		shared_name = f"Shared-{frappe.generate_hash(length=8)}"
		site1, _ = _make_site_and_project()
		site2, _ = _make_site_and_project()

		p1 = frappe.get_doc({
			"doctype": "Project",
			"project_name": shared_name,
			"customer": customer,
			"site": site1,
			"project_type": "Building",
			"project_subtype": "PLOT",
		}).insert(ignore_permissions=True)

		p2 = frappe.get_doc({
			"doctype": "Project",
			"project_name": shared_name,
			"customer": customer,
			"site": site2,
			"project_type": "Building",
			"project_subtype": "PLOT",
		}).insert(ignore_permissions=True)

		# Both projects must coexist. Their `name`s (autoname series) differ.
		self.assertEqual(p1.project_name, shared_name)
		self.assertEqual(p2.project_name, shared_name)
		self.assertNotEqual(p1.name, p2.name)


class TestSalesOrderProjectHooks(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		# Look up an existing Customer + Item for fixture reuse.
		customer = frappe.get_all("Customer", {"disabled": 0}, limit=1, pluck="name")
		if not customer:
			self.skipTest("No customer in this site")
		self.customer = customer[0]
		item = frappe.get_all("Item", filters={"is_stock_item": 0, "disabled": 0}, limit=1, pluck="name")
		if not item:
			self.skipTest("No non-stock item in this site")
		self.item = item[0]

	def _make_project(self):
		from dantata_town.dantata_town.tests.test_project_aggregations import _make_site_and_project
		_, project = _make_site_and_project()
		return frappe.get_doc("Project", project)

	def _make_so(self, project, customer=None, qty=1):
		from frappe.utils import today, add_days
		so = frappe.new_doc("Sales Order")
		if customer:
			so.customer = customer
		so.project = project.name
		so.company = project.company
		so.transaction_date = today()
		so.delivery_date = add_days(today(), 7)
		cost_center = frappe.db.get_value(
			"Cost Center",
			{"company": project.company, "is_group": 0},
			"name",
		)
		so.cost_center = cost_center
		so.append("items", {
			"item_code": self.item,
			"qty": qty,
			"rate": 100,
			"delivery_date": add_days(today(), 7),
			"cost_center": cost_center,
		})
		return so

	def test_customer_fetched_from_project_when_missing(self):
		project = self._make_project()
		so = self._make_so(project, customer=None)
		so.insert(ignore_permissions=True)
		self.assertEqual(so.customer, project.customer)

	def test_existing_customer_not_overwritten(self):
		project = self._make_project()
		so = self._make_so(project, customer=self.customer)
		so.insert(ignore_permissions=True)
		self.assertEqual(so.customer, self.customer)

	def test_second_so_for_same_project_blocked(self):
		project = self._make_project()
		so1 = self._make_so(project)
		so1.insert(ignore_permissions=True)
		so1.submit()
		so2 = self._make_so(project)
		with self.assertRaisesRegex(frappe.ValidationError, "already linked"):
			so2.insert(ignore_permissions=True)

	def test_cancelled_so_does_not_block_new_one(self):
		project = self._make_project()
		so1 = self._make_so(project)
		so1.insert(ignore_permissions=True)
		so1.submit()
		so1.cancel()
		so2 = self._make_so(project)
		so2.insert(ignore_permissions=True)
		self.assertEqual(so2.project, project.name)


class TestExistingSOForProjectEndpoint(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()

	def test_returns_none_when_no_existing(self):
		from dantata_town.dantata_town.sales_order import existing_so_for_project
		from dantata_town.dantata_town.tests.test_project_aggregations import _make_site_and_project
		_, project = _make_site_and_project()
		self.assertIsNone(existing_so_for_project(project))

	def test_returns_so_name_when_one_exists(self):
		from dantata_town.dantata_town.sales_order import existing_so_for_project
		from dantata_town.dantata_town.tests.test_project_aggregations import _make_site_and_project
		from frappe.utils import today, add_days
		_, project = _make_site_and_project()
		# Look up customer + non-stock item + cost_center for fixture.
		customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
		item = frappe.db.get_value("Item", {"is_stock_item": 0, "disabled": 0}, "name")
		company = frappe.db.get_value("Project", project, "company")
		cost_center = frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")
		if not (customer and item and cost_center):
			self.skipTest("Fixture prerequisites unavailable")
		so = frappe.get_doc({
			"doctype": "Sales Order",
			"customer": customer,
			"company": company,
			"cost_center": cost_center,
			"project": project,
			"transaction_date": today(),
			"delivery_date": add_days(today(), 7),
			"items": [{
				"item_code": item,
				"qty": 1,
				"rate": 100,
				"delivery_date": add_days(today(), 7),
				"cost_center": cost_center,
			}],
		}).insert(ignore_permissions=True)
		so.submit()
		# When current_so excludes this SO, endpoint returns None.
		self.assertIsNone(existing_so_for_project(project, current_so=so.name))
		# Without excluding, endpoint returns the SO name.
		self.assertEqual(existing_so_for_project(project), so.name)
