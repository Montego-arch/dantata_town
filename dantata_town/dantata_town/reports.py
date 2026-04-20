# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _


def build_customer_payment_report_rows():
	"""Return a list of dicts, one per outstanding (customer, invoice) row,
	ordered by customer asc, posting_date asc. Each row contains:
	  customer, customer_name, name (invoice), posting_date, due_date,
	  outstanding_amount, property_type, property_description, plot_number.
	Property fields default to "—" when there's no linked Allocation Letter.
	"""
	sis = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "outstanding_amount": (">", 0)},
		fields=["name", "customer", "customer_name", "posting_date",
		        "due_date", "outstanding_amount"],
		order_by="customer asc, posting_date asc",
	)
	so_to_al = {}
	rows = []
	for si in sis:
		so = frappe.db.get_value(
			"Sales Invoice Item",
			{"parent": si.name, "sales_order": ("!=", "")},
			"sales_order",
		)
		if so and so not in so_to_al:
			al_name = frappe.db.get_value(
				"Allocation Letter",
				{"sales_order": so, "docstatus": 1},
				"name",
				order_by="letter_date desc",
			)
			so_to_al[so] = frappe.db.get_value(
				"Allocation Letter", al_name,
				["property_type", "property_description", "plot_number"],
				as_dict=True,
			) if al_name else None
		al = so_to_al.get(so) if so else None
		rows.append({
			**si,
			"property_type": (al or {}).get("property_type") or "—",
			"property_description": (al or {}).get("property_description") or "—",
			"plot_number": (al or {}).get("plot_number") or "—",
		})
	return rows
