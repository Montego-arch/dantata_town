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
