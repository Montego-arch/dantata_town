# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _

from dantata_town.dantata_town.project_aggregations import recalc_project_totals


def auto_link_orphan_sales_orders(doc, method=None):
	"""When a Project is saved with a Site link, find submitted Sales Orders
	whose items belong to that Site and that have no project link, and:
	  - If exactly one matches → set SO.project = this Project.
	  - If multiple match → throw with the candidate list (user must link manually).
	  - If none match → no-op for linking.

	Regardless of the linking outcome, always recompute this Project's totals
	at the end: the Site-based aggregation in `_sum_sales_orders` may pick up
	SOs that share the Site even without a direct project link, and recalcing
	on every save ensures a Project created *after* its SOs were submitted
	still rolls up correctly.

	Idempotent: already-linked SOs are excluded by the `so.project IS NULL`
	filter, so repeated saves do not re-link anything.
	"""
	if not doc.site:
		return
	candidates = frappe.db.sql(
		"""
		select distinct so.name
		from `tabSales Order` so
		join `tabSales Order Item` soi on soi.parent = so.name
		join `tabProject Unit Item` pui
		     on pui.building_type = soi.item_code
		    and pui.parenttype = 'Site'
		    and pui.parent = %(site)s
		where so.docstatus = 1
		  and (so.project is null or so.project = '')
		""",
		{"site": doc.site},
		as_dict=True,
	)
	if len(candidates) > 1:
		names = ", ".join(c.name for c in candidates)
		frappe.throw(_(
			"Multiple unlinked Sales Orders match Site {0}: {1}. "
			"Open the correct one and set its Project field manually."
		).format(doc.site, names))

	if len(candidates) == 1:
		so_name = candidates[0].name
		frappe.db.set_value(
			"Sales Order", so_name, "project", doc.name, update_modified=False
		)
		frappe.msgprint(
			_("Linked Sales Order {0} to this Project.").format(
				frappe.utils.get_link_to_form("Sales Order", so_name)
			),
			alert=True,
			indicator="blue",
		)

	# Always recalc, even when no orphan SO was linked — the Site-based sum
	# catches SOs the per-site-Item join misses (generic SKUs etc.).
	recalc_project_totals(doc.name)
