# Copyright (c) 2026, Montego-arch and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BOQItemDetail(Document):
	def validate(self):
		self.validate_item_for_material()

	def validate_item_for_material(self):
		if self.description_type == "Material" and not self.item:
			frappe.throw(_("Item is mandatory when Description Type is Material"))
