import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


PROJECT_TYPE_SEED = {
	"Building": ["PLOT", "DPC", "CARCASS", "SHELL", "FINISHED"],
	"Infrastructure": [
		"Roads", "Drainages", "Kerbstone", "Water Reticulation", "Electrification",
	],
}


def create_boq_custom_fields():
	"""Create custom fields on ERPNext doctypes for BOQ and Site traceability,
	and seed Dantata Town project classification data."""
	_create_custom_fields()
	_create_property_setters()
	_cleanup_broken_project_links()
	_seed_project_types_and_subtypes()


def _create_custom_fields():
	custom_fields = {
		"Material Request": [
			{
				"fieldname": "boq",
				"fieldtype": "Link",
				"label": "Bill of Quantities",
				"options": "Bill of Quantities",
				"insert_after": "material_request_type",
				"read_only": 1,
				"reqd": 1,
				"module": "Dantata Town",
			},
		],
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
				"insert_after": "project_name",
				"read_only": 1,
				"reqd": 1,
				"module": "Dantata Town",
			},
			{
				"fieldname": "project_subtype",
				"fieldtype": "Link",
				"label": "Project Subtype",
				"options": "Project Subtype",
				"insert_after": "project_type",
				"depends_on": "eval:doc.project_type",
				"link_filters": '[["Project Subtype","project_type","=","eval:doc.project_type"]]',
				"module": "Dantata Town",
			},
		],
		"Quotation": [
			{
				"fieldname": "dt_installment_section",
				"fieldtype": "Section Break",
				"label": "Payment Type",
				"insert_after": "terms_tab",
				"module": "Dantata Town",
			},
			{
				"fieldname": "payment_type",
				"fieldtype": "Select",
				"label": "Payment Type",
				"options": "\nInstallment\nOutright",
				"reqd": 1,
				"insert_after": "dt_installment_section",
				"module": "Dantata Town",
			},
			{
				"fieldname": "installment_column_break",
				"fieldtype": "Column Break",
				"insert_after": "payment_type",
				"module": "Dantata Town",
			},
			{
				"fieldname": "installment_start_date",
				"fieldtype": "Date",
				"label": "Installment Start Date",
				"insert_after": "installment_column_break",
				"depends_on": "eval:doc.payment_type === 'Installment'",
				"mandatory_depends_on": "eval:doc.payment_type === 'Installment'",
				"module": "Dantata Town",
			},
			{
				"fieldname": "installment_deposit_amount",
				"fieldtype": "Currency",
				"label": "Installment Deposit Amount",
				"insert_after": "installment_start_date",
				"depends_on": "eval:doc.payment_type === 'Installment'",
				"mandatory_depends_on": "eval:doc.payment_type === 'Installment'",
				"module": "Dantata Town",
			},
			{
				"fieldname": "installment_months",
				"fieldtype": "Int",
				"label": "Installment Months",
				"insert_after": "installment_deposit_amount",
				"depends_on": "eval:doc.payment_type === 'Installment'",
				"mandatory_depends_on": "eval:doc.payment_type === 'Installment'",
				"module": "Dantata Town",
			},
		],
	}
	create_custom_fields(custom_fields, update=True)


def _create_property_setters():
	"""Set customer as mandatory and allow in quick entry on Project."""
	property_setters = [
		("Project", "customer", "reqd", "1", "Check"),
		("Project", "customer", "allow_in_quick_entry", "1", "Check"),
		("Project", "project_type", "reqd", "1", "Check"),
	]
	for doctype, fieldname, prop, value, prop_type in property_setters:
		frappe.make_property_setter({
			"doctype": doctype,
			"fieldname": fieldname,
			"property": prop,
			"value": value,
			"property_type": prop_type,
		}, is_system_generated=False)


def _cleanup_broken_project_links():
	"""Remove any broken DocType Links on Project for Site."""
	for link in frappe.get_all("DocType Link", filters={
		"parent": "Project",
		"link_doctype": "Site",
	}, pluck="name"):
		frappe.delete_doc("DocType Link", link, force=True)
	frappe.clear_cache(doctype="Project")


def _seed_project_types_and_subtypes():
	"""Seed the Building/Infrastructure types and their subtypes.

	Idempotent: existing Internal/External/Other are never touched.
	"""
	for project_type, subtypes in PROJECT_TYPE_SEED.items():
		if not frappe.db.exists("Project Type", project_type):
			frappe.get_doc({
				"doctype": "Project Type",
				"project_type": project_type,
			}).insert(ignore_permissions=True)

		for subtype in subtypes:
			if not frappe.db.exists("Project Subtype", subtype):
				frappe.get_doc({
					"doctype": "Project Subtype",
					"subtype_name": subtype,
					"project_type": project_type,
				}).insert(ignore_permissions=True)
