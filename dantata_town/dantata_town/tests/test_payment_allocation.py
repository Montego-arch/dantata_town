# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days, flt

from dantata_town.dantata_town.setup import create_boq_custom_fields


class TestPaymentScheduleVisibility(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()

	def test_paid_amount_in_list_view(self):
		value = frappe.db.get_value(
			"Property Setter",
			{
				"doc_type": "Payment Schedule",
				"field_name": "paid_amount",
				"property": "in_list_view",
			},
			"value",
		)
		self.assertEqual(value, "1")

	def test_outstanding_in_list_view(self):
		value = frappe.db.get_value(
			"Property Setter",
			{
				"doc_type": "Payment Schedule",
				"field_name": "outstanding",
				"property": "in_list_view",
			},
			"value",
		)
		self.assertEqual(value, "1")


class TestSOFifoAllocation(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		self.customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
		if not self.customer:
			self.skipTest("No customer")
		self.item = frappe.db.get_value("Item", {"is_stock_item": 0, "disabled": 0}, "name")
		if not self.item:
			self.skipTest("No non-stock item")
		self.company = frappe.db.get_single_value("Global Defaults", "default_company")
		if not self.company:
			self.skipTest("No default company")
		self.receivable = frappe.db.get_value(
			"Account",
			{"company": self.company, "account_type": "Receivable", "is_group": 0},
			"name",
		)
		self.bank = frappe.db.get_value(
			"Account",
			{"company": self.company, "account_type": "Bank", "is_group": 0},
			"name",
		) or frappe.db.get_value(
			"Account",
			{"company": self.company, "account_type": "Cash", "is_group": 0},
			"name",
		)
		self.cost_center = frappe.db.get_value(
			"Cost Center", {"company": self.company, "is_group": 0}, "name"
		)

	def _make_so_with_schedule(self, amounts):
		"""Create + submit an SO with `amounts` payment_schedule tranches (sequential due dates)."""
		so = frappe.new_doc("Sales Order")
		so.customer = self.customer
		so.company = self.company
		so.cost_center = self.cost_center
		so.transaction_date = today()
		so.delivery_date = add_days(today(), 30)
		so.append("items", {
			"item_code": self.item,
			"qty": 1,
			"rate": sum(amounts),
			"delivery_date": add_days(today(), 30),
			"cost_center": self.cost_center,
		})
		for i, amt in enumerate(amounts):
			so.append("payment_schedule", {
				"due_date": add_days(today(), 10 * (i + 1)),
				"invoice_portion": 100.0 / len(amounts),
				"payment_amount": amt,
			})
		so.insert(ignore_permissions=True)
		so.submit()
		return so

	def _make_payment_entry(self, so, amount):
		pe = frappe.get_doc({
			"doctype": "Payment Entry",
			"payment_type": "Receive",
			"party_type": "Customer",
			"party": self.customer,
			"company": self.company,
			"posting_date": today(),
			"paid_amount": amount,
			"received_amount": amount,
			"paid_from": self.receivable,
			"paid_to": self.bank,
			"references": [{
				"reference_doctype": "Sales Order",
				"reference_name": so.name,
				"allocated_amount": amount,
				"total_amount": so.grand_total,
				"outstanding_amount": so.grand_total - amount,
			}],
		})
		pe.set_missing_values()
		pe.insert(ignore_permissions=True)
		pe.submit()
		return pe

	def test_fifo_within_one_tranche(self):
		so = self._make_so_with_schedule([10000, 10000, 10000])
		self._make_payment_entry(so, 6000)
		so.reload()
		self.assertEqual(flt(so.payment_schedule[0].paid_amount), 6000)
		self.assertEqual(flt(so.payment_schedule[0].outstanding), 4000)
		self.assertEqual(flt(so.payment_schedule[1].paid_amount), 0)
		self.assertEqual(flt(so.payment_schedule[1].outstanding), 10000)

	def test_fifo_spans_two_tranches(self):
		so = self._make_so_with_schedule([10000, 10000, 10000])
		self._make_payment_entry(so, 15000)
		so.reload()
		self.assertEqual(flt(so.payment_schedule[0].paid_amount), 10000)
		self.assertEqual(flt(so.payment_schedule[0].outstanding), 0)
		self.assertEqual(flt(so.payment_schedule[1].paid_amount), 5000)
		self.assertEqual(flt(so.payment_schedule[1].outstanding), 5000)

	def test_pe_cancel_resets_paid_amounts(self):
		so = self._make_so_with_schedule([10000, 10000])
		pe = self._make_payment_entry(so, 10000)
		pe.cancel()
		so.reload()
		self.assertEqual(flt(so.payment_schedule[0].paid_amount), 0)
		self.assertEqual(flt(so.payment_schedule[0].outstanding), 10000)
