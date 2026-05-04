from frappe import _


def get_project_dashboard_data(data):
	"""Add Site to Project's connections/dashboard."""
	data.setdefault("internal_links", {})["Site"] = "site"

	data["transactions"].append({
		"label": _("Site"),
		"items": ["Site"],
	})

	return data


def get_sales_order_dashboard_data(data):
	"""Add Allocation Letter to Sales Order's connections/dashboard."""
	data["transactions"].append({
		"label": _("Allocation"),
		"items": ["Allocation Letter"],
	})

	return data


def get_bill_of_quantities_dashboard_data(data):
	"""Surface Sub Contractor Payment Request on the BOQ connections dashboard.

	Frappe normally auto-detects the link field by looking for a field named after
	the parent's snake_case (`bill_of_quantities`). The SCPR field is `boq`, so we
	register it via `non_standard_fieldnames` — without this the connection card
	shows but the count badge stays blank.
	"""
	data["transactions"].append({
		"label": _("Sub Contractor"),
		"items": ["Sub Contractor Payment Request"],
	})
	data.setdefault("non_standard_fieldnames", {})[
		"Sub Contractor Payment Request"
	] = "boq"

	return data
