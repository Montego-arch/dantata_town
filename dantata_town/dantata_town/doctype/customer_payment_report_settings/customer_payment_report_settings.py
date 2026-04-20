# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_address


class CustomerPaymentReportSettings(Document):
	def validate(self):
		if self.enabled and not (self.recipient_emails or "").strip():
			frappe.throw(_("Recipient Emails is required when Enabled is checked."))
		if self.send_day_of_month < 1 or self.send_day_of_month > 28:
			frappe.throw(_("Send Day of Month must be between 1 and 28."))
		for line in (self.recipient_emails or "").splitlines():
			line = line.strip()
			if line:
				validate_email_address(line, throw=True)
