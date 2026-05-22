# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

from typing import Iterable

import frappe
from frappe.utils import flt


def recalc_project_totals(project: str | None) -> None:
	"""Recompute project_expenses, project_payment, and total_sales_amount from submitted docs.

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
	sales = _sum_sales_orders(project)
	frappe.db.set_value(
		"Project",
		project,
		{
			"project_expenses": expenses,
			"project_payment": payment,
			"total_sales_amount": sales,
		},
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
	elif dt == "Sales Order":
		if doc.get("project"):
			projects.add(doc.project)
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

	A Receive Payment Entry contributes when:
	- The PE has a direct `project` link to this project, OR
	- A reference row points to a Sales Invoice whose project is this project.

	Each `Payment Entry Reference` row is counted at most once even if both conditions hold.
	"""
	rows = frappe.db.sql(
		"""
		select sum(per.allocated_amount) as total
		from `tabPayment Entry Reference` per
		join `tabPayment Entry` pe on pe.name = per.parent
		where pe.docstatus = 1
		  and pe.payment_type = 'Receive'
		  and (
		    pe.project = %(project)s
		    or (
		      per.reference_doctype = 'Sales Invoice'
		      and exists (
		        select 1 from `tabSales Invoice` si
		        where si.name = per.reference_name and si.project = %(project)s
		      )
		    )
		  )
		""",
		{"project": project},
		as_dict=True,
	)
	return flt(rows[0].total) if rows else 0


def _sum_sales_orders(project: str) -> float:
	# base_net_total (not net_total or grand_total) is Company Currency post-discount;
	# matches ERPNext core's own Project.update_sales_amount and is safe for multi-currency SOs.
	rows = frappe.db.sql(
		"""
		select sum(base_net_total) as total
		from `tabSales Order`
		where project = %s and docstatus = 1
		""",
		(project,),
		as_dict=True,
	)
	return flt(rows[0].total) if rows else 0


def recalc_project_completion(project: str | None, triggering_boq=None) -> None:
	"""Average BOQ stage progress (active stages only) and persist to Project.

	`triggering_boq` may be passed as the in-memory BOQ document when this is
	called from a validate hook (before DB flush). Its stage_N_progress values
	are used directly so the rollup reflects the current in-memory state.
	"""
	if not project or not frappe.db.exists("Project", project):
		return

	from dantata_town.dantata_town.boq_progress import STAGE_TABLES

	boqs = frappe.get_all(
		"Bill of Quantities",
		filters={"project": project, "docstatus": 1},
		pluck="name",
	)
	# Include the triggering BOQ even if it is not yet docstatus=1 in the DB
	# (e.g. it was submitted but the validate hook fires before the DB write).
	triggering_name = triggering_boq.name if triggering_boq else None
	if triggering_name and triggering_name not in boqs:
		boqs.append(triggering_name)

	if not boqs:
		frappe.db.set_value(
			"Project", project, "project_completion_percent", 0,
			update_modified=False,
		)
		return

	boq_completions = []
	for boq_name in boqs:
		# Use the in-memory doc when available; otherwise fetch from DB.
		if triggering_boq and boq_name == triggering_name:
			boq = triggering_boq
		else:
			boq = frappe.get_doc("Bill of Quantities", boq_name)
		active = [
			flt(boq.get(f"stage_{n}_progress"))
			for n, table_field in STAGE_TABLES.items()
			if boq.get(table_field)
		]
		if active:
			boq_completions.append(sum(active) / len(active))

	completion = (sum(boq_completions) / len(boq_completions)) if boq_completions else 0
	frappe.db.set_value(
		"Project", project, "project_completion_percent", completion,
		update_modified=False,
	)


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
