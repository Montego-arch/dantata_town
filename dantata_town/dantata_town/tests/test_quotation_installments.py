# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from dantata_town.dantata_town.setup import create_boq_custom_fields


class TestQuotationInstallments(FrappeTestCase):
	def test_custom_fields_installed(self):
		create_boq_custom_fields()

		expected = {
			"payment_type": {"fieldtype": "Select", "options": "\nInstallment\nOutright"},
			"installment_start_date": {"fieldtype": "Date"},
			"installment_deposit_amount": {"fieldtype": "Currency"},
			"installment_months": {"fieldtype": "Int"},
		}

		for fieldname, props in expected.items():
			field = frappe.db.get_value(
				"Custom Field",
				{"dt": "Quotation", "fieldname": fieldname},
				["fieldtype", "options", "depends_on"],
				as_dict=True,
			)
			self.assertIsNotNone(
				field,
				f"Custom Field {fieldname} not found on Quotation",
			)
			self.assertEqual(field.fieldtype, props["fieldtype"])
			if "options" in props:
				self.assertEqual(field.options, props["options"])
			if fieldname != "payment_type":
				self.assertEqual(field.depends_on, "eval:doc.payment_type === 'Installment'")
