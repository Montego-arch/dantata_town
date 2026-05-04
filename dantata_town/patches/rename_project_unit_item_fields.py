# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	"""Rename Project Unit Item fields to match construction terminology.

	unit_type -> building_type
	projected_quantity -> unit

	Idempotent: guarded by column-existence checks.
	After copying data, the old columns are dropped so the table stays clean.
	"""
	cols = frappe.db.get_table_columns("Project Unit Item")

	if "unit_type" in cols and "building_type" not in cols:
		rename_field("Project Unit Item", "unit_type", "building_type")

	if "projected_quantity" in cols and "unit" not in cols:
		rename_field("Project Unit Item", "projected_quantity", "unit")

	# Drop orphaned old columns that rename_field leaves behind.
	# Re-fetch cols in case they changed above.
	cols = frappe.db.get_table_columns("Project Unit Item")
	if "unit_type" in cols:
		frappe.db.sql("ALTER TABLE `tabProject Unit Item` DROP COLUMN `unit_type`")
	if "projected_quantity" in cols:
		frappe.db.sql("ALTER TABLE `tabProject Unit Item` DROP COLUMN `projected_quantity`")

	frappe.clear_cache(doctype="Project Unit Item")
	frappe.clear_cache(doctype="Site")
