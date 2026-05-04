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


from dantata_town.dantata_town.sub_contractor import (
	make_purchase_invoice,
)


def _ensure_subcon_cost_item():
	if frappe.db.exists("Item", "Sub Contractor Cost"):
		return
	item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") \
		or frappe.db.get_value("Item Group", {}, "name")
	stock_uom = frappe.db.get_value("UOM", {"name": "Nos"}, "name") \
		or frappe.db.get_value("UOM", {}, "name")
	frappe.get_doc({
		"doctype": "Item",
		"item_code": "Sub Contractor Cost",
		"item_name": "Sub Contractor Cost",
		"item_group": item_group,
		"stock_uom": stock_uom,
		"is_stock_item": 0,
	}).insert(ignore_permissions=True)


def _set_site_expense_account(site):
	company = frappe.db.get_single_value("Global Defaults", "default_company") \
		or frappe.db.get_value("Company", {}, "name")
	expense = frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Expense Account", "is_group": 0},
		"name",
	) or frappe.db.get_value(
		"Account", {"company": company, "is_group": 0, "root_type": "Expense"}, "name"
	)
	frappe.db.set_value("Site", site, "expense_account", expense)
	return expense


def _make_approved_request(site, project, supplier):
	"""Build, submit, and return the name of a request.

	On dev sites without a Workflow installed, `workflow_state` is None on the
	submitted doc; the server-side `make_purchase_invoice` gate
	`if req.workflow_state and req.workflow_state != "Approved"` correctly
	treats None as "not blocked", so the PI gets created. Tests don't need to
	stage a workflow.
	"""
	import json
	boq = _make_submitted_boq(site, project, sub_count=1, company_count=0)
	sub_row = frappe.get_doc("Bill of Quantities", boq).table_txao[0]
	req_name = make_request_from_boq(
		boq=boq, supplier=supplier, date=today(),
		selected=json.dumps([{
			"stage_label": "Stage 1",
			"boq_item_name": sub_row.name,
			"description": sub_row.description,
			"unit": sub_row.unit,
			"quantity": sub_row.planned_quantity,
			"rate": sub_row.rate,
		}]),
	)
	req = frappe.get_doc("Sub Contractor Payment Request", req_name)
	req.submit()
	return req.name


class TestMakePurchaseInvoice(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		_ensure_subcon_cost_item()
		self.supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")

	def test_creates_draft_pi_with_correct_fields(self):
		site, project = _make_site_and_project_for_flow()
		_set_site_expense_account(site)
		req_name = _make_approved_request(site, project, self.supplier)
		pi_name = make_purchase_invoice(req_name)
		pi = frappe.get_doc("Purchase Invoice", pi_name)
		self.assertEqual(pi.docstatus, 0)
		self.assertEqual(pi.supplier, self.supplier)
		self.assertEqual(pi.site, site)
		self.assertEqual(pi.sub_contractor_payment_request, req_name)
		self.assertEqual(len(pi.items), 1)
		row = pi.items[0]
		self.assertEqual(row.item_code, "Sub Contractor Cost")
		self.assertEqual(flt(row.qty), 1)
		self.assertEqual(flt(row.rate), 5000)  # 5 × 1000 from the source BOQ row
		self.assertEqual(row.project, project)

	def test_missing_expense_account_errors(self):
		site, project = _make_site_and_project_for_flow()
		# Deliberately do NOT set expense_account on the Site
		req_name = _make_approved_request(site, project, self.supplier)
		with self.assertRaises(frappe.ValidationError):
			make_purchase_invoice(req_name)

	def test_missing_subcon_cost_item_errors(self):
		# Delete the Item; FrappeTestCase's transactional rollback restores it
		# at the end of the test. If the delete itself fails on this dev site
		# (e.g., ledger entries reference the item from a prior unrelated
		# session), skipTest with the reason — this is environment, not logic.
		site, project = _make_site_and_project_for_flow()
		_set_site_expense_account(site)
		req_name = _make_approved_request(site, project, self.supplier)
		try:
			frappe.delete_doc("Item", "Sub Contractor Cost",
			                  ignore_permissions=True, force=True)
		except Exception as e:
			self.skipTest(f"Cannot delete Sub Contractor Cost item on this site: {e}")
		with self.assertRaises(frappe.ValidationError):
			make_purchase_invoice(req_name)

	def test_draft_request_errors(self):
		import json
		site, project = _make_site_and_project_for_flow()
		_set_site_expense_account(site)
		boq = _make_submitted_boq(site, project, sub_count=1, company_count=0)
		sub_row = frappe.get_doc("Bill of Quantities", boq).table_txao[0]
		req_name = make_request_from_boq(
			boq=boq, supplier=self.supplier, date=today(),
			selected=json.dumps([{
				"stage_label": "Stage 1",
				"boq_item_name": sub_row.name,
				"description": sub_row.description,
				"unit": sub_row.unit,
				"quantity": sub_row.planned_quantity,
				"rate": sub_row.rate,
			}]),
		)
		# Do NOT submit; leave as draft (docstatus = 0).
		with self.assertRaises(frappe.ValidationError):
			make_purchase_invoice(req_name)

	def test_pi_submit_increases_project_expenses(self):
		"""Regression: the Spec 1 hooks pick up the generated PI's contribution."""
		site, project = _make_site_and_project_for_flow()
		_set_site_expense_account(site)
		req_name = _make_approved_request(site, project, self.supplier)
		pi_name = make_purchase_invoice(req_name)
		pi = frappe.get_doc("Purchase Invoice", pi_name)
		# Fill anything else PI submit needs (cost_center / company already set
		# by set_missing_values).
		company = pi.company
		if not pi.due_date:
			pi.due_date = add_days(today(), 30)
		if not pi.bill_no:
			pi.bill_no = frappe.generate_hash(length=6)
			pi.bill_date = today()
		pi.items[0].cost_center = frappe.db.get_value(
			"Cost Center", {"company": company, "is_group": 0}, "name"
		)
		pi.save(ignore_permissions=True)
		pi.submit()
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_expenses")),
			5000,
		)
