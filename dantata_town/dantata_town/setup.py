import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def create_boq_custom_fields():
	"""Create custom fields on ERPNext doctypes for BOQ and Site traceability."""
	custom_fields = {
		"Material Request Item": [
			{
				"fieldname": "boq",
				"fieldtype": "Link",
				"label": "Bill of Quantities",
				"options": "Bill of Quantities",
				"insert_after": "project",
				"read_only": 1,
				"module": "Dantata Town",
			},
			{
				"fieldname": "boq_detail",
				"fieldtype": "Data",
				"label": "BOQ Detail Reference",
				"insert_after": "boq",
				"hidden": 1,
				"read_only": 1,
				"module": "Dantata Town",
			},
		],
		"Project": [
			{
				"fieldname": "site",
				"fieldtype": "Link",
				"label": "Site",
				"options": "Site",
				"insert_after": "company",
				"module": "Dantata Town",
			},
		],
	}
	create_custom_fields(custom_fields, update=True)
