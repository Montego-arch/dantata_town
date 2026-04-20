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
