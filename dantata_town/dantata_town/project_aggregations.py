# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

from typing import Iterable

import frappe
from frappe.utils import flt


def recalc_project_totals(project: str | None) -> None:
	"""Recompute project_expenses and project_payment from submitted docs.

	Re-sums from docstatus=1 rows so cancellation/amendment is naturally consistent.
	No-op if project is falsy or does not exist.
	"""
	if not project:
		return
	if not frappe.db.exists("Project", project):
		return
	expenses = (
		_sum_purchase_invoice_items(project)
		+ _sum_expense_claims(project)
		+ _sum_journal_debits(project)
	)
	payment = (
		_sum_payment_entry_references(project)
		+ _sum_journal_credits_to_receivable(project)
	)
	frappe.db.set_value(
		"Project",
		project,
		{"project_expenses": expenses, "project_payment": payment},
		update_modified=False,
	)


def recalc_for_doc(doc, method=None) -> None:
	"""Doc-event hook entrypoint. Recalculates each Project the doc touches."""
	for project in _projects_touched_by(doc):
		recalc_project_totals(project)


def _projects_touched_by(doc) -> Iterable[str]:
	"""Return the unique set of Project names linked from `doc`.

	Different shape per doctype:
	- Purchase Invoice: items[].project
	- Expense Claim: parent.project
	- Journal Entry: accounts[].project
	- Payment Entry: references[] -> resolve project from the referenced Sales Invoice / Purchase Invoice
	"""
	projects: set[str] = set()
	dt = doc.doctype

	if dt == "Purchase Invoice":
		for row in doc.get("items") or []:
			if row.get("project"):
				projects.add(row.project)
	elif dt == "Expense Claim":
		if doc.get("project"):
			projects.add(doc.project)
	elif dt == "Journal Entry":
		for row in doc.get("accounts") or []:
			if row.get("project"):
				projects.add(row.project)
	elif dt == "Payment Entry":
		# Direct project field if present on the Payment Entry parent
		if doc.get("project"):
			projects.add(doc.project)
		# Resolve via referenced invoices
		for row in doc.get("references") or []:
			ref_dt = row.get("reference_doctype")
			ref_name = row.get("reference_name")
			if not ref_dt or not ref_name:
				continue
			project = frappe.db.get_value(ref_dt, ref_name, "project")
			if project:
				projects.add(project)
	return projects


def _sum_purchase_invoice_items(project: str) -> float:
	rows = frappe.db.sql(
		"""
		select sum(pii.amount) as total
		from `tabPurchase Invoice Item` pii
		join `tabPurchase Invoice` pi on pi.name = pii.parent
		where pi.docstatus = 1 and pii.project = %s
		""",
		(project,),
		as_dict=True,
	)
	return flt(rows[0].total) if rows else 0


def _sum_expense_claims(project: str) -> float:
	rows = frappe.db.sql(
		"""
		select sum(total_sanctioned_amount) as total
		from `tabExpense Claim`
		where project = %s and docstatus = 1
		""",
		(project,),
		as_dict=True,
	)
	return flt(rows[0].total) if rows else 0


def _sum_journal_debits(project: str) -> float:
	rows = frappe.db.sql(
		"""
		select sum(ja.debit_in_account_currency) as total
		from `tabJournal Entry Account` ja
		join `tabJournal Entry` je on je.name = ja.parent
		where je.docstatus = 1 and ja.project = %s
		""",
		(project,),
		as_dict=True,
	)
	return flt(rows[0].total) if rows else 0


def _sum_journal_credits_to_receivable(project: str) -> float:
	rows = frappe.db.sql(
		"""
		select sum(ja.credit_in_account_currency) as total
		from `tabJournal Entry Account` ja
		join `tabJournal Entry` je on je.name = ja.parent
		join `tabAccount` acc on acc.name = ja.account
		where je.docstatus = 1
		  and ja.project = %s
		  and acc.account_type = 'Receivable'
		""",
		(project,),
		as_dict=True,
	)
	return flt(rows[0].total) if rows else 0


def _sum_payment_entry_references(project: str) -> float:
	"""Sum allocated amounts from Payment Entries that touch this project.

	A Payment Entry touches `project` if either:
	- The PE itself has `project = X`, or
	- A reference row points to a Sales/Purchase Invoice whose project is X.

	Receive payments (party_type=Customer) count as money-in.
	"""
	rows = frappe.db.sql(
		"""
		select sum(per.allocated_amount) as total
		from `tabPayment Entry Reference` per
		join `tabPayment Entry` pe on pe.name = per.parent
		where pe.docstatus = 1
		  and pe.payment_type = 'Receive'
		  and (
		    per.reference_doctype = 'Sales Invoice'
		    and exists (
		      select 1 from `tabSales Invoice` si
		      where si.name = per.reference_name and si.project = %(project)s
		    )
		  )
		""",
		{"project": project},
		as_dict=True,
	)
	return flt(rows[0].total) if rows else 0


@frappe.whitelist()
def get_site_building_types(doctype, txt, searchfield, start, page_len, filters):
	"""Search-query handler for the Project.building_type set_query.

	Returns Items present in the chosen Site's project_units.building_type.
	"""
	site = (filters or {}).get("site")
	if not site:
		return []
	return frappe.db.sql(
		"""
		select distinct pu.building_type, item.item_name
		from `tabProject Unit Item` pu
		left join `tabItem` item on item.name = pu.building_type
		where pu.parent = %(site)s
		  and pu.parenttype = 'Site'
		  and (pu.building_type like %(txt)s or item.item_name like %(txt)s)
		order by pu.building_type
		limit %(start)s, %(page_len)s
		""",
		{
			"site": site,
			"txt": f"%{txt}%",
			"start": start,
			"page_len": page_len,
		},
	)
