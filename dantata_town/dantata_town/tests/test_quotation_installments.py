# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from dantata_town.dantata_town.setup import create_boq_custom_fields


class TestQuotationInstallments(FrappeTestCase):
	def test_custom_fields_installed(self):
		create_boq_custom_fields()

		eval_expr = "eval:doc.payment_type === 'Installment'"
		expected = {
			"dt_installment_section": {"fieldtype": "Section Break"},
			"payment_type": {"fieldtype": "Select", "options": "\nInstallment\nOutright"},
			"installment_column_break": {"fieldtype": "Column Break"},
			"installment_start_date": {
				"fieldtype": "Date",
				"depends_on": eval_expr,
				"mandatory_depends_on": eval_expr,
			},
			"installment_deposit_amount": {
				"fieldtype": "Currency",
				"depends_on": eval_expr,
				"mandatory_depends_on": eval_expr,
			},
			"installment_months": {
				"fieldtype": "Int",
				"depends_on": eval_expr,
				"mandatory_depends_on": eval_expr,
			},
		}

		for fieldname, props in expected.items():
			field = frappe.db.get_value(
				"Custom Field",
				{"dt": "Quotation", "fieldname": fieldname},
				["fieldtype", "options", "depends_on", "mandatory_depends_on"],
				as_dict=True,
			)
			self.assertIsNotNone(
				field,
				f"Custom Field {fieldname} not found on Quotation",
			)
			self.assertEqual(field.fieldtype, props["fieldtype"])
			if "options" in props:
				self.assertEqual(field.options, props["options"])
			if "depends_on" in props:
				self.assertEqual(field.depends_on, props["depends_on"])
			if "mandatory_depends_on" in props:
				self.assertEqual(field.mandatory_depends_on, props["mandatory_depends_on"])

	def _new_quotation(self, **overrides):
		"""Helper: build a draft Quotation in memory with sensible defaults."""
		defaults = {
			"doctype": "Quotation",
			"quotation_to": "Customer",
			"party_name": frappe.db.get_value("Customer", {"disabled": 0}, "name"),
			"currency": "NGN",
			"conversion_rate": 1,
			"selling_price_list": frappe.db.get_value(
				"Price List", {"selling": 1, "currency": "NGN"}, "name"
			),
			"items": [{
				"item_code": frappe.db.get_value(
					"Item", {"disabled": 0, "is_sales_item": 1}, "name"
				),
				"qty": 1,
				"rate": 50000,
			}],
			"payment_type": "Installment",
			"installment_deposit_amount": 10000,
			"installment_start_date": frappe.utils.today(),
			"installment_months": 4,
		}
		defaults.update(overrides)
		return frappe.get_doc(defaults)

	def test_outright_clears_installment_fields(self):
		create_boq_custom_fields()
		doc = self._new_quotation(payment_type="Outright")
		doc.insert(ignore_permissions=True)
		doc.reload()
		self.assertIn(doc.installment_deposit_amount, (0, None))
		self.assertIn(doc.installment_start_date, (None, ""))
		self.assertIn(doc.installment_months, (0, None))

	def test_installment_draft_save_permissive(self):
		"""Draft saves are permissive — user is still filling in fields."""
		create_boq_custom_fields()
		doc = self._new_quotation(installment_deposit_amount=0)
		doc.insert(ignore_permissions=True)  # Should not raise
		self.assertTrue(doc.name)
