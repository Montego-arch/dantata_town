# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from dantata_town.dantata_town.setup import create_boq_custom_fields

EXPECTED_SUBTYPES = {
	"Building": {"PLOT", "DPC", "CARCASS", "SHELL", "FINISHED"},
	"Infrastructure": {
		"Roads", "Drainages", "Kerbstone", "Water Reticulation", "Electrification",
	},
}


class TestProjectTypeSetup(FrappeTestCase):
	def test_seed_creates_types_and_subtypes(self):
		create_boq_custom_fields()

		for parent_type, subtypes in EXPECTED_SUBTYPES.items():
			self.assertTrue(
				frappe.db.exists("Project Type", parent_type),
				f"Project Type {parent_type} should exist",
			)
			actual = set(frappe.get_all(
				"Project Subtype",
				filters={"project_type": parent_type},
				pluck="name",
			))
			self.assertEqual(
				actual, subtypes,
				f"Subtypes for {parent_type} do not match",
			)

	def test_seed_is_idempotent(self):
		create_boq_custom_fields()
		first_count = frappe.db.count("Project Subtype")
		create_boq_custom_fields()
		second_count = frappe.db.count("Project Subtype")
		self.assertEqual(first_count, second_count)

	def test_project_subtype_custom_field_exists(self):
		create_boq_custom_fields()
		field = frappe.db.get_value(
			"Custom Field",
			{"dt": "Project", "fieldname": "project_subtype"},
			["fieldtype", "options", "depends_on", "link_filters"],
			as_dict=True,
		)
		self.assertIsNotNone(field, "project_subtype custom field not found on Project")
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "Project Subtype")
		self.assertEqual(field.depends_on, "eval:doc.project_type")
		self.assertEqual(
			field.link_filters,
			'[["Project Subtype","project_type","=","eval:doc.project_type"]]',
		)

	def test_project_type_is_required(self):
		create_boq_custom_fields()
		ps = frappe.db.get_value(
			"Property Setter",
			{"doc_type": "Project", "field_name": "project_type", "property": "reqd"},
			"value",
		)
		self.assertEqual(ps, "1")

	def test_validator_rejects_mismatched_subtype(self):
		create_boq_custom_fields()
		from dantata_town.dantata_town.utils import validate_project_subtype_matches_type
		doc = frappe._dict(project_type="Building", project_subtype="Roads")
		with self.assertRaises(frappe.ValidationError):
			validate_project_subtype_matches_type(doc)

	def test_validator_accepts_matching_subtype(self):
		create_boq_custom_fields()
		from dantata_town.dantata_town.utils import validate_project_subtype_matches_type
		doc = frappe._dict(project_type="Building", project_subtype="SHELL")
		try:
			validate_project_subtype_matches_type(doc)
		except frappe.ValidationError:
			self.fail("Validator rejected a valid Building/SHELL pair")

	def test_validator_accepts_empty_subtype(self):
		create_boq_custom_fields()
		from dantata_town.dantata_town.utils import validate_project_subtype_matches_type
		doc = frappe._dict(project_type="Building", project_subtype=None)
		try:
			validate_project_subtype_matches_type(doc)
		except frappe.ValidationError:
			self.fail("Validator rejected an empty subtype")
