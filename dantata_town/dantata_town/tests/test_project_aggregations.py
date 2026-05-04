# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from dantata_town.dantata_town.setup import create_boq_custom_fields
from dantata_town.dantata_town.project_aggregations import (
	recalc_project_totals,
	recalc_for_doc,
)


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
