# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, add_days, today

from dantata_town.dantata_town.setup import create_boq_custom_fields


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
		for stage in range(1, 8):
			for suffix, fieldtype, expect_allow_on_submit in [
				("start_date", "Date", 1),
				("end_date", "Date", 1),
				("duration", "Int", 0),
				("progress", "Percent", 0),
				("status", "Data", 0),
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
