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
