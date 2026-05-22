# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from dantata_town.dantata_town.project_aggregations import recalc_project_totals


def execute():
	"""One-time backfill: recompute Project.total_sales_amount (and the new
	sales_order_amount custom field) for every Project that has at least one
	submitted Sales Order linked.

	Phase-4 added the field display but never wired a recompute trigger, so
	existing data never refreshed. Task 4 added the recompute trigger; this
	patch fills in the historical values.
	"""
	projects = frappe.db.sql_list(
		"""
		select distinct project from `tabSales Order`
		where docstatus = 1 and ifnull(project, '') != ''
		"""
	)
	for p in projects:
		# Per-project try/except so one bad row (e.g., orphaned SO data) doesn't
		# abort the whole backfill — Frappe's patch log marks the patch executed
		# even on partial failure, so a clean log line per failure is critical.
		try:
			recalc_project_totals(p)
		except Exception as e:
			frappe.log_error(
				f"Backfill failed for Project {p}: {e}",
				"recalc_sales_amount_for_existing_projects",
			)
	frappe.db.commit()
