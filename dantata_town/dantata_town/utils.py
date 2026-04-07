import frappe
from frappe import _
from frappe.utils import flt


def validate_project_has_site(doc, method):
	"""Block Project creation without a Site."""
	if not doc.site:
		frappe.throw(
			_("A Project cannot be created without a Site. "
			  "Please create the Project from a Site record.")
		)


def update_boq_consumed_qty(doc, method):
	"""Called on Purchase Receipt submit.
	Traces: PR Item -> MR Item -> BOQ detail.
	"""
	for item in doc.items:
		boq, boq_detail = _get_boq_reference_from_pr_item(item)
		if boq and boq_detail:
			_update_consumed_quantity(boq, boq_detail, flt(item.qty))


def reverse_boq_consumed_qty(doc, method):
	"""Called on Purchase Receipt cancel."""
	for item in doc.items:
		boq, boq_detail = _get_boq_reference_from_pr_item(item)
		if boq and boq_detail:
			_update_consumed_quantity(boq, boq_detail, -flt(item.qty))


def update_boq_consumed_qty_from_stock_entry(doc, method):
	"""Called on Stock Entry submit (Material Transfer type)."""
	if doc.stock_entry_type not in ("Material Transfer", "Material Issue"):
		return

	for item in doc.items:
		boq, boq_detail = _get_boq_reference_from_se_item(item)
		if boq and boq_detail:
			_update_consumed_quantity(boq, boq_detail, flt(item.qty))


def reverse_boq_consumed_qty_from_stock_entry(doc, method):
	"""Called on Stock Entry cancel."""
	if doc.stock_entry_type not in ("Material Transfer", "Material Issue"):
		return

	for item in doc.items:
		boq, boq_detail = _get_boq_reference_from_se_item(item)
		if boq and boq_detail:
			_update_consumed_quantity(boq, boq_detail, -flt(item.qty))


def _get_boq_reference_from_pr_item(pr_item):
	"""Trace from PR Item back to BOQ via Material Request."""
	if not pr_item.material_request or not pr_item.material_request_item:
		return None, None

	return _get_boq_from_mr_item(pr_item.material_request_item)


def _get_boq_reference_from_se_item(se_item):
	"""Trace from Stock Entry Item back to BOQ via Material Request."""
	if not se_item.material_request or not se_item.material_request_item:
		return None, None

	return _get_boq_from_mr_item(se_item.material_request_item)


def _get_boq_from_mr_item(mr_item_name):
	"""Get BOQ reference from a Material Request Item."""
	mr_item = frappe.db.get_value(
		"Material Request Item",
		mr_item_name,
		["boq", "boq_detail"],
		as_dict=True,
	)
	if mr_item and mr_item.boq and mr_item.boq_detail:
		return mr_item.boq, mr_item.boq_detail
	return None, None


def _update_consumed_quantity(boq_name, boq_detail_name, qty_delta):
	"""Update consumed_quantity on a specific BOQ Items child row."""
	current = frappe.db.get_value(
		"BOQ Items",
		boq_detail_name,
		["consumed_quantity", "planned_quantity", "variation_quantity", "actual_rate"],
		as_dict=True,
	)
	if not current:
		return

	new_consumed = flt(current.consumed_quantity) + flt(qty_delta)

	frappe.db.set_value("BOQ Items", boq_detail_name, {
		"consumed_quantity": new_consumed,
		"remaining_quantity": flt(current.planned_quantity) - new_consumed,
		"actual_quantity": new_consumed + flt(current.variation_quantity),
		"actual_amount": new_consumed * flt(current.actual_rate),
	})
