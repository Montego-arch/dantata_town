# Copyright (c) 2026, Montego-arch and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, nowdate, get_link_to_form
from frappe.model.document import Document


STAGE_TABLE_FIELDS = ["table_txao"] + [f"description{n}" for n in range(2, 16)]

STAGE_NAME_MAP = [("stage_1", "table_txao", "stage_1_summary")] + [
	(f"stage_{n}", f"description{n}", f"stage_{n}_summary") for n in range(2, 16)
]


class BillofQuantities(Document):
	def validate(self):
		self.validate_project_site()
		self.calculate_amounts()
		self.calculate_quantities()
		self.update_summary()

	def validate_project_site(self):
		"""Ensure the project belongs to the selected site."""
		if self.project and self.site:
			project_site = frappe.db.get_value("Project", self.project, "site")
			if project_site != self.site:
				frappe.throw(
					_("Project {0} does not belong to Site {1}").format(
						self.project, self.site
					)
				)

	def calculate_amounts(self):
		for table_field in STAGE_TABLE_FIELDS:
			for row in self.get(table_field) or []:
				row.amount = flt(row.planned_quantity) * flt(row.rate)
				row.actual_amount = flt(row.consumed_quantity) * flt(row.actual_rate)

	def calculate_quantities(self):
		for table_field in STAGE_TABLE_FIELDS:
			for row in self.get(table_field) or []:
				row.remaining_quantity = flt(row.planned_quantity) - flt(row.consumed_quantity)
				row.actual_quantity = flt(row.consumed_quantity) + flt(row.variation_quantity)

	def update_summary(self):
		self.set("summary", [])
		for stage_name_field, table_field, summary_field in STAGE_NAME_MAP:
			stage_name = self.get(stage_name_field)
			rows = self.get(table_field) or []

			# Clear per-stage summary
			self.set(summary_field, [])

			if not stage_name and not rows:
				continue

			label = stage_name or stage_name_field.replace("_", " ").title()

			labour_total = 0
			material_total = 0
			for row in rows:
				if row.description_type == "Labour":
					labour_total += flt(row.amount)
				elif row.description_type == "Material":
					material_total += flt(row.amount)
				else:
					material_total += flt(row.amount)

			if labour_total or material_total:
				# Recompute progress inline (count-based: completed rows / total rows).
				# This avoids depending on hook firing order — recalc_boq_progress runs
				# after validate(), so stage_N_progress may not be current here yet.
				total_rows = len(rows)
				done_rows = sum(1 for r in rows if r.get("completed"))
				progress = (100 * done_rows / total_rows) if total_rows else 0
				summary_row = {
					"stage": label,
					"description": label,
					"labour": labour_total,
					"material": material_total,
					"amount": labour_total + material_total,
					"progress": progress,
				}
				# Per-stage summary
				self.append(summary_field, summary_row)
				# Overall summary
				self.append("summary", summary_row)


@frappe.whitelist()
def create_material_request(boq_name, child_docname, qty):
	"""Create a Material Request from a specific BOQ Items row."""
	qty = flt(qty)
	if qty <= 0:
		frappe.throw(_("Quantity must be greater than zero"))

	boq = frappe.get_doc("Bill of Quantities", boq_name)
	boq.check_permission("read")

	# Find the child row across all stage tables
	row = None
	for table_field in STAGE_TABLE_FIELDS:
		for r in boq.get(table_field) or []:
			if r.name == child_docname:
				row = r
				break
		if row:
			break

	if not row:
		frappe.throw(_("BOQ Item row not found"))

	if row.description_type != "Material":
		frappe.throw(_("Material Requests can only be created for Material type items"))

	if not row.item:
		frappe.throw(_("No inventory Item linked to this BOQ description"))

	# Quantity validation
	remaining = flt(row.planned_quantity) - flt(row.consumed_quantity)
	if qty > remaining and remaining > 0:
		if not frappe.has_permission("Bill of Quantities", ptype="submit"):
			frappe.throw(
				_("Requested quantity {0} exceeds remaining quantity {1}. "
				  "Excess requires approval from a higher role.").format(qty, remaining)
			)
		variation_excess = qty - remaining
		frappe.msgprint(
			_("Excess quantity {0} will be recorded as variation").format(variation_excess)
		)

	mr = frappe.new_doc("Material Request")
	mr.material_request_type = "Purchase"
	mr.schedule_date = nowdate()
	mr.boq = boq_name
	mr.append("items", {
		"item_code": row.item,
		"qty": qty,
		"uom": row.unit or frappe.db.get_value("Item", row.item, "stock_uom"),
		"schedule_date": nowdate(),
		"boq": boq_name,
		"boq_detail": child_docname,
	})
	mr.insert()

	frappe.msgprint(
		_("Material Request {0} created successfully").format(
			get_link_to_form("Material Request", mr.name)
		)
	)
	return mr.name
