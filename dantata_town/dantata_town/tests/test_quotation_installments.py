# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from dantata_town.dantata_town.setup import create_boq_custom_fields


class TestQuotationInstallments(FrappeTestCase):
	def test_custom_fields_installed(self):
		create_boq_custom_fields()

		eval_expr = "eval:doc.payment_type === 'Installment'"
		expected = {
			"site": {"fieldtype": "Link", "options": "Site"},
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

	def test_installment_submit_requires_deposit(self):
		create_boq_custom_fields()
		doc = self._new_quotation(installment_deposit_amount=0)
		doc.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_installment_submit_requires_start_date(self):
		create_boq_custom_fields()
		doc = self._new_quotation(installment_start_date=None)
		doc.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_installment_submit_requires_months(self):
		create_boq_custom_fields()
		doc = self._new_quotation(installment_months=0)
		doc.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_installment_submit_rejects_deposit_ge_total(self):
		create_boq_custom_fields()
		doc = self._new_quotation(installment_deposit_amount=60000)  # total is 50000
		doc.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_generate_produces_n_plus_1_rows(self):
		create_boq_custom_fields()
		doc = self._new_quotation()
		doc.insert(ignore_permissions=True)

		from dantata_town.dantata_town.quotation import generate_installment_schedule
		generate_installment_schedule(doc.name)
		doc.reload()

		self.assertEqual(len(doc.payment_schedule), 5)  # 1 deposit + 4 monthly
		self.assertEqual(flt(doc.payment_schedule[0].payment_amount), 10000)
		for i in range(1, 5):
			self.assertGreater(flt(doc.payment_schedule[i].payment_amount), 0)

	def test_generate_sum_equals_grand_total(self):
		create_boq_custom_fields()
		doc = self._new_quotation()
		doc.insert(ignore_permissions=True)

		from dantata_town.dantata_town.quotation import generate_installment_schedule
		generate_installment_schedule(doc.name)
		doc.reload()

		total = sum(flt(row.payment_amount) for row in doc.payment_schedule)
		self.assertEqual(total, flt(doc.grand_total))

	def test_generate_last_row_absorbs_rounding_drift(self):
		"""deposit=10000, total=40001, months=3 → balance=30001, per_month=10000.33,
		last row = 10000.34 (absorbs the 0.01 drift)."""
		create_boq_custom_fields()
		# Use rate=40001 to force non-even division.
		doc = self._new_quotation(
			items=[{
				"item_code": frappe.db.get_value(
					"Item", {"disabled": 0, "is_sales_item": 1}, "name"
				),
				"qty": 1,
				"rate": 40001,
			}],
			installment_deposit_amount=10000,
			installment_months=3,
		)
		doc.insert(ignore_permissions=True)

		from dantata_town.dantata_town.quotation import generate_installment_schedule
		generate_installment_schedule(doc.name)
		doc.reload()

		# Rows 1 and 2 should be equal; row 3 (last) should differ by the rounding drift.
		self.assertEqual(flt(doc.payment_schedule[1].payment_amount), 10000.33)
		self.assertEqual(flt(doc.payment_schedule[2].payment_amount), 10000.33)
		self.assertEqual(flt(doc.payment_schedule[3].payment_amount), 10000.34)
		# Sum still equals grand_total.
		total = sum(flt(row.payment_amount) for row in doc.payment_schedule)
		self.assertEqual(total, flt(doc.grand_total))

	def test_generate_due_dates_step_monthly_with_add_months(self):
		"""start=2026-01-31, months=2. First monthly row due end of Feb, second end of Mar."""
		create_boq_custom_fields()
		doc = self._new_quotation(
			installment_start_date="2026-01-31",
			installment_months=2,
		)
		doc.insert(ignore_permissions=True)

		from dantata_town.dantata_town.quotation import generate_installment_schedule
		generate_installment_schedule(doc.name)
		doc.reload()

		# Deposit row: exact start date.
		self.assertEqual(str(doc.payment_schedule[0].due_date), "2026-01-31")
		# First monthly: Feb's last day (28 in 2026, non-leap).
		self.assertEqual(str(doc.payment_schedule[1].due_date), "2026-02-28")
		# Second monthly: March's 31st.
		self.assertEqual(str(doc.payment_schedule[2].due_date), "2026-03-31")

	def test_generate_rejects_deposit_ge_total(self):
		create_boq_custom_fields()
		doc = self._new_quotation(installment_deposit_amount=60000)  # total=50000
		doc.insert(ignore_permissions=True)

		from dantata_town.dantata_town.quotation import generate_installment_schedule
		with self.assertRaises(frappe.ValidationError):
			generate_installment_schedule(doc.name)

	def test_generate_rejects_months_below_1(self):
		create_boq_custom_fields()
		doc = self._new_quotation(installment_months=0)
		doc.insert(ignore_permissions=True)

		from dantata_town.dantata_town.quotation import generate_installment_schedule
		with self.assertRaises(frappe.ValidationError):
			generate_installment_schedule(doc.name)

	def test_generate_is_idempotent(self):
		"""Running twice produces the same row count and amounts — no accumulation."""
		create_boq_custom_fields()
		doc = self._new_quotation()
		doc.insert(ignore_permissions=True)

		from dantata_town.dantata_town.quotation import generate_installment_schedule
		generate_installment_schedule(doc.name)
		doc.reload()
		first_rows = [(r.payment_amount, r.due_date) for r in doc.payment_schedule]

		generate_installment_schedule(doc.name)
		doc.reload()
		second_rows = [(r.payment_amount, r.due_date) for r in doc.payment_schedule]

		self.assertEqual(first_rows, second_rows)
		self.assertEqual(len(doc.payment_schedule), 5)
