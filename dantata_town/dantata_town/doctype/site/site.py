# Copyright (c) 2026, Montego-arch and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import flt


class Site(Document):
	def validate(self):
		self.calculate_totals()

	def calculate_totals(self):
		total = 0
		for row in self.get("project_units") or []:
			row.amount = flt(row.projected_quantity) * flt(row.rate)
			total += flt(row.projected_quantity)
		self.total_units = total
