# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _


def fetch_from_project(doc, method=None):
	"""When SO.project is set and SO.customer is blank, copy customer from Project.

	Hooked on `before_validate` so the customer is populated before ERPNext core's
	`validate` runs (which requires customer to be set).
	"""
	if not doc.project or doc.customer:
		return
	customer = frappe.db.get_value("Project", doc.project, "customer")
	if customer:
		doc.customer = customer


def enforce_one_so_per_project(doc, method=None):
	"""Block save if another non-cancelled SO already links to this project."""
	if not doc.project:
		return
	existing = frappe.db.sql(
		"""
		select name from `tabSales Order`
		where project = %s and name != %s and docstatus != 2
		limit 1
		""",
		(doc.project, doc.name or ""),
	)
	if existing:
		frappe.throw(
			_("Project {0} is already linked to Sales Order {1}").format(
				doc.project, existing[0][0]
			)
		)


@frappe.whitelist()
def existing_so_for_project(project: str, current_so: str | None = None) -> str | None:
	"""Return the name of any existing non-cancelled SO already linked to `project`,
	excluding `current_so` if provided. Used by the SO form script for inline UX."""
	if not project:
		return None
	row = frappe.db.sql(
		"""
		select name from `tabSales Order`
		where project = %s and name != %s and docstatus != 2
		limit 1
		""",
		(project, current_so or ""),
	)
	return row[0][0] if row else None
