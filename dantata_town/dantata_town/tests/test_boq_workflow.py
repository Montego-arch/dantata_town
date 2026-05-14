# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from dantata_town.dantata_town.setup import create_boq_custom_fields


WORKFLOW_NAME = "Bill of Quantities Approval"
ROLE_NAME = "BOQ Approver"


class TestBOQWorkflowInstalled(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()

	def test_role_created(self):
		self.assertTrue(frappe.db.exists("Role", ROLE_NAME))

	def test_workflow_created(self):
		self.assertTrue(frappe.db.exists("Workflow", WORKFLOW_NAME))
		wf = frappe.get_doc("Workflow", WORKFLOW_NAME)
		self.assertEqual(wf.document_type, "Bill of Quantities")
		self.assertEqual(wf.is_active, 1)
		state_names = {s.state for s in wf.states}
		self.assertEqual(
			state_names,
			{"Draft", "Pending Approval", "Approved", "Unlocked", "Rejected"},
		)

	def test_workflow_transitions(self):
		wf = frappe.get_doc("Workflow", WORKFLOW_NAME)
		transitions = {(t.state, t.action, t.next_state) for t in wf.transitions}
		expected = {
			("Draft", "Submit for Approval", "Pending Approval"),
			("Pending Approval", "Approve", "Approved"),
			("Pending Approval", "Reject", "Rejected"),
			("Rejected", "Re-open", "Draft"),
			("Unlocked", "Submit for Approval", "Pending Approval"),
		}
		self.assertEqual(transitions, expected)

	def test_approved_and_unlocked_doc_status(self):
		wf = frappe.get_doc("Workflow", WORKFLOW_NAME)
		approved = next(s for s in wf.states if s.state == "Approved")
		self.assertEqual(str(approved.doc_status), "1")
		# Unlocked is docstatus=0 — the custom unlock_boq_for_edit function
		# manipulates docstatus directly; there is no workflow transition into it.
		unlocked = next(s for s in wf.states if s.state == "Unlocked")
		self.assertEqual(str(unlocked.doc_status), "0")

	def test_existing_submitted_boqs_backfilled(self):
		"""After installer runs, any submitted BOQ with no workflow_state is set to Approved."""
		boq_name = frappe.get_all(
			"Bill of Quantities",
			filters={"docstatus": 1},
			limit=1,
			pluck="name",
		)
		if not boq_name:
			self.skipTest("No submitted BOQ to test backfill")
		frappe.db.set_value("Bill of Quantities", boq_name[0], "workflow_state", None, update_modified=False)
		create_boq_custom_fields()
		state = frappe.db.get_value("Bill of Quantities", boq_name[0], "workflow_state")
		self.assertEqual(state, "Approved")


class TestUnlockBOQ(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		# Ensure the test user has the role.
		role = "BOQ Approver"
		user_roles = frappe.get_roles()
		if role not in user_roles:
			# In test context we run as Administrator who has all roles.
			pass

	def test_unlock_function_reverts_docstatus(self):
		"""unlock_boq_for_edit must flip docstatus 1 → 0 and set workflow_state to Unlocked."""
		from dantata_town.dantata_town.bill_of_quantities_workflow import unlock_boq_for_edit

		# Find a submitted BOQ or skip.
		boq_name = frappe.get_all(
			"Bill of Quantities",
			filters={"docstatus": 1},
			limit=1,
			pluck="name",
		)
		if not boq_name:
			self.skipTest("No submitted BOQ available for unlock test")
		boq_name = boq_name[0]

		# Set it to Approved so the function accepts it.
		frappe.db.set_value(
			"Bill of Quantities", boq_name, "workflow_state", "Approved",
			update_modified=False,
		)
		unlock_boq_for_edit(boq_name)
		self.assertEqual(
			frappe.db.get_value("Bill of Quantities", boq_name, "docstatus"), 0
		)
		self.assertEqual(
			frappe.db.get_value("Bill of Quantities", boq_name, "workflow_state"),
			"Unlocked",
		)

		# Cleanup: restore the BOQ to its prior state so the suite stays clean.
		frappe.db.set_value(
			"Bill of Quantities", boq_name,
			{"docstatus": 1, "workflow_state": "Approved"},
			update_modified=False,
		)

	def test_unlock_rejects_unsubmitted_boq(self):
		from dantata_town.dantata_town.bill_of_quantities_workflow import unlock_boq_for_edit
		# A draft BOQ should be rejected.
		boq_name = frappe.get_all(
			"Bill of Quantities",
			filters={"docstatus": 0},
			limit=1,
			pluck="name",
		)
		if not boq_name:
			self.skipTest("No draft BOQ available")
		with self.assertRaises(frappe.ValidationError):
			unlock_boq_for_edit(boq_name[0])
