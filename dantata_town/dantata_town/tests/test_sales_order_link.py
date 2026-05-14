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
