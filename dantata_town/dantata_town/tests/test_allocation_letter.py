# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


def _ensure_terms(chairman="Alhassan A. Dantata", company="Dantata Town Developers Ltd", conditions="<p>1. Conditions go here.</p>"):
	terms = frappe.get_single("Allocation Letter Terms")
	terms.default_chairman_name = chairman
	terms.default_company_name = company
	terms.conditions_text = conditions
	terms.withdrawal_clause_text = ""
	terms.save(ignore_permissions=True)


def _pick_submitted_sales_order():
	so = frappe.get_all(
		"Sales Order",
		filters={"docstatus": 1},
		fields=["name", "customer", "customer_name", "grand_total"],
		limit=1,
	)
	return so[0] if so else None


class TestAllocationLetter(FrappeTestCase):
	def test_make_allocation_letter_prefills_from_sales_order(self):
		_ensure_terms()
		so = _pick_submitted_sales_order()
		if not so:
			self.skipTest("No submitted Sales Order on this site")

		from dantata_town.dantata_town.doctype.allocation_letter.allocation_letter import (
			make_allocation_letter,
		)
		target = make_allocation_letter(so.name)

		self.assertEqual(target.doctype, "Allocation Letter")
		self.assertEqual(target.sales_order, so.name)
		self.assertEqual(target.customer, so.customer)
		self.assertEqual(target.customer_name, so.customer_name)
		self.assertEqual(target.cost_of_property, so.grand_total)
		self.assertEqual(target.addressee_name, so.customer_name)
		self.assertEqual(target.chairman_name, "Alhassan A. Dantata")
		self.assertEqual(target.company_name, "Dantata Town Developers Ltd")
		self.assertEqual(target.letter_date, frappe.utils.today())

	def _new_draft_letter(self, so, **overrides):
		"""Helper to build a new AL in memory with sensible defaults."""
		_ensure_terms()
		doc = frappe.get_doc({
			"doctype": "Allocation Letter",
			"letter_date": frappe.utils.today(),
			"sales_order": so.name,
			"customer": so.customer,
			"addressee_name": so.customer_name,
			"property_type": "Residential",
			"property_description": "4-bedrooms Semi-Detached Duplex - DPC",
			"location_scheme": "Dantata City Estate, F01 Kubwa, Abuja",
			"plot_number": "DCB-001",
			"purchase_price_option": "Installment",
			"cost_of_property": 1000,
			"payment_duration": "4 months",
			"installment_schedule": [
				{"sequence_label": "First", "amount": 250, "due_date": frappe.utils.today()},
				{"sequence_label": "Second", "amount": 250, "due_date": frappe.utils.today()},
				{"sequence_label": "Third", "amount": 250, "due_date": frappe.utils.today()},
				{"sequence_label": "Fourth", "amount": 250, "due_date": frappe.utils.today()},
			],
		})
		doc.update(overrides)
		return doc

	def test_outright_clears_schedule_and_duration(self):
		so = _pick_submitted_sales_order()
		if not so:
			self.skipTest("No submitted Sales Order on this site")
		doc = self._new_draft_letter(so, purchase_price_option="Outright")
		doc.insert(ignore_permissions=True)
		doc.reload()
		self.assertEqual(len(doc.installment_schedule or []), 0)
		self.assertIn(doc.payment_duration, (None, ""))

	def test_installment_schedule_sum_mismatch_rejected(self):
		so = _pick_submitted_sales_order()
		if not so:
			self.skipTest("No submitted Sales Order on this site")
		doc = self._new_draft_letter(so)
		doc.installment_schedule[0].amount = 100  # total now 850, not 1000
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_installment_without_payment_duration_rejected(self):
		so = _pick_submitted_sales_order()
		if not so:
			self.skipTest("No submitted Sales Order on this site")
		doc = self._new_draft_letter(so, payment_duration="")
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_installment_without_schedule_rows_rejected(self):
		so = _pick_submitted_sales_order()
		if not so:
			self.skipTest("No submitted Sales Order on this site")
		doc = self._new_draft_letter(so, installment_schedule=[])
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)
