import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


PROJECT_TYPE_SEED = {
	"Building": ["PLOT", "DPC", "CARCASS", "SHELL", "FINISHED"],
	"Infrastructure": [
		"Roads", "Drainages", "Kerbstone", "Water Reticulation", "Electrification",
	],
}


def create_boq_custom_fields():
	"""Register custom fields on Material Request, Project, Quotation, BOQ
	Items, and Purchase Invoice; seed Dantata Town project types and subtypes;
	and install BOQ workflow.
	(Site customizations live in site.json.)"""
	_create_custom_fields()
	_create_property_setters()
	_cleanup_broken_project_links()
	_seed_project_types_and_subtypes()
	_create_boq_workflow()


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
			{
				"fieldname": "building_type",
				"fieldtype": "Link",
				"label": "Building Type",
				"options": "Item",
				"insert_after": "site",
				"depends_on": "eval:doc.site",
				"module": "Dantata Town",
			},
			{
				"fieldname": "dt_financials_section",
				"fieldtype": "Section Break",
				"label": "Financials",
				"insert_after": "project_subtype",
				"module": "Dantata Town",
			},
			{
				"fieldname": "project_expenses",
				"fieldtype": "Currency",
				"label": "Project Expenses",
				"insert_after": "dt_financials_section",
				"read_only": 1,
				"module": "Dantata Town",
			},
			{
				"fieldname": "dt_financials_col",
				"fieldtype": "Column Break",
				"insert_after": "project_expenses",
				"module": "Dantata Town",
			},
			{
				"fieldname": "project_payment",
				"fieldtype": "Currency",
				"label": "Project Payment",
				"insert_after": "dt_financials_col",
				"read_only": 1,
				"module": "Dantata Town",
			},
			{
				"fieldname": "project_completion_percent",
				"fieldtype": "Percent",
				"label": "Completion",
				"insert_after": "project_payment",
				"read_only": 1,
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
		"BOQ Items": [
			{
				"fieldname": "completed",
				"fieldtype": "Check",
				"label": "Completed",
				"insert_after": "actual_amount",
				"allow_on_submit": 1,
				"in_list_view": 1,
				"module": "Dantata Town",
			},
			{
				"fieldname": "assignment_type",
				"fieldtype": "Select",
				"label": "Assignment Type",
				"options": "Company\nSub Contractor",
				"default": "Company",
				"insert_after": "completed",
				"allow_on_submit": 1,
				"in_list_view": 1,
				"module": "Dantata Town",
			},
		],
		"Purchase Invoice": [
			{
				"fieldname": "site",
				"fieldtype": "Link",
				"label": "Site",
				"options": "Site",
				"insert_after": "company",
				"module": "Dantata Town",
			},
			{
				"fieldname": "sub_contractor_payment_request",
				"fieldtype": "Link",
				"label": "Sub Contractor Payment Request",
				"options": "Sub Contractor Payment Request",
				"insert_after": "site",
				"read_only": 1,
				"module": "Dantata Town",
			},
		],
	}

	# Per-stage tracking fields on Bill of Quantities (× 15 stages)
	stage_summary_fieldnames = {n: f"stage_{n}_summary" for n in range(1, 16)}
	boq_stage_fields = []
	for stage_no, summary_fieldname in stage_summary_fieldnames.items():
		previous = summary_fieldname
		for suffix, ftype, extra in [
			("start_date", "Date", {"allow_on_submit": 1}),
			("end_date", "Date", {"allow_on_submit": 1}),
			# duration / progress / status are server-computed in validate.
			# allow_on_submit lets the auto-save (triggered by toggling a line-item
			# `completed` checkbox) persist the recomputed values without Frappe
			# rejecting them as "Not allowed to change after submission".
			# read_only still prevents direct UI editing.
			("duration", "Int", {"read_only": 1, "allow_on_submit": 1, "label_extra": " (days)"}),
			("progress", "Percent", {"read_only": 1, "allow_on_submit": 1}),
			("status", "Data", {"read_only": 1, "allow_on_submit": 1}),
		]:
			fieldname = f"stage_{stage_no}_{suffix}"
			label_extra = extra.pop("label_extra", "")
			label = f"Stage {stage_no} {suffix.replace('_', ' ').title()}{label_extra}"
			boq_stage_fields.append({
				"fieldname": fieldname,
				"fieldtype": ftype,
				"label": label,
				"insert_after": previous,
				"module": "Dantata Town",
				**extra,
			})
			previous = fieldname
	custom_fields.setdefault("Bill of Quantities", []).extend(boq_stage_fields)

	create_custom_fields(custom_fields, update=True)
	_force_allow_on_submit_flags()


