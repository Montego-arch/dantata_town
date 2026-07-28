# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from dantata_town.dantata_town.tests._helpers import ensure_test_employee


class TestVisitorLog(FrappeTestCase):
	def setUp(self):
		self.employee = ensure_test_employee()

	def _log(self, submit=True, **overrides):
		doc = frappe.get_doc({
			"doctype": "Visitor Log",
			"visitor_name": "Amina Yusuf",
			"phone_number": "08030000000",
			"address": "12 Kubwa Road, Abuja",
			"person_to_see": self.employee,
			"purpose_of_visit": "Plot enquiry",
			**overrides,
		})
		doc.insert(ignore_permissions=True)
		if submit:
			doc.submit()
		return doc

	def test_insert_stamps_time_in_and_leaves_visitor_on_site(self):
		doc = self._log(submit=False)

		self.assertTrue(doc.time_in)
		self.assertFalse(doc.time_out)

	def test_check_out_records_time_out_on_a_submitted_visit(self):
		doc = self._log()

		doc.check_out()

		self.assertTrue(frappe.db.get_value("Visitor Log", doc.name, "time_out"))

	def test_checking_out_an_already_departed_visitor_is_rejected(self):
		doc = self._log()
		doc.check_out()

		with self.assertRaises(frappe.ValidationError):
			doc.check_out()

	def test_checking_out_a_visit_that_was_never_submitted_is_rejected(self):
		doc = self._log(submit=False)

		with self.assertRaises(frappe.ValidationError):
			doc.check_out()

	def test_time_out_earlier_than_time_in_is_rejected(self):
		doc = self._log(submit=False)
		doc.time_in = "14:00:00"
		doc.save(ignore_permissions=True)
		doc.submit()

		doc.time_out = "13:00:00"

		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)
