# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, add_days, today

from dantata_town.dantata_town.setup import create_boq_custom_fields
from dantata_town.dantata_town.boq_progress import (
	STAGE_TABLES,
	validate_stage_dates,
	recalc_boq_progress,
)


class TestBOQStageFieldsInstalled(FrappeTestCase):
	def test_completed_checkbox_on_boq_items(self):
		create_boq_custom_fields()
		field = frappe.db.get_value(
			"Custom Field",
			{"dt": "BOQ Items", "fieldname": "completed"},
			["fieldtype", "allow_on_submit", "in_list_view"],
			as_dict=True,
		)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Check")
		self.assertEqual(field.allow_on_submit, 1)
		self.assertEqual(field.in_list_view, 1)

	def test_per_stage_fields_exist(self):
		create_boq_custom_fields()
		for stage in range(1, 16):
			# All 5 are allow_on_submit=1: dates so the user can edit them
			# post-submit; duration/progress/status so server-computed updates
			# can persist on the auto-save fired by toggling line-item completed.
			for suffix, fieldtype, expect_allow_on_submit in [
				("start_date", "Date", 1),
				("end_date", "Date", 1),
				("duration", "Int", 1),
				("progress", "Percent", 1),
				("status", "Data", 1),
			]:
				fieldname = f"stage_{stage}_{suffix}"
				field = frappe.db.get_value(
					"Custom Field",
					{"dt": "Bill of Quantities", "fieldname": fieldname},
					["fieldtype", "read_only", "allow_on_submit"],
					as_dict=True,
				)
				self.assertIsNotNone(field, f"{fieldname} missing")
				self.assertEqual(field.fieldtype, fieldtype, fieldname)
				if suffix in ("duration", "progress", "status"):
					self.assertEqual(field.read_only, 1, fieldname)
				if expect_allow_on_submit:
					self.assertEqual(field.allow_on_submit, 1, fieldname)


def _make_site():
	create_boq_custom_fields()
	from dantata_town.dantata_town.tests._helpers import get_test_expense_account
	uom = frappe.db.get_value("UOM", {}, "name")
	# template_item is now required; building_type is auto-populated by Site.validate.
	template_item = frappe.db.get_value("Item", {"disabled": 0, "has_variants": 0}, "name") \
		or frappe.db.get_value("Item", {"disabled": 0}, "name")
	site = frappe.get_doc({
		"doctype": "Site",
		"site_name": f"BOQSite-{frappe.generate_hash(length=6)}",
		"expense_account": get_test_expense_account(),
		"project_units": [{"template_item": template_item, "unit": 1, "uom": uom, "rate": 1}],
	}).insert(ignore_permissions=True)
	return site.name


def _detail_name():
	"""Return a BOQ Item Detail name to use as `description`. Create one if none exist."""
	existing = frappe.db.get_value("BOQ Item Detail", {}, "name")
	if existing:
		return existing
	return frappe.get_doc({
		"doctype": "BOQ Item Detail",
		"description": f"Detail-{frappe.generate_hash(length=6)}",
		"description_type": "Material",
		"unit": "Nos",
	}).insert(ignore_permissions=True).name


def _make_project(site):
	"""Create a fresh Project linked to the given site."""
	return frappe.get_doc({
		"doctype": "Project",
		"project_name": f"P-{frappe.generate_hash(length=6)}",
		"customer": frappe.db.get_value("Customer", {"disabled": 0}, "name"),
		"site": site,
		"project_type": "Building",
		"project_subtype": "PLOT",
	}).insert(ignore_permissions=True).name


