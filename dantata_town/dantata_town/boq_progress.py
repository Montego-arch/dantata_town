# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate


# Map of BOQ stage number -> the parent's child-table fieldname for that stage.
# These names are baked into the existing Bill of Quantities doctype JSON.
STAGE_TABLES = {
	1: "table_txao",
	2: "description2",
	3: "description3",
	4: "description4",
	5: "description5",
	6: "description6",
	7: "description7",
	8: "description8",
	9: "description9",
	10: "description10",
	11: "description11",
	12: "description12",
	13: "description13",
	14: "description14",
	15: "description15",
	16: "description16",
	17: "description17",
	18: "description18",
	19: "description19",
	20: "description20",
}


def validate_stage_dates(doc, method=None):
	"""Require start/end dates for any stage that has line items, and end >= start."""
	for stage_no, table_field in STAGE_TABLES.items():
		rows = doc.get(table_field) or []
		if not rows:
			continue
		start = doc.get(f"stage_{stage_no}_start_date")
		end = doc.get(f"stage_{stage_no}_end_date")
		if not start or not end:
			frappe.throw(_(
				"Stage {0} has line items — start and end dates are required."
			).format(stage_no))
		if getdate(end) < getdate(start):
			frappe.throw(_(
				"Stage {0} end date cannot be before start date."
			).format(stage_no))


def recalc_boq_progress(doc, method=None):
	"""Recompute duration, progress, and status for each stage.

	Progress is count-based: 100 * checked / total.
	Status = "Completed" when progress hits 100 and the stage has at least one row.
	"""
	for stage_no, table_field in STAGE_TABLES.items():
		rows = doc.get(table_field) or []
		total = len(rows)
		done = sum(1 for r in rows if r.completed)
		progress = (100 * done / total) if total else 0
		doc.set(f"stage_{stage_no}_progress", progress)
		doc.set(
			f"stage_{stage_no}_status",
			"Completed" if total and flt(progress) == 100 else "",
		)
		start = doc.get(f"stage_{stage_no}_start_date")
		end = doc.get(f"stage_{stage_no}_end_date")
		doc.set(
			f"stage_{stage_no}_duration",
			(getdate(end) - getdate(start)).days if start and end else 0,
		)

	# After per-stage recompute, roll the BOQ's progress up to the linked Project.
	# Pass `doc` so recalc_project_completion can use the freshly computed in-memory
	# progress values rather than re-reading stale data from the DB (this hook fires
	# during validate, before the DB write).
	if doc.project:
		from dantata_town.dantata_town.project_aggregations import recalc_project_completion
		# Only inject the in-memory doc when it's already at docstatus=1 (the
		# submit-time validate case, where doc.docstatus is set to 1 in memory
		# before the DB write). Draft saves pass triggering=None so they don't
		# pollute the completion average.
		triggering = doc if doc.docstatus == 1 else None
		recalc_project_completion(doc.project, triggering_boq=triggering)
