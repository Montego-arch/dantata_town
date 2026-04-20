# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, now, today


class AllocationLetter(Document):
	def validate(self):
		pass

	def on_update(self):
		pass

	def before_submit(self):
		pass


@frappe.whitelist()
def make_allocation_letter(source_name, target_doc=None):
	"""Create an Allocation Letter pre-filled from a Sales Order."""

	def set_defaults(source, target):
		from frappe.contacts.doctype.address.address import get_default_address

		target.letter_date = today()
		target.addressee_name = source.customer_name
		primary_addr = get_default_address("Customer", source.customer)
		if primary_addr:
			addr = frappe.get_doc("Address", primary_addr)
			lines = [addr.address_line1, addr.address_line2, addr.city, addr.country]
			target.addressee_address = "\n".join([l for l in lines if l])

		terms = frappe.get_single("Allocation Letter Terms")
		if terms.default_chairman_name:
			target.chairman_name = terms.default_chairman_name
		target.company_name = terms.default_company_name or "Dantata Town Developers Ltd"

	return get_mapped_doc(
		"Sales Order",
		source_name,
		{
			"Sales Order": {
				"doctype": "Allocation Letter",
				"field_map": {
					"name": "sales_order",
					"customer": "customer",
					"customer_name": "customer_name",
					"grand_total": "cost_of_property",
				},
			},
		},
		target_doc,
		set_defaults,
	)
