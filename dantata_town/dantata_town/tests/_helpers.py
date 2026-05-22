# Shared test fixture helpers for the dantata_town test suite.

import frappe


def get_test_expense_account():
	"""Resolve an Expense Account from the default company for use as
	Site.expense_account in tests. Site.expense_account is mandatory, so every
	fixture that inserts a Site needs one."""
	company = frappe.db.get_single_value("Global Defaults", "default_company") \
		or frappe.db.get_value("Company", {}, "name")
	return frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Expense Account", "is_group": 0},
		"name",
	) or frappe.db.get_value(
		"Account", {"company": company, "is_group": 0, "root_type": "Expense"}, "name"
	)


def ensure_site_preconditions():
	"""Ensure the hardcoded defaults Site._check_setup_preconditions requires.

	Idempotent — safe to call from any test setUp."""
	if not frappe.db.exists("Item Group", "PROPERTIES"):
		frappe.get_doc({
			"doctype": "Item Group",
			"item_group_name": "PROPERTIES",
			"parent_item_group": "All Item Groups",
			"is_group": 0,
		}).insert(ignore_permissions=True)
	if not frappe.db.exists("UOM", "Unit"):
		frappe.get_doc({"doctype": "UOM", "uom_name": "Unit"}).insert(ignore_permissions=True)
