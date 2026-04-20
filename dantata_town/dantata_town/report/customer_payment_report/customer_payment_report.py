# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

from dantata_town.dantata_town.reports import build_customer_payment_report_rows


def execute(filters=None):
	columns = [
		{"label": "Customer", "fieldname": "customer", "fieldtype": "Link",
		 "options": "Customer", "width": 180},
		{"label": "Customer Name", "fieldname": "customer_name",
		 "fieldtype": "Data", "width": 200},
		{"label": "Invoice", "fieldname": "name", "fieldtype": "Link",
		 "options": "Sales Invoice", "width": 180},
		{"label": "Posting Date", "fieldname": "posting_date",
		 "fieldtype": "Date", "width": 110},
		{"label": "Due Date", "fieldname": "due_date",
		 "fieldtype": "Date", "width": 110},
		{"label": "Outstanding", "fieldname": "outstanding_amount",
		 "fieldtype": "Currency", "width": 140},
		{"label": "Property Type", "fieldname": "property_type",
		 "fieldtype": "Data", "width": 130},
		{"label": "Description", "fieldname": "property_description",
		 "fieldtype": "Data", "width": 260},
		{"label": "Plot", "fieldname": "plot_number",
		 "fieldtype": "Data", "width": 100},
	]
	return columns, build_customer_payment_report_rows()
