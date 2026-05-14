# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, today, add_days

from dantata_town.dantata_town.setup import create_boq_custom_fields
from dantata_town.dantata_town.project_aggregations import (
	recalc_project_totals,
	recalc_for_doc,
)


class TestProjectFinancialFields(FrappeTestCase):
	def test_building_type_field_exists_on_project(self):
		create_boq_custom_fields()
		field = frappe.db.get_value(
			"Custom Field",
			{"dt": "Project", "fieldname": "building_type"},
			["fieldtype", "options", "depends_on"],
			as_dict=True,
		)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "Item")
		self.assertEqual(field.depends_on, "eval:doc.site")

	def test_financials_fields_exist_on_project(self):
		create_boq_custom_fields()
		for fieldname, fieldtype in [
			("dt_financials_section", "Section Break"),
			("project_expenses", "Currency"),
			("dt_financials_col", "Column Break"),
			("project_payment", "Currency"),
		]:
			field = frappe.db.get_value(
				"Custom Field",
				{"dt": "Project", "fieldname": fieldname},
				["fieldtype", "read_only"],
				as_dict=True,
			)
			self.assertIsNotNone(field, f"{fieldname} not found")
			self.assertEqual(field.fieldtype, fieldtype)
			if fieldtype == "Currency":
				self.assertEqual(field.read_only, 1)

	def test_total_sales_amount_relabeled_and_unhidden(self):
		create_boq_custom_fields()
		label = frappe.db.get_value(
			"Property Setter",
			{"doc_type": "Project", "field_name": "total_sales_amount", "property": "label"},
			"value",
		)
		hidden = frappe.db.get_value(
			"Property Setter",
			{"doc_type": "Project", "field_name": "total_sales_amount", "property": "hidden"},
			"value",
		)
		self.assertEqual(label, "Sales Order Amount")
		self.assertEqual(hidden, "0")


def _ensure_company():
	"""Return the site's default Company name (or the first Company on the site)."""
	return frappe.db.get_single_value("Global Defaults", "default_company") \
		or frappe.db.get_value("Company", {}, "name")


def _expense_account(company):
	return frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Expense Account", "is_group": 0},
		"name",
	) or frappe.db.get_value(
		"Account", {"company": company, "is_group": 0, "root_type": "Expense"}, "name"
	)


def _receivable_account(company):
	return frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Receivable", "is_group": 0},
		"name",
	)


def _bank_account(company):
	return frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Bank", "is_group": 0},
		"name",
	) or frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Cash", "is_group": 0},
		"name",
	)


def _cost_center(company):
	return frappe.db.get_value(
		"Cost Center", {"company": company, "is_group": 0}, "name"
	)


def _business_segment():
	"""Return any Business Segment name, or None if the doctype doesn't exist / is empty."""
	if not frappe.db.table_exists("Business Segment"):
		return None
	return frappe.db.get_value("Business Segment", {}, "name")


def _make_site_and_project():
	"""Create a minimal Site + Project pair, return their names."""
	create_boq_custom_fields()
	from dantata_town.dantata_town.tests._helpers import get_test_expense_account
	uom = frappe.db.get_value("UOM", {}, "name")
	item = frappe.db.get_value("Item", {"disabled": 0, "is_sales_item": 1}, "name") \
	       or frappe.db.get_value("Item", {"disabled": 0}, "name")
	customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
	company = frappe.db.get_single_value("Global Defaults", "default_company")

	site = frappe.get_doc({
		"doctype": "Site",
		"site_name": f"AggSite-{frappe.generate_hash(length=6)}",
		"expense_account": get_test_expense_account(),
		"project_units": [{"building_type": item, "unit": 1, "uom": uom, "rate": 1}],
	}).insert(ignore_permissions=True)

	project = frappe.get_doc({
		"doctype": "Project",
		"project_name": f"AggProj-{frappe.generate_hash(length=6)}",
		"customer": customer,
		"company": company,
		"site": site.name,
		"project_type": "Building",
		"project_subtype": "PLOT",
	}).insert(ignore_permissions=True)
	return site.name, project.name


class TestRecalcProjectTotals(FrappeTestCase):
	def test_no_documents_yields_zero(self):
		_, project = _make_site_and_project()
		recalc_project_totals(project)
		expenses = frappe.db.get_value("Project", project, "project_expenses")
		payment = frappe.db.get_value("Project", project, "project_payment")
		self.assertEqual(expenses, 0)
		self.assertEqual(payment, 0)

	def test_unknown_project_is_noop(self):
		recalc_project_totals(None)  # must not raise
		recalc_project_totals("DOES-NOT-EXIST")  # must not raise; just a no-op or write to nothing


