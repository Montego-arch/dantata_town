# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _


UNLOCK_ROLE = "BOQ Approver"


@frappe.whitelist()
def unlock_boq_for_edit(name: str) -> None:
	"""Bypass workflow to revert an Approved BOQ to docstatus=0 for editing.

	Frappe core forbids docstatus=1 → 0 workflow transitions, so this lives
	outside the workflow as a role-gated custom action.
	"""
	if UNLOCK_ROLE not in frappe.get_roles():
		frappe.throw(_("Only {0} can unlock BOQs").format(UNLOCK_ROLE))
	current_status = frappe.db.get_value("Bill of Quantities", name, "docstatus")
	if current_status != 1:
		frappe.throw(_("Only submitted BOQs can be unlocked"))
	frappe.db.set_value(
		"Bill of Quantities", name,
		{"docstatus": 0, "workflow_state": "Unlocked"},
		update_modified=False,
	)
	frappe.db.commit()
