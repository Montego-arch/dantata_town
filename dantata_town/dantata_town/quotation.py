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


def check_sellable_cap(doc, method=None):
	"""Block save when sum of qty across non-cancelled Quotation Items
	(excluding this Quotation) plus this Quotation's qty would exceed the
	Sellable cap on the matching Site row.

	Quotation Items whose item_code is not a building_type on any Site row
	are silently skipped (not site-tracked).
	"""
	this_qty: dict[str, float] = {}
	for row in doc.items:
		this_qty[row.item_code] = this_qty.get(row.item_code, 0) + flt(row.qty)

	for item_code, qty_on_this in this_qty.items():
		site_row = frappe.db.sql(
			"""
			select parent as site, unit, reserved_unit
			from `tabProject Unit Item`
			where parenttype = 'Site' and building_type = %s
			limit 1
			""",
			(item_code,),
			as_dict=True,
		)
		if not site_row:
			continue
		cap = flt(site_row[0].unit) - flt(site_row[0].reserved_unit)

		# Counts both draft (0) and submitted (1) quotations against the cap.
		# Cancelled (2) is excluded. This was an explicit design choice — drafts
		# consume capacity so concurrent users can't over-allocate the same units.
		other = frappe.db.sql(
			"""
			select coalesce(sum(qi.qty), 0)
			from `tabQuotation Item` qi
			join `tabQuotation` q on q.name = qi.parent
			where q.docstatus != 2
			  and q.name != %s
			  and qi.item_code = %s
			""",
			(doc.name or "", item_code),
		)
		other_qty = flt(other[0][0] if other else 0)

		if (other_qty + qty_on_this) > cap:
			available = cap - other_qty
			frappe.throw(_(
				"Cannot quote {0} of {1}: only {2} sellable on {3} "
				"(already on other quotations: {4})."
			).format(
				qty_on_this, item_code, available, site_row[0].site, other_qty
			))
