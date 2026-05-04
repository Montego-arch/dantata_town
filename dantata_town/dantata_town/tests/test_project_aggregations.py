# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today, add_days

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
	company = frappe.db.get_single_value("Global Defaults", "default_company")

	site = frappe.get_doc({
		"doctype": "Site",
		"site_name": f"AggSite-{frappe.generate_hash(length=6)}",
		"project_units": [{"building_type": item, "unit": 1, "uom": uom, "rate": 1}],
	}).insert(ignore_permissions=True)

	project = frappe.get_doc({
		"doctype": "Project",
		"project_name": f"AggProj-{frappe.generate_hash(length=6)}",
		"customer": customer,
		"company": company,
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


class TestProjectAggregationHooks(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()

	def _submit_purchase_invoice(self, project: str | None, amount: float = 1000) -> str:
		company = frappe.db.get_single_value("Global Defaults", "default_company")
		supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
		item = frappe.db.get_value("Item", {"is_purchase_item": 1, "disabled": 0}, "name") \
		       or frappe.db.get_value("Item", {"disabled": 0}, "name")
		credit_to = frappe.db.get_value(
			"Account", {"company": company, "account_type": "Payable", "is_group": 0}, "name"
		)
		expense_account = frappe.db.get_value(
			"Account",
			{"company": company, "root_type": "Expense", "account_type": "", "is_group": 0},
			"name",
		)
		cost_center = frappe.db.get_value(
			"Cost Center", {"company": company, "is_group": 0}, "name"
		)
		item_row = {
			"item_code": item,
			"qty": 1,
			"rate": amount,
			"expense_account": expense_account,
			"cost_center": cost_center,
		}
		if project:
			item_row["project"] = project
		pi = frappe.get_doc({
			"doctype": "Purchase Invoice",
			"company": company,
			"supplier": supplier,
			"posting_date": today(),
			"due_date": add_days(today(), 30),
			"bill_no": f"TEST-{frappe.generate_hash(length=6)}",
			"bill_date": today(),
			"credit_to": credit_to,
			"update_stock": 0,
			"items": [item_row],
		})
		pi.set_missing_values()
		pi.insert(ignore_permissions=True)
		pi.submit()
		return pi.name

	def test_purchase_invoice_submit_increases_project_expenses(self):
		_, project = _make_site_and_project()
		self._submit_purchase_invoice(project, amount=2500)
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_expenses")),
			2500,
		)

	def test_purchase_invoice_cancel_reverses_project_expenses(self):
		_, project = _make_site_and_project()
		pi_name = self._submit_purchase_invoice(project, amount=1500)
		pi = frappe.get_doc("Purchase Invoice", pi_name)
		pi.cancel()
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_expenses")),
			0,
		)

	def test_doc_with_no_project_is_noop(self):
		_, project = _make_site_and_project()
		# A PI without a project link must not affect the unrelated project's expenses.
		self._submit_purchase_invoice(project=None, amount=999)
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_expenses")),
			0,
		)
