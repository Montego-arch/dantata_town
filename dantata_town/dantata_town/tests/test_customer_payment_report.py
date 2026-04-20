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
