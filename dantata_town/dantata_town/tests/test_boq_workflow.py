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
			("Approved", "Unlock for Edit", "Unlocked"),
			# Frappe blocks 1→0 docstatus transitions, so Unlocked goes back to
			# Approved directly (Re-approve) instead of back through Pending.
			("Unlocked", "Re-approve", "Approved"),
		}
		self.assertEqual(transitions, expected)

	def test_approved_and_unlocked_doc_status(self):
		wf = frappe.get_doc("Workflow", WORKFLOW_NAME)
		approved = next(s for s in wf.states if s.state == "Approved")
		self.assertEqual(str(approved.doc_status), "1")
		# Frappe blocks doc_status=1 → doc_status=0 transitions, so Unlocked
		# keeps doc_status=1 (still submitted) with allow_edit granting BOQ
		# Approver the right to modify the document.
		unlocked = next(s for s in wf.states if s.state == "Unlocked")
		self.assertEqual(str(unlocked.doc_status), "1")

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
