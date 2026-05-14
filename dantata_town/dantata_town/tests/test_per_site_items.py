# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from dantata_town.dantata_town.setup import create_boq_custom_fields


class TestProjectUnitItemSchema(FrappeTestCase):
	def test_template_item_field_exists(self):
		meta = frappe.get_meta("Project Unit Item")
		fieldnames = {f.fieldname for f in meta.fields}
		self.assertIn("template_item", fieldnames)
		template = next(f for f in meta.fields if f.fieldname == "template_item")
		self.assertEqual(template.fieldtype, "Link")
		self.assertEqual(template.options, "Item")
		self.assertEqual(template.reqd, 1)

	def test_reserved_unit_field_exists(self):
		meta = frappe.get_meta("Project Unit Item")
		fieldnames = {f.fieldname for f in meta.fields}
		self.assertIn("reserved_unit", fieldnames)
		reserved = next(f for f in meta.fields if f.fieldname == "reserved_unit")
		self.assertEqual(reserved.fieldtype, "Float")

	def test_building_type_is_read_only(self):
		meta = frappe.get_meta("Project Unit Item")
		bt = next(f for f in meta.fields if f.fieldname == "building_type")
		self.assertEqual(bt.read_only, 1)

	def test_unit_label_is_total_units(self):
		meta = frappe.get_meta("Project Unit Item")
		unit_field = next(f for f in meta.fields if f.fieldname == "unit")
		self.assertEqual(unit_field.label, "Total Units")
