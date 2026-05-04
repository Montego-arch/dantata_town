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
