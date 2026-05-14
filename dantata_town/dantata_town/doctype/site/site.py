# Copyright (c) 2026, Montego-arch and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class Site(Document):
	def validate(self):
		self._ensure_per_site_items()
		self.calculate_totals()

	def before_rename(self, old, new, merge=False):
		frappe.throw(_(
			"Site renaming is blocked because per-site Items embed the Site name. "
			"Create a new Site instead and migrate data manually if needed."
		))

	def on_trash(self):
		# Block delete if any per-site Item is referenced on a submitted SO.
		item_codes = [row.building_type for row in (self.project_units or []) if row.building_type]
		if not item_codes:
			return
		referenced = frappe.db.sql(
			"""
			select distinct soi.item_code
			from `tabSales Order Item` soi
			join `tabSales Order` so on so.name = soi.parent
			where so.docstatus = 1 and soi.item_code in %(items)s
			""",
			{"items": tuple(item_codes)},
		)
		if referenced:
			items = ", ".join(r[0] for r in referenced)
			frappe.throw(_(
				"Cannot delete Site: per-site Items still referenced on submitted Sales Orders: {0}"
			).format(items))

	def _ensure_per_site_items(self):
		"""For each project_units row, ensure a per-site Item exists and link it."""
		for row in self.get("project_units") or []:
			if not row.template_item:
				continue
			template = frappe.get_doc("Item", row.template_item)
			target_name = f"{self.site_name} - {template.item_name}"
			if not frappe.db.exists("Item", target_name):
				new_item = frappe.copy_doc(template)
				new_item.item_code = target_name
				new_item.item_name = target_name
				# Drop company-specific defaults to avoid warehouse/company mismatch errors.
				new_item.set("item_defaults", [])
				new_item.insert(ignore_permissions=True)
			row.building_type = target_name

	def calculate_totals(self):
		total = 0
		for row in self.get("project_units") or []:
			row.amount = flt(row.unit) * flt(row.rate)
			total += flt(row.unit)
		self.total_units = total
