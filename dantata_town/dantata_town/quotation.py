# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate


@frappe.whitelist()
def generate_installment_schedule(quotation_name):
	"""Rewrite the Quotation's payment_schedule child table from
	installment_deposit_amount + installment_start_date + installment_months.
	"""
	doc = frappe.get_doc("Quotation", quotation_name)
	doc.check_permission("write")
	_validate_installment_inputs(doc)

	total = flt(doc.grand_total)
	deposit = flt(doc.installment_deposit_amount)
	months = int(doc.installment_months)
	start = getdate(doc.installment_start_date)

	balance = total - deposit
	per_month_amount = flt(balance / months, 2)
	last_month_amount = flt(balance - per_month_amount * (months - 1), 2)

	# Only payment_amount is set; invoice_portion is intentionally omitted so
	# ERPNext's set_payment_schedule does not back-compute amounts from a
	# rounded percentage (which loses kobo on large totals). The percentage
	# is folded into the description for visibility instead.
	def _pct(amount):
		return flt(amount / total * 100, 2)

	doc.set("payment_schedule", [])
	doc.append("payment_schedule", {
		"due_date": start,
		"payment_amount": deposit,
		"description": _("Deposit ({0}%)").format(_pct(deposit)),
	})
	for i in range(1, months + 1):
		is_last = i == months
		amount = last_month_amount if is_last else per_month_amount
		doc.append("payment_schedule", {
			"due_date": add_months(start, i),
			"payment_amount": amount,
			"description": _("Installment {0} of {1} ({2}%)").format(
				i, months, _pct(amount)
			),
		})
	doc.save()
	return doc


def validate_quotation_payment_type(doc, method=None):
	"""Doc hook: clear installment fields if Outright; validate on submit if Installment."""
	if doc.payment_type == "Outright":
		doc.installment_deposit_amount = None
		doc.installment_start_date = None
		doc.installment_months = None
		return
	if doc.payment_type == "Installment":
		# Drafts are permissive so users can fill in gradually;
		# submit-time triggers a strict check.
		if doc.docstatus == 0:
			return
		_validate_installment_inputs(doc)


def _validate_installment_inputs(doc):
	if flt(doc.installment_deposit_amount) <= 0:
		frappe.throw(_("Installment Deposit Amount must be greater than zero."))
	if flt(doc.installment_deposit_amount) >= flt(doc.grand_total):
		frappe.throw(_("Installment Deposit Amount must be less than the Quotation total."))
	if not doc.installment_start_date:
		frappe.throw(_("Installment Start Date is required for installment plans."))
	if not doc.installment_months or int(doc.installment_months) < 1:
		frappe.throw(_("Installment Months must be at least 1."))
