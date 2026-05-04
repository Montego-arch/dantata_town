# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def make_request_from_boq(boq: str, supplier: str, date: str, selected) -> str:
	"""Create a draft Sub Contractor Payment Request from selected BOQ rows.

	`selected` is a JSON-serialized list of dicts:
	  [{"stage_label", "boq_item_name", "description", "unit", "quantity", "rate"}]

	The original_quantity and original_rate fields are snapshotted at creation
	so the at-submit diff has stable reference values even if the source BOQ is
	later amended.
	"""
	if not frappe.db.exists("Bill of Quantities", boq):
		frappe.throw(_("BOQ {0} does not exist").format(boq))
	if frappe.db.get_value("Bill of Quantities", boq, "docstatus") != 1:
		frappe.throw(_(
			"BOQ {0} must be submitted before generating a payment request"
		).format(boq))

	rows = frappe.parse_json(selected) if isinstance(selected, str) else (selected or [])
	if not rows:
		frappe.throw(_("Select at least one line"))

	site, project = frappe.db.get_value(
		"Bill of Quantities", boq, ["site", "project"]
	)

	req = frappe.new_doc("Sub Contractor Payment Request")
	req.date = date
	req.site = site
	req.project = project
	req.boq = boq
	req.supplier = supplier
	for r in rows:
		req.append("items", {
			"stage_label": r.get("stage_label"),
			"description": r["description"],
			"unit": r.get("unit"),
			"quantity": flt(r["quantity"]),
			"rate": flt(r["rate"]),
			"original_quantity": flt(r["quantity"]),
			"original_rate": flt(r["rate"]),
			"boq_item": r.get("boq_item_name"),
		})
	req.insert(ignore_permissions=False)
	return req.name
