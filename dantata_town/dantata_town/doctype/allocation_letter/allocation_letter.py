# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, now, today


class AllocationLetter(Document):
	def validate(self):
		if self.purchase_price_option == "Outright":
			self.installment_schedule = []
			self.payment_duration = None
			return

		if self.purchase_price_option == "Installment":
			if not self.payment_duration:
				frappe.throw(_("Payment Duration is required for installment offers."))
			if not self.installment_schedule:
				frappe.throw(_("Add at least one installment row for installment offers."))
			total = sum(flt(row.amount) for row in self.installment_schedule)
			if flt(total) != flt(self.cost_of_property):
				currency = frappe.defaults.get_global_default("currency")
				frappe.throw(_(
					"Installment schedule total ({0}) does not match Cost of Property ({1})."
				).format(
					frappe.utils.fmt_money(total, currency=currency),
					frappe.utils.fmt_money(self.cost_of_property, currency=currency),
				))

	def on_update(self):
		pass

	def before_submit(self):
		terms = frappe.get_single("Allocation Letter Terms")
		if not (terms.conditions_text or "").strip():
			frappe.throw(_(
				"Please configure Allocation Letter Terms → Conditions Text before submitting."
			))
		snapshot = terms.conditions_text
		if terms.withdrawal_clause_text:
			snapshot += "\n\n" + terms.withdrawal_clause_text
		self.terms_snapshot = snapshot


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
