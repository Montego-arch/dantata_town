# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.utils import flt


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


def check_reservations(doc, method=None):
	"""Block save when (sum of approved SO qty for this Item, excluding this SO,
	plus this SO's qty) would exceed the (total - reserved) cap on its Site."""
	# Aggregate qty per item_code on this SO (handles multiple lines for same item).
	this_so_qty: dict[str, float] = {}
	for row in doc.items:
		this_so_qty[row.item_code] = this_so_qty.get(row.item_code, 0) + flt(row.qty)

	for item_code, qty_on_this in this_so_qty.items():
		site_row = frappe.db.sql(
			"""
			select parent as site, unit as total, reserved_unit as reserved
			from `tabProject Unit Item`
			where parenttype = 'Site' and building_type = %s
			limit 1
			""",
			(item_code,),
			as_dict=True,
		)
		if not site_row:
			continue  # not a site-tracked item
		site_row = site_row[0]
		cap = flt(site_row.total) - flt(site_row.reserved)

		# Sum of approved qty for this item across all other SOs (docstatus 1).
		other = frappe.db.sql(
			"""
			select coalesce(sum(soi.qty), 0)
			from `tabSales Order Item` soi
			join `tabSales Order` so on so.name = soi.parent
			where so.docstatus = 1
			  and so.name != %s
			  and soi.item_code = %s
			""",
			(doc.name or "", item_code),
		)
		approved_elsewhere = flt(other[0][0] if other else 0)

		total_after_save = approved_elsewhere + qty_on_this
		if total_after_save > cap:
			available = cap - approved_elsewhere
			frappe.throw(_(
				"Cannot sell {0} of {1}: only {2} of {3} units remain available on {4} (reserved: {5})."
			).format(qty_on_this, item_code, available, flt(site_row.total), site_row.site, flt(site_row.reserved)))