def _force_allow_on_submit_flags():
	"""Frappe v15's create_custom_fields(update=True) sometimes silently skips
	flag updates on existing Custom Fields. Force allow_on_submit=1 directly via
	db_set on every field that needs it, so a migrate after this function runs
	is guaranteed to land the flag (especially on sites where the field was
	originally created with allow_on_submit=0).

	Also force read_only=0 on Project.site so the quick entry can show it
	(read-only fields are excluded from the quick entry dialog regardless of
	allow_in_quick_entry). The same skip-on-update behavior in v15 means an
	already-existing read_only=1 row will not be cleared without this nudge.
	"""
	enforce = []
	enforce.append(("BOQ Items", "completed"))
	enforce.append(("BOQ Items", "assignment_type"))
	for stage in range(1, 16):
		for suffix in ("start_date", "end_date", "duration", "progress", "status"):
			enforce.append(("Bill of Quantities", f"stage_{stage}_{suffix}"))

	for dt, fieldname in enforce:
		cf = frappe.db.get_value(
			"Custom Field", {"dt": dt, "fieldname": fieldname}, "name"
		)
		if cf:
			frappe.db.set_value(
				"Custom Field", cf, "allow_on_submit", 1, update_modified=False
			)

	site_cf = frappe.db.get_value(
		"Custom Field", {"dt": "Project", "fieldname": "site"}, "name"
	)
	if site_cf:
		frappe.db.set_value(
			"Custom Field", site_cf, "read_only", 0, update_modified=False
		)


def _create_property_setters():
	"""Set customer as mandatory and allow in quick entry on Project, and
	hide the unused invoice_portion column on the Payment Schedule grid
	(percentage is folded into the description for installment plans)."""
	property_setters = [
		("Project", "customer", "reqd", "1", "Check"),
		("Project", "customer", "allow_in_quick_entry", "1", "Check"),
		("Project", "site", "allow_in_quick_entry", "1", "Check"),
		("Project", "building_type", "allow_in_quick_entry", "1", "Check"),
		("Project", "project_type", "reqd", "1", "Check"),
		("Payment Schedule", "invoice_portion", "in_list_view", "0", "Check"),
		("Project", "total_sales_amount", "hidden", "0", "Check"),
		("Project", "total_sales_amount", "label", "Sales Order Amount", "Data"),
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


def _create_boq_workflow():
	"""Create BOQ Approver role + workflow; backfill existing submitted BOQs.

	Idempotent: safe to run multiple times via after_install / after_migrate.
	"""
	role_name = "BOQ Approver"
	system_manager = "System Manager"

	if not frappe.db.exists("Role", role_name):
		frappe.get_doc({
			"doctype": "Role",
			"role_name": role_name,
			"desk_access": 1,
		}).insert(ignore_permissions=True)

	# Workflow State and Action master records must exist before the Workflow.
	for state_name, style in [
		("Draft", "Warning"),
		("Pending Approval", "Primary"),
		("Approved", "Success"),
		("Unlocked", "Danger"),
		("Rejected", "Danger"),
	]:
		if not frappe.db.exists("Workflow State", state_name):
			frappe.get_doc({
				"doctype": "Workflow State",
				"workflow_state_name": state_name,
				"style": style,
			}).insert(ignore_permissions=True)

	for action in [
		"Submit for Approval", "Approve", "Reject", "Re-open", "Unlock for Edit", "Re-approve",
	]:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({
				"doctype": "Workflow Action Master",
				"workflow_action_name": action,
			}).insert(ignore_permissions=True)

	workflow_name = "Bill of Quantities Approval"
	if frappe.db.exists("Workflow", workflow_name):
		wf = frappe.get_doc("Workflow", workflow_name)
		wf.is_active = 1
	else:
		wf = frappe.new_doc("Workflow")
		wf.workflow_name = workflow_name
		wf.document_type = "Bill of Quantities"
		wf.is_active = 1
		wf.workflow_state_field = "workflow_state"

	# Replace states.
	# NOTE: Frappe blocks transitions from doc_status=1 → doc_status=0.
	# Therefore all states reachable from "Approved" (doc_status=1) must also
	# use doc_status=1. "Unlocked" is doc_status=1 with allow_edit=BOQ Approver
	# so the approver can modify without cancelling. "Pending Approval" remains
	# doc_status=0 so that Reject (→ Rejected, doc_status=0) is valid.
	wf.states = []
	for state_name, doc_status, allow_edit in [
		("Draft", "0", system_manager),
		("Pending Approval", "0", system_manager),
		("Approved", "1", role_name),
		("Unlocked", "1", role_name),
		("Rejected", "0", system_manager),
	]:
		wf.append("states", {
			"state": state_name,
			"doc_status": doc_status,
			"allow_edit": allow_edit,
		})

	# Replace transitions.
	# "Unlocked → Re-approve → Approved" is used instead of routing back through
	# Pending Approval (which would require crossing the 1→0 docstatus boundary
	# that Frappe's validate_docstatus disallows).
	wf.transitions = []
	for state, action, next_state, allowed in [
		("Draft", "Submit for Approval", "Pending Approval", system_manager),
		("Pending Approval", "Approve", "Approved", role_name),
		("Pending Approval", "Reject", "Rejected", role_name),
		("Rejected", "Re-open", "Draft", system_manager),
		("Approved", "Unlock for Edit", "Unlocked", role_name),
		("Unlocked", "Re-approve", "Approved", role_name),
	]:
		wf.append("transitions", {
			"state": state,
			"action": action,
			"next_state": next_state,
			"allowed": allowed,
		})

	wf.save(ignore_permissions=True)

	# Backfill: any submitted BOQ without a workflow_state becomes "Approved".
	frappe.db.sql(
		"""
		update `tabBill of Quantities`
		set workflow_state = 'Approved'
		where docstatus = 1
		  and (workflow_state is null or workflow_state = '')
		"""
	)
