# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class AllocationLetter(Document):
	def validate(self):
		pass

	def on_update(self):
		pass

	def before_submit(self):
		pass