class TestProjectAggregationHooks(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()

	def _submit_purchase_invoice(self, project: str | None, amount: float = 1000) -> str:
		company = frappe.db.get_single_value("Global Defaults", "default_company")
		supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
		item = frappe.db.get_value("Item", {"is_purchase_item": 1, "disabled": 0}, "name") \
		       or frappe.db.get_value("Item", {"disabled": 0}, "name")
		credit_to = frappe.db.get_value(
			"Account", {"company": company, "account_type": "Payable", "is_group": 0}, "name"
		)
		expense_account = frappe.db.get_value(
			"Account",
			{"company": company, "root_type": "Expense", "account_type": "", "is_group": 0},
			"name",
		)
		cost_center = frappe.db.get_value(
			"Cost Center", {"company": company, "is_group": 0}, "name"
		)
		item_row = {
			"item_code": item,
			"qty": 1,
			"rate": amount,
			"expense_account": expense_account,
			"cost_center": cost_center,
		}
		if project:
			item_row["project"] = project
		pi = frappe.get_doc({
			"doctype": "Purchase Invoice",
			"company": company,
			"supplier": supplier,
			"posting_date": today(),
			"due_date": add_days(today(), 30),
			"bill_no": f"TEST-{frappe.generate_hash(length=6)}",
			"bill_date": today(),
			"credit_to": credit_to,
			"update_stock": 0,
			"items": [item_row],
		})
		pi.set_missing_values()
		pi.insert(ignore_permissions=True)
		pi.submit()
		return pi.name

	def test_purchase_invoice_submit_increases_project_expenses(self):
		_, project = _make_site_and_project()
		self._submit_purchase_invoice(project, amount=2500)
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_expenses")),
			2500,
		)

	def test_purchase_invoice_cancel_reverses_project_expenses(self):
		_, project = _make_site_and_project()
		pi_name = self._submit_purchase_invoice(project, amount=1500)
		pi = frappe.get_doc("Purchase Invoice", pi_name)
		pi.cancel()
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_expenses")),
			0,
		)

	def test_doc_with_no_project_is_noop(self):
		_, project = _make_site_and_project()
		# A PI without a project link must not affect the unrelated project's expenses.
		self._submit_purchase_invoice(project=None, amount=999)
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_expenses")),
			0,
		)

	# ------------------------------------------------------------------ #
	# Expense Claim tests
	# ------------------------------------------------------------------ #

	def _check_expense_claim_feasible(self):
		"""Skip the test if Expense Claim cannot be created on this site."""
		# Use the employee's own company to avoid department-mismatch validation errors.
		employee_row = frappe.db.get_value(
			"Employee", {"status": "Active"}, ["name", "company"], as_dict=True
		)
		if not employee_row:
			self.skipTest("No active Employee available; skipping Expense Claim test")
		# Check for mandatory custom fields whose linked doctypes don't exist on this site
		mandatory_custom = frappe.db.sql(
			"""select fieldname, options from `tabCustom Field`
			   where dt='Expense Claim' and reqd=1""",
			as_dict=True,
		)
		for cf in mandatory_custom:
			if cf.options and not frappe.db.table_exists(cf.options):
				self.skipTest(
					f"Expense Claim mandatory field '{cf.fieldname}' links to "
					f"'{cf.options}' which has no table on this site; skipping"
				)
		return employee_row

	def _submit_expense_claim(self, project: str, amount: float = 500) -> str:
		# Use the employee's own company to avoid department-mismatch validation errors.
		employee_row = self._check_expense_claim_feasible()
		employee = employee_row.name
		company = employee_row.company or _ensure_company()
		expense_account = _expense_account(company)
		cost_center = _cost_center(company)
		expense_type = frappe.db.get_value("Expense Claim Type", {}, "name") \
		               or frappe.get_doc({
		                   "doctype": "Expense Claim Type",
		                   "expense_type": "DT-Test",
		                   "accounts": [{"company": company, "default_account": expense_account}],
		               }).insert(ignore_permissions=True).name
		ec = frappe.get_doc({
			"doctype": "Expense Claim",
			"employee": employee,
			"company": company,
			"posting_date": today(),
			"approval_status": "Approved",
			"project": project,
			"payable_account": frappe.db.get_value(
				"Account", {"company": company, "account_type": "Payable", "is_group": 0}, "name"
			),
			"expenses": [{
				"expense_date": today(),
				"expense_type": expense_type,
				"description": "Test claim",
				"amount": amount,
				"sanctioned_amount": amount,
				"default_account": expense_account,
				"cost_center": cost_center,
			}],
		})
		ec.insert(ignore_permissions=True)
		ec.submit()
		return ec.name

	def test_expense_claim_submit_increases_project_expenses(self):
		_, project = _make_site_and_project()
		self._submit_expense_claim(project, amount=750)
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_expenses")),
			750,
		)

	def test_expense_claim_cancel_reverses(self):
		_, project = _make_site_and_project()
		ec_name = self._submit_expense_claim(project, amount=300)
		frappe.get_doc("Expense Claim", ec_name).cancel()
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_expenses")),
			0,
		)

	# ------------------------------------------------------------------ #
	# Journal Entry tests
	# ------------------------------------------------------------------ #

	def _submit_journal_entry(self, project: str, amount: float, side: str = "debit") -> str:
		"""side='debit' creates an expense JE; side='credit' creates a credit-to-receivable JE."""
		company = _ensure_company()
		expense_account = _expense_account(company)
		receivable = _receivable_account(company)
		bank = _bank_account(company)
		cost_center = _cost_center(company)
		business_segment = _business_segment()
		if side == "debit":
			accounts = [
				{"account": expense_account, "debit_in_account_currency": amount,
				 "project": project, "cost_center": cost_center},
				{"account": bank, "credit_in_account_currency": amount,
				 "cost_center": cost_center},
			]
		else:
			# credit to receivable on this project
			customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
			accounts = [
				{"account": receivable, "credit_in_account_currency": amount,
				 "project": project, "party_type": "Customer", "party": customer,
				 "cost_center": cost_center},
				{"account": bank, "debit_in_account_currency": amount,
				 "cost_center": cost_center},
			]
		je_doc = {
			"doctype": "Journal Entry",
			"voucher_type": "Journal Entry",
			"company": company,
			"posting_date": today(),
			"cost_center": cost_center,
			"accounts": accounts,
		}
		if business_segment:
			je_doc["business_segment"] = business_segment
		je = frappe.get_doc(je_doc)
		je.insert(ignore_permissions=True)
		je.submit()
		return je.name

	def test_journal_entry_debit_increases_project_expenses(self):
		_, project = _make_site_and_project()
		self._submit_journal_entry(project, 1200, side="debit")
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_expenses")),
			1200,
		)

	def test_journal_entry_credit_to_receivable_increases_project_payment(self):
		_, project = _make_site_and_project()
		self._submit_journal_entry(project, 800, side="credit")
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_payment")),
			800,
		)

	# ------------------------------------------------------------------ #
	# Payment Entry tests
	# ------------------------------------------------------------------ #

	def _ensure_field_sales_rep(self, company):
		"""Return a Field Sales Reps name, creating a test record if none exist."""
		existing = frappe.db.get_value("Field Sales Reps", {}, "name")
		if existing:
			return existing
		# Create a minimal test record
		fsr = frappe.get_doc({
			"doctype": "Field Sales Reps",
			"sales_rep_name": "DT-Test Sales Rep",
			"enabled": 1,
		})
		fsr.insert(ignore_permissions=True)
		return fsr.name

	def _submit_sales_invoice(self, project: str, amount: float = 1000) -> str:
		company = _ensure_company()
		customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
		item = frappe.db.get_value("Item", {"is_sales_item": 1, "disabled": 0}, "name") \
		       or frappe.db.get_value("Item", {"disabled": 0}, "name")
		si_doc = {
			"doctype": "Sales Invoice",
			"customer": customer,
			"company": company,
			"posting_date": today(),
			"due_date": add_days(today(), 30),
			"project": project,
			"debit_to": _receivable_account(company),
			"items": [{
				"item_code": item,
				"qty": 1,
				"rate": amount,
				"income_account": frappe.db.get_value(
					"Account",
					{"company": company, "account_type": "Income Account", "is_group": 0},
					"name",
				) or frappe.db.get_value(
					"Account",
					{"company": company, "root_type": "Income", "is_group": 0},
					"name",
				),
				"cost_center": _cost_center(company),
			}],
		}
		# Satisfy any mandatory custom field for Field Sales Reps
		if frappe.db.get_value(
			"Custom Field",
			{"dt": "Sales Invoice", "fieldname": "custom_sales_rep_id", "reqd": 1},
			"name",
		):
			si_doc["custom_sales_rep_id"] = self._ensure_field_sales_rep(company)
		si = frappe.get_doc(si_doc)
		si.set_missing_values()
		si.insert(ignore_permissions=True)
		si.submit()
		return si.name

	def _submit_payment_entry_against_si(self, si_name: str, amount: float) -> str:
		si = frappe.get_doc("Sales Invoice", si_name)
		company = si.company
		pe = frappe.get_doc({
			"doctype": "Payment Entry",
			"payment_type": "Receive",
			"company": company,
			"posting_date": today(),
			"party_type": "Customer",
			"party": si.customer,
			"paid_from": _receivable_account(company),
			"paid_to": _bank_account(company),
			"paid_amount": amount,
			"received_amount": amount,
			"references": [{
				"reference_doctype": "Sales Invoice",
				"reference_name": si.name,
				"allocated_amount": amount,
				"total_amount": si.grand_total,
				"outstanding_amount": si.outstanding_amount,
			}],
		})
		pe.set_missing_values()
		pe.insert(ignore_permissions=True)
		pe.submit()
		return pe.name

	def test_payment_entry_against_si_increases_project_payment(self):
		_, project = _make_site_and_project()
		si_name = self._submit_sales_invoice(project, amount=1000)
		self._submit_payment_entry_against_si(si_name, amount=1000)
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_payment")),
			1000,
		)

	def test_payment_entry_not_double_counted_when_both_paths_match(self):
		"""Regression test: if pe.project = X AND si.project = X, the allocated amount
		must contribute exactly once to project_payment."""
		_, project = _make_site_and_project()
		si_name = self._submit_sales_invoice(project, amount=2000)
		# ERPNext typically auto-populates pe.project from the SI when allocating;
		# check the actual PE after submit to ensure pe.project == project, then assert
		# the project_payment is 2000 (single contribution), not 4000 (doubled).
		pe_name = self._submit_payment_entry_against_si(si_name, amount=2000)
		pe = frappe.get_doc("Payment Entry", pe_name)
		# Sanity: if pe.project isn't already set to our project, force it by cancelling
		# and creating a fresh PE with the project field explicitly set.
		if pe.project != project:
			pe.cancel()
			# Re-open the SI so it has outstanding amount again
			frappe.db.set_value("Sales Invoice", si_name, "outstanding_amount", 2000, update_modified=False)
			si = frappe.get_doc("Sales Invoice", si_name)
			pe2 = frappe.get_doc({
				"doctype": "Payment Entry",
				"payment_type": "Receive",
				"company": pe.company,
				"posting_date": today(),
				"party_type": "Customer",
				"party": pe.party,
				"project": project,
				"paid_from": _receivable_account(pe.company),
				"paid_to": _bank_account(pe.company),
				"paid_amount": 2000,
				"received_amount": 2000,
				"references": [{
					"reference_doctype": "Sales Invoice",
					"reference_name": si_name,
					"allocated_amount": 2000,
					"total_amount": si.grand_total,
					"outstanding_amount": 2000,
				}],
			})
			pe2.set_missing_values()
			pe2.insert(ignore_permissions=True)
			pe2.submit()
		self.assertEqual(
			flt(frappe.db.get_value("Project", project, "project_payment")),
			2000,
		)

	# ------------------------------------------------------------------ #
	# Multi-project Purchase Invoice
	# ------------------------------------------------------------------ #

	def test_purchase_invoice_with_two_projects_updates_both(self):
		_, p1 = _make_site_and_project()
		_, p2 = _make_site_and_project()
		company = _ensure_company()
		supplier = frappe.db.get_value("Supplier", {"disabled": 0}, "name")
		item = frappe.db.get_value("Item", {"is_purchase_item": 1, "disabled": 0}, "name") \
		       or frappe.db.get_value("Item", {"disabled": 0}, "name")
		pi = frappe.get_doc({
			"doctype": "Purchase Invoice",
			"supplier": supplier,
			"company": company,
			"posting_date": today(),
			"due_date": add_days(today(), 30),
			"bill_no": frappe.generate_hash(length=6),
			"bill_date": today(),
			"credit_to": frappe.db.get_value(
				"Account", {"company": company, "account_type": "Payable", "is_group": 0}, "name"
			),
			"update_stock": 0,
			"items": [
				{"item_code": item, "qty": 1, "rate": 100, "project": p1,
				 "expense_account": _expense_account(company), "cost_center": _cost_center(company)},
				{"item_code": item, "qty": 1, "rate": 200, "project": p2,
				 "expense_account": _expense_account(company), "cost_center": _cost_center(company)},
			],
		})
		pi.set_missing_values()
		pi.insert(ignore_permissions=True)
		pi.submit()
		self.assertEqual(
			flt(frappe.db.get_value("Project", p1, "project_expenses")),
			100,
		)
		self.assertEqual(
			flt(frappe.db.get_value("Project", p2, "project_expenses")),
			200,
		)