class TestRecalcBOQProgress(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()

	def _new_boq(self, stage_rows: dict[int, list[dict]]) -> "frappe.model.document.Document":
		"""Build an in-memory BOQ doc with the given stage_no -> list-of-row-dicts.

		Always creates a fresh Site + Project pair so tests stay isolated.
		"""
		site = _make_site()
		project = _make_project(site)

		doc = frappe.new_doc("Bill of Quantities")
		doc.site = site
		doc.project = project
		doc.date = today()
		for stage_no, rows in stage_rows.items():
			table = STAGE_TABLES[stage_no]
			for row in rows:
				doc.append(table, {"description": _detail_name(), **row})
		return doc

	def test_empty_stage_progress_is_zero(self):
		doc = self._new_boq({})
		recalc_boq_progress(doc)
		for stage_no in STAGE_TABLES:
			self.assertEqual(doc.get(f"stage_{stage_no}_progress"), 0)
			self.assertEqual(doc.get(f"stage_{stage_no}_status"), "")

	def test_one_of_four_checked_yields_25(self):
		doc = self._new_boq({1: [
			{"completed": 0, "planned_quantity": 1, "rate": 1},
			{"completed": 1, "planned_quantity": 1, "rate": 1},
			{"completed": 0, "planned_quantity": 1, "rate": 1},
			{"completed": 0, "planned_quantity": 1, "rate": 1},
		]})
		recalc_boq_progress(doc)
		self.assertEqual(flt(doc.stage_1_progress), 25)
		self.assertEqual(doc.stage_1_status, "")

	def test_all_checked_yields_100_and_completed(self):
		doc = self._new_boq({2: [
			{"completed": 1, "planned_quantity": 1, "rate": 1},
			{"completed": 1, "planned_quantity": 1, "rate": 1},
		]})
		recalc_boq_progress(doc)
		self.assertEqual(flt(doc.stage_2_progress), 100)
		self.assertEqual(doc.stage_2_status, "Completed")

	def test_duration_computed_from_dates(self):
		doc = self._new_boq({3: [{"completed": 0, "planned_quantity": 1, "rate": 1}]})
		doc.stage_3_start_date = today()
		doc.stage_3_end_date = add_days(today(), 10)
		recalc_boq_progress(doc)
		self.assertEqual(doc.stage_3_duration, 10)


class TestValidateStageDates(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()

	def test_empty_stage_does_not_require_dates(self):
		site = _make_site()
		doc = frappe.new_doc("Bill of Quantities")
		doc.site = site
		doc.project = _make_project(site)
		doc.date = today()
		# No rows in any stage; should not raise.
		validate_stage_dates(doc)

	def test_stage_with_items_requires_both_dates(self):
		site = _make_site()
		doc = frappe.new_doc("Bill of Quantities")
		doc.site = site
		doc.project = _make_project(site)
		doc.date = today()
		doc.append("table_txao", {
			"description": _detail_name(),
			"planned_quantity": 1,
			"rate": 1,
		})
		with self.assertRaises(frappe.ValidationError):
			validate_stage_dates(doc)

	def test_end_before_start_raises(self):
		site = _make_site()
		doc = frappe.new_doc("Bill of Quantities")
		doc.site = site
		doc.project = _make_project(site)
		doc.date = today()
		doc.append("table_txao", {
			"description": _detail_name(),
			"planned_quantity": 1,
			"rate": 1,
		})
		doc.stage_1_start_date = today()
		doc.stage_1_end_date = add_days(today(), -2)
		with self.assertRaises(frappe.ValidationError):
			validate_stage_dates(doc)


class TestStageTables(FrappeTestCase):
	def test_stage_tables_covers_1_to_15(self):
		"""STAGE_TABLES must include 15 stages with consistent fieldname pattern."""
		self.assertEqual(set(STAGE_TABLES.keys()), set(range(1, 16)))
		# Stages 2-15 should follow the `descriptionN` naming convention.
		# Stage 1 keeps the legacy `table_txao` for backward compat.
		self.assertEqual(STAGE_TABLES[1], "table_txao")
		for n in range(2, 16):
			self.assertEqual(STAGE_TABLES[n], f"description{n}")


class TestSummaryProgress(FrappeTestCase):
	"""The Overall Summary table should mirror each stage's progress %."""

	def setUp(self):
		create_boq_custom_fields()
		from dantata_town.dantata_town.tests.test_project_aggregations import _make_site_and_project
		site, project = _make_site_and_project()
		self.site = site
		self.project = project
		self.item = frappe.db.get_value("Item", {"disabled": 0}, "name")

	def test_boq_summary_item_has_progress_field(self):
		meta = frappe.get_meta("BOQ Summary Item")
		fieldnames = {f.fieldname for f in meta.fields}
		self.assertIn("progress", fieldnames)
		progress = next(f for f in meta.fields if f.fieldname == "progress")
		self.assertEqual(progress.fieldtype, "Percent")
		self.assertEqual(progress.read_only, 1)

	def test_overall_summary_row_carries_stage_progress(self):
		boq = frappe.new_doc("Bill of Quantities")
		boq.site = self.site
		boq.project = self.project
		boq.date = today()
		boq.naming_series = "BOQ-.YYYY.-.#####"
		boq.set("stage_1", "Foundations")
		boq.set("stage_1_start_date", today())
		boq.set("stage_1_end_date", add_days(today(), 7))
		boq.append("table_txao", {
			"description_type": "Material",
			"item": self.item,
			"planned_quantity": 10,
			"rate": 100,
			"completed": 1,
		})
		boq.set("stage_2", "Walls")
		boq.set("stage_2_start_date", today())
		boq.set("stage_2_end_date", add_days(today(), 7))
		boq.append("description2", {
			"description_type": "Material",
			"item": self.item,
			"planned_quantity": 5,
			"rate": 50,
			"completed": 0,
		})
		boq.append("description2", {
			"description_type": "Material",
			"item": self.item,
			"planned_quantity": 3,
			"rate": 40,
			"completed": 1,
		})
		boq.insert(ignore_permissions=True)
		# Stage 1: 1/1 = 100%. Stage 2: 1/2 = 50%.
		stages_in_summary = {row.stage: flt(row.progress) for row in boq.summary}
		self.assertEqual(stages_in_summary.get("Foundations"), 100.0)
		self.assertEqual(stages_in_summary.get("Walls"), 50.0)
