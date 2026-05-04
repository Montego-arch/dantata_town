# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from dantata_town.dantata_town.setup import create_boq_custom_fields


class TestSubContractorFieldsInstalled(FrappeTestCase):
	def test_assignment_type_field_on_boq_items(self):
		create_boq_custom_fields()
		field = frappe.db.get_value(
			"Custom Field",
			{"dt": "BOQ Items", "fieldname": "assignment_type"},
			["fieldtype", "options", "default", "allow_on_submit", "in_list_view"],
			as_dict=True,
		)
		self.assertIsNotNone(field, "assignment_type missing on BOQ Items")
		self.assertEqual(field.fieldtype, "Select")
		self.assertEqual(field.options, "Company\nSub Contractor")
		self.assertEqual(field.default, "Company")
		self.assertEqual(field.allow_on_submit, 1)
		self.assertEqual(field.in_list_view, 1)

	def test_site_field_on_purchase_invoice(self):
		create_boq_custom_fields()
		field = frappe.db.get_value(
			"Custom Field",
			{"dt": "Purchase Invoice", "fieldname": "site"},
			["fieldtype", "options"],
			as_dict=True,
		)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "Site")

	def test_sub_contractor_payment_request_field_on_purchase_invoice(self):
		create_boq_custom_fields()
		field = frappe.db.get_value(
			"Custom Field",
			{"dt": "Purchase Invoice", "fieldname": "sub_contractor_payment_request"},
			["fieldtype", "options", "read_only"],
			as_dict=True,
		)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "Sub Contractor Payment Request")
		self.assertEqual(field.read_only, 1)

	def test_expense_account_field_on_site(self):
		"""Site.expense_account is JSON-defined, not a Custom Field — verify via meta."""
		meta = frappe.get_meta("Site")
		field = meta.get_field("expense_account")
		self.assertIsNotNone(field, "expense_account missing on Site")
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "Account")


from frappe.utils import today, add_days, flt

from dantata_town.dantata_town.sub_contractor import (
	make_request_from_boq,
)


def _make_site_and_project_for_flow():
	create_boq_custom_fields()
	uom = frappe.db.get_value("UOM", {}, "name")
	item = frappe.db.get_value("Item", {"disabled": 0}, "name")
	customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
	company = frappe.db.get_single_value("Global Defaults", "default_company") \
		or frappe.db.get_value("Company", {}, "name")
	site = frappe.get_doc({
		"doctype": "Site",
		"site_name": f"Flow-Site-{frappe.generate_hash(length=6)}",
		"project_units": [{"building_type": item, "unit": 1, "uom": uom, "rate": 1}],
	}).insert(ignore_permissions=True)
	project = frappe.get_doc({
		"doctype": "Project",
		"project_name": f"Flow-Proj-{frappe.generate_hash(length=6)}",
		"customer": customer,
		"company": company,
		"site": site.name,
		"project_type": "Building",
		"project_subtype": "PLOT",
	}).insert(ignore_permissions=True)
	return site.name, project.name


def _detail_for_flow():
	existing = frappe.db.get_value("BOQ Item Detail", {}, "name")
	if existing:
		return existing
	return frappe.get_doc({
		"doctype": "BOQ Item Detail",
		"description": f"Detail-{frappe.generate_hash(length=6)}",
		"description_type": "Material",
		"unit": "Nos",
	}).insert(ignore_permissions=True).name


