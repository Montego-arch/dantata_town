# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

from frappe.model.document import Document
from frappe.utils import flt


class SubContractorPaymentRequest(Document):
	def validate(self):
		self._compute_amounts()

	def _compute_amounts(self):
		for row in self.items:
			row.amount = flt(row.quantity) * flt(row.rate)
		self.total_amount = sum(flt(row.amount) for row in self.items)
