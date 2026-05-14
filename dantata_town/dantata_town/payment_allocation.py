# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.utils import flt


def allocate_so_payments(sales_order: str | None) -> None:
	"""Recompute paid_amount and outstanding FIFO across the SO's payment_schedule.

	Payments are received-side: PEs that reference the SO, plus JE credits to a
	Receivable account tagged with the SO's project.
	"""
	if not sales_order or not frappe.db.exists("Sales Order", sales_order):
		return
	so = frappe.get_doc("Sales Order", sales_order)
	rows = sorted(so.payment_schedule or [], key=lambda r: (r.due_date, r.idx))
	if not rows:
		return

	received = _sum_pe_to_so(sales_order)
	if so.project:
		received += _sum_je_to_project_receivable(so.project)

	remaining = flt(received)
	for row in rows:
		amount = flt(row.payment_amount)
		paid = min(remaining, amount)
		outstanding = amount - paid
		frappe.db.set_value(
			"Payment Schedule", row.name,
			{"paid_amount": paid, "outstanding": outstanding},
			update_modified=False,
		)
		remaining -= paid


def recalc_for_pe(doc, method=None) -> None:
	"""Doc-event entrypoint for Payment Entry. Recompute touched SOs + ALs."""
	touched_sos = set()
	for ref in doc.get("references") or []:
		if ref.reference_doctype == "Sales Order" and ref.reference_name:
			touched_sos.add(ref.reference_name)
	for so in touched_sos:
		allocate_so_payments(so)
		al = frappe.db.get_value(
			"Allocation Letter",
			{"sales_order": so, "docstatus": 1},
			"name",
		)
		if al:
			allocate_al_installments(al)


def recalc_for_je(doc, method=None) -> None:
	"""Doc-event entrypoint for Journal Entry. Recompute SOs + ALs of touched projects."""
	projects = {row.project for row in (doc.get("accounts") or []) if row.get("project")}
	if not projects:
		return
	for project in projects:
		sos = frappe.get_all(
			"Sales Order",
			filters={"project": project, "docstatus": 1},
			pluck="name",
		)
		for so in sos:
			allocate_so_payments(so)
			al = frappe.db.get_value(
				"Allocation Letter",
				{"sales_order": so, "docstatus": 1},
				"name",
			)
			if al:
				allocate_al_installments(al)


def _sum_pe_to_so(sales_order: str) -> float:
	"""Sum allocated amounts from submitted PEs referencing this SO."""
	rows = frappe.db.sql(
		"""
		select coalesce(sum(per.allocated_amount), 0)
		from `tabPayment Entry Reference` per
		join `tabPayment Entry` pe on pe.name = per.parent
		where pe.docstatus = 1
		  and pe.payment_type = 'Receive'
		  and per.reference_doctype = 'Sales Order'
		  and per.reference_name = %s
		""",
		(sales_order,),
	)
	return flt(rows[0][0] if rows else 0)


def _sum_je_to_project_receivable(project: str) -> float:
	"""Sum JE credits to Receivable accounts tagged with this project."""
	rows = frappe.db.sql(
		"""
		select coalesce(sum(ja.credit_in_account_currency), 0)
		from `tabJournal Entry Account` ja
		join `tabJournal Entry` je on je.name = ja.parent
		join `tabAccount` acc on acc.name = ja.account
		where je.docstatus = 1
		  and ja.project = %s
		  and acc.account_type = 'Receivable'
		""",
		(project,),
	)
	return flt(rows[0][0] if rows else 0)


def allocate_al_installments(allocation_letter: str | None) -> None:
	"""Mirror of allocate_so_payments but updates AL.installment_schedule rows.

	The AL's installments use field `amount` (not `payment_amount`). Payments are
	pulled from the AL's linked Sales Order: PEs referencing that SO plus JE credits
	to a Receivable account tagged with the SO's project.
	"""
	if not allocation_letter or not frappe.db.exists("Allocation Letter", allocation_letter):
		return
	al = frappe.get_doc("Allocation Letter", allocation_letter)
	rows = sorted(al.get("installment_schedule") or [], key=lambda r: (r.due_date, r.idx))
	if not rows or not al.sales_order:
		return

	received = _sum_pe_to_so(al.sales_order)
	so_project = frappe.db.get_value("Sales Order", al.sales_order, "project")
	if so_project:
		received += _sum_je_to_project_receivable(so_project)

	remaining = flt(received)
	for row in rows:
		amount = flt(row.amount)
		paid = min(remaining, amount)
		outstanding = amount - paid
		frappe.db.set_value(
			"Allocation Letter Installment", row.name,
			{"paid_amount": paid, "outstanding": outstanding},
			update_modified=False,
		)
		remaining -= paid
