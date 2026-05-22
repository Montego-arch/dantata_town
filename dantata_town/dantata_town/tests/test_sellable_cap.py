# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today

from dantata_town.dantata_town.setup import create_boq_custom_fields
from dantata_town.dantata_town.tests._helpers import (
	get_test_expense_account,
	ensure_site_preconditions,
)


def _make_site_with_cap(template, unit, reserved):
	"""Make a Site with one project_unit row and return (site_name, per_site_item_code)."""
	site = frappe.get_doc({
		"doctype": "Site",
		"site_name": f"CapSite-{frappe.generate_hash(length=6)}",
		"expense_account": get_test_expense_account(),
		"project_units": [{
			"template_item": template,
			"unit": unit,
			"reserved_unit": reserved,
			"uom": "Unit",
			"rate": 1000,
		}],
	}).insert(ignore_permissions=True)
	return site.name, site.project_units[0].building_type


def _make_quotation(item_code, qty, save=True, submit=False):
	customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
	q = frappe.get_doc({
		"doctype": "Quotation",
		"quotation_to": "Customer",
		"party_name": customer,
		"transaction_date": today(),
		"valid_till": today(),
		"payment_type": "Outright",
		"items": [{
			"item_code": item_code,
			"qty": qty,
			"rate": 1000,
		}],
	})
	if save:
		q.insert(ignore_permissions=True)
	if submit:
		q.submit()
	return q


class TestSellableCap(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		ensure_site_preconditions()

	def test_quotation_within_cap_saves(self):
		_, item = _make_site_with_cap("Cap-A", unit=10, reserved=2)  # sellable=8
		q = _make_quotation(item, qty=5)
		self.assertTrue(frappe.db.exists("Quotation", q.name))

	def test_quotation_exceeding_cap_throws(self):
		_, item = _make_site_with_cap("Cap-B", unit=10, reserved=2)  # sellable=8
		_make_quotation(item, qty=5)
		with self.assertRaises(frappe.ValidationError) as cm:
			_make_quotation(item, qty=4)  # 5 + 4 = 9 > 8
		self.assertIn("sellable", str(cm.exception).lower())

	def test_cancelling_quotation_frees_cap(self):
		_, item = _make_site_with_cap("Cap-C", unit=10, reserved=2)  # sellable=8
		q1 = _make_quotation(item, qty=5, submit=True)
		# Now cancel q1; cap should free up.
		q1.cancel()
		q2 = _make_quotation(item, qty=8)
		self.assertTrue(frappe.db.exists("Quotation", q2.name))

	def test_submitted_quotation_counts(self):
		_, item = _make_site_with_cap("Cap-D", unit=10, reserved=2)  # sellable=8
		_make_quotation(item, qty=5, submit=True)
		with self.assertRaises(frappe.ValidationError):
			_make_quotation(item, qty=4)

	def test_non_site_item_skipped(self):
		# Item exists but is not referenced on any Site row → cap does not apply.
		other = frappe.db.sql(
			"""
			select name from `tabItem`
			where is_sales_item = 1 and disabled = 0
			  and name not in (
				  select building_type from `tabProject Unit Item`
				  where parenttype = 'Site' and building_type is not null
			  )
			limit 1
			""",
			as_dict=True,
		)
		if not other:
			self.skipTest("No non-site sales-enabled Item available")
		q = _make_quotation(other[0].name, qty=99999)
		self.assertTrue(frappe.db.exists("Quotation", q.name))
