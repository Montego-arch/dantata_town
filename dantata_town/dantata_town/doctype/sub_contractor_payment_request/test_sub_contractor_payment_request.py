# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today

from dantata_town.dantata_town.setup import create_boq_custom_fields


def _make_site_and_project_minimal():
	"""Build a minimal Site + Project pair for tests in this module."""
	create_boq_custom_fields()
	from dantata_town.dantata_town.tests._helpers import get_test_expense_account
	uom = frappe.db.get_value("UOM", {}, "name")
	item = frappe.db.get_value("Item", {"disabled": 0}, "name")
	customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
	company = frappe.db.get_single_value("Global Defaults", "default_company") \
		or frappe.db.get_value("Company", {}, "name")
	site = frappe.get_doc({
		"doctype": "Site",
		"site_name": f"SCPR-Site-{frappe.generate_hash(length=6)}",
		"expense_account": get_test_expense_account(),
		"project_units": [{"building_type": item, "unit": 1, "uom": uom, "rate": 1}],
	}).insert(ignore_permissions=True)
	project = frappe.get_doc({
		"doctype": "Project",
		"project_name": f"SCPR-Proj-{frappe.generate_hash(length=6)}",
		"customer": customer,
		"company": company,
		"site": site.name,
		"project_type": "Building",
		"project_subtype": "PLOT",
	}).insert(ignore_permissions=True)
	return site.name, project.name


def _detail_name():
	existing = frappe.db.get_value("BOQ Item Detail", {}, "name")
	if existing:
		return existing
	return frappe.get_doc({
		"doctype": "BOQ Item Detail",
		"description": f"Detail-{frappe.generate_hash(length=6)}",
		"description_type": "Material",
		"unit": "Nos",
	}).insert(ignore_permissions=True).name


def _make_boq(site, project):
	"""Insert and submit a BOQ with a single Sub Contractor row in stage 1."""
	doc = frappe.new_doc("Bill of Quantities")
	doc.site = site
	doc.project = project
	doc.date = today()
	doc.append("table_txao", {
		"description": _detail_name(),
		"planned_quantity": 5,
		"rate": 1000,
		"assignment_type": "Sub Contractor",
	})
	doc.stage_1_start_date = today()
	doc.stage_1_end_date = frappe.utils.add_days(today(), 10)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


class TestSubContractorPaymentRequestDoctype(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()

	def _new_request(self, supplier=None, items=None):
		site, project = _make_site_and_project_minimal()
		boq = _make_boq(site, project)
		supplier = supplier or frappe.db.get_value("Supplier", {"disabled": 0}, "name")
		req = frappe.new_doc("Sub Contractor Payment Request")
		req.date = today()
		req.site = site
		req.project = project
		req.boq = boq
		req.supplier = supplier
		for r in (items or [{"description": _detail_name(), "quantity": 2, "rate": 500,
		                     "original_quantity": 2, "original_rate": 500,
		                     "stage_label": "Stage 1"}]):
			req.append("items", r)
		return req

	def test_validate_recomputes_row_amount(self):
		req = self._new_request(items=[{
			"description": _detail_name(),
			"quantity": 3, "rate": 250,
			"original_quantity": 3, "original_rate": 250,
			"stage_label": "Stage 1",
		}])
		req.insert(ignore_permissions=True)
		self.assertEqual(flt(req.items[0].amount), 750)

	def test_validate_recomputes_total_amount(self):
		req = self._new_request(items=[
			{"description": _detail_name(), "quantity": 2, "rate": 500,
			 "original_quantity": 2, "original_rate": 500, "stage_label": "Stage 1"},
			{"description": _detail_name(), "quantity": 1, "rate": 100,
			 "original_quantity": 1, "original_rate": 100, "stage_label": "Stage 1"},
		])
		req.insert(ignore_permissions=True)
		self.assertEqual(flt(req.total_amount), 1100)

	def test_submit_lifecycle(self):
		req = self._new_request()
		req.insert(ignore_permissions=True)
		self.assertEqual(req.docstatus, 0)
		req.submit()
		self.assertEqual(req.docstatus, 1)
		req.cancel()
		self.assertEqual(req.docstatus, 2)

	def test_doctype_field_metadata(self):
		meta = frappe.get_meta("Sub Contractor Payment Request")
		self.assertTrue(meta.is_submittable)
		for fieldname in ["naming_series", "date", "site", "project", "boq",
		                  "supplier", "items", "total_amount", "amended_from"]:
			self.assertIsNotNone(meta.get_field(fieldname), f"{fieldname} missing on parent")
		child_meta = frappe.get_meta("Sub Contractor Payment Request Item")
		for fieldname in ["stage_label", "description", "unit", "quantity", "rate",
		                  "amount", "original_quantity", "original_rate", "boq_item"]:
			self.assertIsNotNone(child_meta.get_field(fieldname), f"{fieldname} missing on child")
