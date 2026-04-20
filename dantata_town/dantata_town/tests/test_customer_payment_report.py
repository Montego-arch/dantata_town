# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

# Ensure a default outgoing Email Account exists so queueing the report email
# succeeds in the test site (which otherwise has no email account configured).
test_dependencies = ["Email Account"]


class TestCustomerPaymentReport(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Promote the test email account to default_outgoing so frappe.sendmail
		# can resolve a sender when queueing the report.
		if frappe.db.exists("Email Account", "_Test Email Account 1"):
			frappe.db.set_value(
				"Email Account", "_Test Email Account 1",
				{"default_outgoing": 1, "enable_outgoing": 1},
			)
		# Also bust Frappe's per-process email-account cache so the promotion
		# is visible to subsequent find_outgoing() calls.
		for attr in ("outgoing_email_account", "incoming_email_account"):
			if hasattr(frappe.local, attr):
				delattr(frappe.local, attr)

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

	def _reset_settings(self, enabled=1, day=1, emails="a@example.com", last_sent_date=None, last_sent_status=None):
		"""Reset the single to a known baseline."""
		doc = frappe.get_single("Customer Payment Report Settings")
		doc.enabled = enabled
		doc.send_day_of_month = day
		doc.recipient_emails = emails
		doc.last_sent_date = last_sent_date
		doc.last_sent_status = last_sent_status
		doc.save(ignore_permissions=True)

	def _count_queued_emails(self, subject_substring):
		return frappe.db.count(
			"Email Queue",
			{"message": ("like", f"%{subject_substring}%")},
		)

	def test_scheduled_disabled_skips(self):
		from dantata_town.dantata_town.reports import send_monthly_customer_payment_report
		self._reset_settings(enabled=0)
		before = self._count_queued_emails("Monthly Customer Payment Report")
		send_monthly_customer_payment_report()
		after = self._count_queued_emails("Monthly Customer Payment Report")
		self.assertEqual(after, before)
		doc = frappe.get_single("Customer Payment Report Settings")
		self.assertEqual(doc.last_sent_status, "Skipped (disabled)")

	def test_scheduled_wrong_day_skips(self):
		from dantata_town.dantata_town.reports import send_monthly_customer_payment_report
		today = frappe.utils.getdate()
		other_day = 28 if today.day != 28 else 27
		self._reset_settings(enabled=1, day=other_day)
		before = self._count_queued_emails("Monthly Customer Payment Report")
		send_monthly_customer_payment_report()
		after = self._count_queued_emails("Monthly Customer Payment Report")
		self.assertEqual(after, before)
		doc = frappe.get_single("Customer Payment Report Settings")
		self.assertEqual(doc.last_sent_status, "Skipped (wrong day)")

	def test_scheduled_right_day_sends(self):
		from dantata_town.dantata_town.reports import send_monthly_customer_payment_report
		today = frappe.utils.getdate()
		self._reset_settings(enabled=1, day=today.day, last_sent_date=None)
		before = self._count_queued_emails("Monthly Customer Payment Report")
		send_monthly_customer_payment_report()
		after = self._count_queued_emails("Monthly Customer Payment Report")
		self.assertEqual(after, before + 1)
		doc = frappe.get_single("Customer Payment Report Settings")
		self.assertEqual(doc.last_sent_status, "Success")
		self.assertEqual(frappe.utils.getdate(doc.last_sent_date), today)

	def test_scheduled_double_send_guard(self):
		from dantata_town.dantata_town.reports import send_monthly_customer_payment_report
		today = frappe.utils.getdate()
		self._reset_settings(enabled=1, day=today.day, last_sent_date=today)
		before = self._count_queued_emails("Monthly Customer Payment Report")
		send_monthly_customer_payment_report()
		after = self._count_queued_emails("Monthly Customer Payment Report")
		self.assertEqual(after, before)  # no new email
		doc = frappe.get_single("Customer Payment Report Settings")
		self.assertEqual(doc.last_sent_status, "Success")

	def test_scheduled_empty_rows_still_sends(self):
		"""When there are no outstanding invoices, the email still goes out with
		the empty-state body so silence doesn't mask a silent failure."""
		from dantata_town.dantata_town import reports
		from dantata_town.dantata_town.reports import send_monthly_customer_payment_report
		today = frappe.utils.getdate()
		self._reset_settings(enabled=1, day=today.day, last_sent_date=None)

		original = reports.build_customer_payment_report_rows
		reports.build_customer_payment_report_rows = lambda: []
		try:
			before = self._count_queued_emails("Monthly Customer Payment Report")
			send_monthly_customer_payment_report()
			after = self._count_queued_emails("Monthly Customer Payment Report")
			self.assertEqual(after, before + 1)
		finally:
			reports.build_customer_payment_report_rows = original

		recent = frappe.get_all(
			"Email Queue",
			filters={"message": ("like", "%No outstanding balances this month%")},
			pluck="name",
		)
		self.assertGreaterEqual(len(recent), 1)
		doc = frappe.get_single("Customer Payment Report Settings")
		self.assertEqual(doc.last_sent_status, "Success")

	def test_send_report_now_disabled_rejected(self):
		from dantata_town.dantata_town.reports import send_report_now
		self._reset_settings(enabled=0)
		with self.assertRaises(frappe.ValidationError):
			send_report_now()

	def test_send_report_now_sends_regardless_of_day(self):
		"""Send Now bypasses day/last-sent checks."""
		from dantata_town.dantata_town.reports import send_report_now
		today = frappe.utils.getdate()
		other_day = 28 if today.day != 28 else 27
		self._reset_settings(enabled=1, day=other_day, last_sent_date=today)
		before = self._count_queued_emails("Monthly Customer Payment Report")
		send_report_now()
		after = self._count_queued_emails("Monthly Customer Payment Report")
		self.assertEqual(after, before + 1)
		doc = frappe.get_single("Customer Payment Report Settings")
		self.assertEqual(doc.last_sent_status, "Success")

	def test_send_report_now_requires_privileged_role(self):
		"""Accounts User lacks permission; System Manager / Accounts Manager do."""
		from dantata_town.dantata_town.reports import send_report_now
		self._reset_settings(enabled=1, day=1)

		# Find or create an Accounts User with none of the privileged roles.
		test_user_email = "cpr_accounts_user@example.com"
		if not frappe.db.exists("User", test_user_email):
			user = frappe.get_doc({
				"doctype": "User",
				"email": test_user_email,
				"first_name": "CPR",
				"last_name": "Accounts User",
				"enabled": 1,
				"roles": [{"role": "Accounts User"}],
				"send_welcome_email": 0,
			})
			user.insert(ignore_permissions=True)

		original_user = frappe.session.user
		# frappe.only_for() is a no-op when flags.in_test is True, so disable it
		# for the duration of this check to exercise the real permission branch.
		original_in_test = frappe.flags.in_test
		frappe.flags.in_test = False
		frappe.set_user(test_user_email)
		try:
			with self.assertRaises(frappe.PermissionError):
				send_report_now()
		finally:
			frappe.set_user(original_user)
			frappe.flags.in_test = original_in_test

	def test_script_report_execute_shape(self):
		from dantata_town.dantata_town.report.customer_payment_report.customer_payment_report import execute
		columns, data = execute(filters=None)
		self.assertEqual(len(columns), 9)
		expected_fieldnames = [
			"customer", "customer_name", "name", "posting_date", "due_date",
			"outstanding_amount", "property_type", "property_description", "plot_number",
		]
		self.assertEqual([c["fieldname"] for c in columns], expected_fieldnames)
		# Data shape matches the aggregation helper's output.
		from dantata_town.dantata_town.reports import build_customer_payment_report_rows
		self.assertEqual(data, build_customer_payment_report_rows())