class TestProjectCompletion(FrappeTestCase):
	def setUp(self):
		create_boq_custom_fields()
		self.company = frappe.db.get_single_value("Global Defaults", "default_company")

	def _make_boq(self, project_name, site_name, stage_rows):
		"""Build (do not submit) a BOQ with the given stage rows.

		`stage_rows` is a dict like {1: [{"completed": 1}], 2: [{"completed": 0}]}.
		Each entry's stage gets start/end dates set (so validate passes) and the
		given rows appended to the relevant child table.
		"""
		from dantata_town.dantata_town.boq_progress import STAGE_TABLES
		boq = frappe.new_doc("Bill of Quantities")
		boq.site = site_name
		boq.project = project_name
		boq.date = today()
		boq.naming_series = "BOQ-.YYYY.-.#####"
		for stage_no, rows in stage_rows.items():
			boq.set(f"stage_{stage_no}", f"Stage {stage_no}")
			boq.set(f"stage_{stage_no}_start_date", today())
			boq.set(f"stage_{stage_no}_end_date", add_days(today(), 7))
			for row in rows:
				# Each row needs at least an item_code to satisfy BOQ Items validation.
				if "item_code" not in row:
					row["item_code"] = frappe.db.get_value("Item", {"disabled": 0}, "name")
				boq.append(STAGE_TABLES[stage_no], row)
		boq.insert(ignore_permissions=True)
		return boq

	def test_completion_averages_active_stages_only(self):
		from dantata_town.dantata_town.project_aggregations import recalc_project_completion
		site, project = _make_site_and_project()
		boq = self._make_boq(
			project_name=project,
			site_name=site,
			stage_rows={
				1: [{"completed": 1}],
				2: [{"completed": 1}, {"completed": 0}],
			},
		)
		boq.submit()
		recalc_project_completion(project)
		value = frappe.db.get_value("Project", project, "project_completion_percent")
		# Active stages: 1 (100%), 2 (50%). Average = 75.
		self.assertEqual(flt(value), 75.0)

	def test_completion_zero_when_no_active_stages(self):
		from dantata_town.dantata_town.project_aggregations import recalc_project_completion
		site, project = _make_site_and_project()
		recalc_project_completion(project)
		value = frappe.db.get_value("Project", project, "project_completion_percent")
		self.assertEqual(flt(value), 0.0)

	def test_completion_two_boqs_equally_weighted(self):
		from dantata_town.dantata_town.project_aggregations import recalc_project_completion
		site, project = _make_site_and_project()
		boq_a = self._make_boq(project, site, {1: [{"completed": 1}]})  # 100%
		boq_b = self._make_boq(project, site, {1: [{"completed": 0}, {"completed": 0}]})  # 0%
		boq_a.submit()
		boq_b.submit()
		recalc_project_completion(project)
		value = frappe.db.get_value("Project", project, "project_completion_percent")
		# Avg of 100 and 0 = 50.
		self.assertEqual(flt(value), 50.0)

	def test_completion_recalculated_on_boq_save(self):
		"""Toggling stage rows on a saved BOQ should roll up the new % without explicit recalc call."""
		site, project = _make_site_and_project()
		boq = self._make_boq(project, site, {1: [{"completed": 0}]})
		boq.submit()
		# Initially 0% complete.
		value = frappe.db.get_value("Project", project, "project_completion_percent")
		self.assertEqual(flt(value), 0.0)
		# Now flip the completed checkbox on the single row, save, and expect 100%.
		boq.reload()
		boq.get("table_txao")[0].completed = 1
		boq.save()
		value = frappe.db.get_value("Project", project, "project_completion_percent")
		self.assertEqual(flt(value), 100.0)
