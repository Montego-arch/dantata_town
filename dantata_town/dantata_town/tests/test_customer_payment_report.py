# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestCustomerPaymentReport(FrappeTestCase):
	def _settings(self, **overrides):
		"""Load the single, apply overrides, return the doc."""
		doc = frappe.get_single("Customer Payment Report Settings")
		for k, v in overrides.items():
			doc.set(k, v)
		return doc

	def test_day_below_1_rejected(self):
		doc = self._settings(send_day_of_month=0, enabled=0)
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_day_above_28_rejected(self):
		doc = self._settings(send_day_of_month=29, enabled=0)
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_day_28_accepted(self):
		doc = self._settings(send_day_of_month=28, enabled=0, recipient_emails="")
		doc.save(ignore_permissions=True)  # no raise

	def test_enabled_without_recipients_rejected(self):
		doc = self._settings(enabled=1, send_day_of_month=1, recipient_emails="")
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_malformed_email_rejected(self):
		doc = self._settings(enabled=1, send_day_of_month=1, recipient_emails="not-an-email")
		with self.assertRaises(Exception):  # validate_email_address raises InvalidEmailAddressError
			doc.save(ignore_permissions=True)

	def test_multiple_valid_emails_accepted(self):
		doc = self._settings(
			enabled=1,
			send_day_of_month=1,
			recipient_emails="a@example.com\nb@example.com",
		)
		doc.save(ignore_permissions=True)
		# Reload to confirm persistence.
		doc = frappe.get_single("Customer Payment Report Settings")
		self.assertIn("a@example.com", doc.recipient_emails)
		self.assertIn("b@example.com", doc.recipient_emails)

	def test_aggregation_only_submitted_outstanding_invoices(self):
		from dantata_town.dantata_town.reports import build_customer_payment_report_rows
		rows = build_customer_payment_report_rows()
		invoice_names = {r["name"] for r in rows}

		# Every returned invoice must be submitted and have outstanding > 0.
		for inv in invoice_names:
			doc = frappe.db.get_value(
				"Sales Invoice", inv,
				["docstatus", "outstanding_amount"], as_dict=True,
			)
			self.assertEqual(doc.docstatus, 1)
			self.assertGreater(float(doc.outstanding_amount), 0)

		# No invoice with outstanding == 0 should appear.
		paid = frappe.get_all(
			"Sales Invoice",
			filters={"docstatus": 1, "outstanding_amount": 0},
			pluck="name",
		)
		self.assertTrue(invoice_names.isdisjoint(paid))

	def test_aggregation_property_fields_fallback_to_dash(self):
		"""For any returned row whose SO has no submitted AL, property fields = '—'."""
		from dantata_town.dantata_town.reports import build_customer_payment_report_rows
		rows = build_customer_payment_report_rows()
		for r in rows:
			so = frappe.db.get_value(
				"Sales Invoice Item",
				{"parent": r["name"], "sales_order": ("!=", "")},
				"sales_order",
			)
			has_al = so and frappe.db.exists(
				"Allocation Letter", {"sales_order": so, "docstatus": 1}
			)
			if not has_al:
				self.assertEqual(r["property_type"], "—")
				self.assertEqual(r["property_description"], "—")
				self.assertEqual(r["plot_number"], "—")

	def test_aggregation_property_fields_match_linked_al(self):
		"""For any returned row whose SO has a submitted AL, property fields match
		the AL's values (positive path)."""
		from dantata_town.dantata_town.reports import build_customer_payment_report_rows
		rows = build_customer_payment_report_rows()
		tested_any = False
		for r in rows:
			so = frappe.db.get_value(
				"Sales Invoice Item",
				{"parent": r["name"], "sales_order": ("!=", "")},
				"sales_order",
			)
			if not so:
				continue
			al_name = frappe.db.get_value(
				"Allocation Letter",
				{"sales_order": so, "docstatus": 1},
				"name",
				order_by="letter_date desc",
			)
			if not al_name:
				continue
			al = frappe.db.get_value(
				"Allocation Letter", al_name,
				["property_type", "property_description", "plot_number"],
				as_dict=True,
			)
			self.assertEqual(r["property_type"], al.property_type or "—")
			self.assertEqual(r["property_description"], al.property_description or "—")
			self.assertEqual(r["plot_number"], al.plot_number or "—")
			tested_any = True
		if not tested_any:
			self.skipTest("No outstanding SI → SO → submitted AL path present on this site")
