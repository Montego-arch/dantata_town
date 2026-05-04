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
	"""Surface Sub Contractor Payment Request on the BOQ connections dashboard."""
	data["transactions"].append({
		"label": _("Sub Contractor"),
		"items": ["Sub Contractor Payment Request"],
	})

	return data
