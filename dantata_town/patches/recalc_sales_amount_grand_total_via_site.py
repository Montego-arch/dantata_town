# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from dantata_town.dantata_town.project_aggregations import recalc_project_totals


def execute():
	"""Re-backfill Project.sales_order_amount after switching the Sales Order
	rollup from base_net_total + SO.project filter to grand_total + Site filter.

	Two reasons existing values may be stale:
	  - Projects whose SOs were never explicitly linked (SO.project IS NULL) used
	    to show 0; they now pick up SOs that share the Site.
	  - Projects whose SOs include taxes / shipping / additional discount had
	    base_net_total <> grand_total, so the historical figure was wrong.

	Recompute every Project that has a Site link (covers (b) above) and every
	Project that already had a directly-linked SO (covers the old code path).
	"""
	projects = set(
		frappe.db.sql_list(
			"""
			select name from `tabProject`
			where ifnull(site, '') != ''
			"""
		)
	)
	projects.update(
		frappe.db.sql_list(
			"""
			select distinct project from `tabSales Order`
			where docstatus = 1 and ifnull(project, '') != ''
			"""
		)
	)
	for p in projects:
		try:
			recalc_project_totals(p)
		except Exception as e:
			frappe.log_error(
				f"Backfill failed for Project {p}: {e}",
				"recalc_sales_amount_grand_total_via_site",
			)
	frappe.db.commit()
