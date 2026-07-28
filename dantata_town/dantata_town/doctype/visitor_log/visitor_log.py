# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_time, nowtime


class VisitorLog(Document):
	def before_insert(self):
		# Frappe stamps every empty Time field with nowtime() while applying
		# defaults, so time_out has to be cleared or no visitor is ever on site.
		self.time_in = nowtime()
		self.time_out = None

	def validate(self):
		self.validate_time_order()

	def before_update_after_submit(self):
		self.validate_time_order()

	def validate_time_order(self):
		if self.time_in and self.time_out and get_time(self.time_out) < get_time(self.time_in):
			frappe.throw(_("Time Out cannot be earlier than Time In."))

	@frappe.whitelist()
	def check_out(self):
		if self.docstatus != 1:
			frappe.throw(_("Submit the visit before checking the visitor out."))

		if self.time_out:
			frappe.throw(_("{0} has already been checked out.").format(self.visitor_name))

		self.time_out = nowtime()
		self.save()
