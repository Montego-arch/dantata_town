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
