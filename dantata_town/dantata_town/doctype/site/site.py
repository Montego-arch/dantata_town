# Copyright (c) 2026, Montego-arch and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


PER_SITE_ITEM_GROUP = "PROPERTIES"
PER_SITE_STOCK_UOM = "Unit"
PER_SITE_DEFAULT_WAREHOUSE = "Stores - DTD"


class Site(Document):
	def validate(self):
		self._check_setup_preconditions()
		self._ensure_per_site_items()
		self.calculate_totals()

	def before_rename(self, old, new, merge=False):
		frappe.throw(_(
			"Site renaming is blocked because per-site Items embed the Site name. "
			"Create a new Site instead and migrate data manually if needed."
		))

	def on_trash(self):
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

	def _check_setup_preconditions(self):
		"""Surface a clear error if hardcoded defaults for per-site Item creation
		are missing, instead of letting Frappe throw a generic link-broken error
		deep inside Item.insert()."""
		if not self.get("project_units"):
			return
		if not frappe.db.exists("Item Group", PER_SITE_ITEM_GROUP):
			frappe.throw(_(
				"Item Group '{0}' must exist before saving a Site with project_units. "
				"Create it under Stock > Item Group."
			).format(PER_SITE_ITEM_GROUP))
		if not frappe.db.exists("UOM", PER_SITE_STOCK_UOM):
			frappe.throw(_(
				"UOM '{0}' must exist before saving a Site with project_units."
			).format(PER_SITE_STOCK_UOM))

	def _resolve_default_warehouse(self, company):
		"""Return the warehouse to use in item_defaults for *company*.

		Preference order:
		1. The canonical production warehouse PER_SITE_DEFAULT_WAREHOUSE ("Stores - DTD")
		   if it exists and belongs to *company*.
		2. Any warehouse named "Stores" that belongs to *company* (ERPNext convention).
		3. None — do not set a warehouse; ERPNext will leave it blank.

		We must not let ERPNext auto-fill from Stock Settings because the Stock
		Settings default_warehouse may belong to a different company, which
		triggers a validation error.
		"""
		if frappe.db.exists("Warehouse", PER_SITE_DEFAULT_WAREHOUSE):
			wh_company = frappe.db.get_value("Warehouse", PER_SITE_DEFAULT_WAREHOUSE, "company")
			if wh_company == company:
				return PER_SITE_DEFAULT_WAREHOUSE
		# Fall back: look for a "Stores" warehouse belonging to this company.
		stores_wh = frappe.db.get_value(
			"Warehouse",
			{"warehouse_name": "Stores", "company": company},
			"name",
		)
		return stores_wh or None

	def _ensure_per_site_items(self):
		"""For each project_units row, ensure a per-site Item exists and link it.

		`template_item` is now a Data field — the typed string becomes part of the
		per-site Item name directly. No template Item lookup is performed.
		"""
		default_company = frappe.db.get_single_value("Global Defaults", "default_company")
		default_warehouse = self._resolve_default_warehouse(default_company)
		for row in self.get("project_units") or []:
			if not row.template_item:
				continue
			target_name = f"{self.site_name} - {row.template_item}"
			if not frappe.db.exists("Item", target_name):
				new_item = frappe.new_doc("Item")
				new_item.item_code = target_name
				new_item.item_name = target_name
				new_item.item_group = PER_SITE_ITEM_GROUP
				new_item.stock_uom = PER_SITE_STOCK_UOM
				new_item.is_stock_item = 1
				new_item.is_purchase_item = 1
				new_item.is_sales_item = 1
				new_item.grant_commission = 1
				defaults_row = {"company": default_company}
				if default_warehouse:
					defaults_row["default_warehouse"] = default_warehouse
				new_item.append("item_defaults", defaults_row)
				new_item.insert(ignore_permissions=True)
				frappe.msgprint(
					_("Created Item: {0}").format(
						frappe.utils.get_link_to_form("Item", target_name)
					),
					alert=True,
					indicator="blue",
				)
			row.building_type = target_name
			frappe.db.set_value(
				"Item", target_name, "reserved_unit", flt(row.reserved_unit),
				update_modified=False,
			)

	def calculate_totals(self):
		total = 0
		for row in self.get("project_units") or []:
			row.amount = flt(row.unit) * flt(row.rate)
			row.sellable_unit = flt(row.unit) - flt(row.reserved_unit)
			total += flt(row.unit)
		self.total_units = total