def _make_submitted_boq(site, project, sub_count=1, company_count=1, stage=1):
	"""Create + submit a BOQ with N sub-contractor rows and M company rows in stage."""
	stage_table = {
		1: "table_txao", 2: "description2", 3: "description3",
		4: "description4", 5: "description5", 6: "description6", 7: "description7",
	}[stage]
	detail = _detail_for_flow()
	doc = frappe.new_doc("Bill of Quantities")
	doc.site = site
	doc.project = project
	doc.date = today()
	for _ in range(sub_count):
		doc.append(stage_table, {
			"description": detail, "planned_quantity": 5, "rate": 1000,
			"assignment_type": "Sub Contractor",
		})
	for _ in range(company_count):
		doc.append(stage_table, {
			"description": detail, "planned_quantity": 5, "rate": 1000,
			"assignment_type": "Company",
		})
	doc.set(f"stage_{stage}_start_date", today())
	doc.set(f"stage_{stage}_end_date", add_days(today(), 10))
	doc.set(f"stage_{stage}", f"Test Stage {stage}")
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


class TestMakeRequestFromBOQ(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		self.supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")

	def test_creates_draft_request_with_snapshots(self):
		site, project = _make_site_and_project_for_flow()
		boq_name = _make_submitted_boq(site, project, sub_count=1, company_count=1)
		boq = frappe.get_doc("Bill of Quantities", boq_name)
		# Pick the Sub Contractor row from stage 1
		sub_row = next(r for r in boq.table_txao if r.assignment_type == "Sub Contractor")
		import json
		req_name = make_request_from_boq(
			boq=boq_name,
			supplier=self.supplier,
			date=today(),
			selected=json.dumps([{
				"stage_label": "Stage 1 — Test Stage 1",
				"boq_item_name": sub_row.name,
				"description": sub_row.description,
				"unit": sub_row.unit,
				"quantity": sub_row.planned_quantity,
				"rate": sub_row.rate,
			}]),
		)
		req = frappe.get_doc("Sub Contractor Payment Request", req_name)
		self.assertEqual(req.docstatus, 0)
		self.assertEqual(req.boq, boq_name)
		self.assertEqual(req.site, site)
		self.assertEqual(req.project, project)
		self.assertEqual(req.supplier, self.supplier)
		self.assertEqual(len(req.items), 1)
		row = req.items[0]
		self.assertEqual(flt(row.original_quantity), 5)
		self.assertEqual(flt(row.original_rate), 1000)
		self.assertEqual(flt(row.quantity), 5)
		self.assertEqual(flt(row.rate), 1000)
		self.assertEqual(row.boq_item, sub_row.name)

	def test_empty_selection_raises(self):
		import json
		site, project = _make_site_and_project_for_flow()
		boq_name = _make_submitted_boq(site, project)
		with self.assertRaises(frappe.ValidationError):
			make_request_from_boq(
				boq=boq_name, supplier=self.supplier, date=today(),
				selected=json.dumps([]),
			)

	def test_draft_boq_raises(self):
		import json
		site, project = _make_site_and_project_for_flow()
		# Create a BOQ but DON'T submit it
		stage_table = "table_txao"
		detail = _detail_for_flow()
		doc = frappe.new_doc("Bill of Quantities")
		doc.site = site
		doc.project = project
		doc.date = today()
		doc.append(stage_table, {
			"description": detail, "planned_quantity": 5, "rate": 1000,
			"assignment_type": "Sub Contractor",
		})
		doc.stage_1_start_date = today()
		doc.stage_1_end_date = add_days(today(), 10)
		doc.insert(ignore_permissions=True)  # docstatus = 0
		with self.assertRaises(frappe.ValidationError):
			make_request_from_boq(
				boq=doc.name, supplier=self.supplier, date=today(),
				selected=json.dumps([{
					"stage_label": "Stage 1",
					"boq_item_name": doc.table_txao[0].name,
					"description": detail,
					"unit": "Nos",
					"quantity": 1,
					"rate": 100,
				}]),
			)

	def test_unknown_boq_raises(self):
		import json
		with self.assertRaises(frappe.ValidationError):
			make_request_from_boq(
				boq="DOES-NOT-EXIST", supplier=self.supplier, date=today(),
				selected=json.dumps([{"stage_label": "X", "boq_item_name": "Y",
				                     "description": "Z", "unit": "Nos",
				                     "quantity": 1, "rate": 1}]),
			)
