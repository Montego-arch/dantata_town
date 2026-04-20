# Project Type Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-level Project classification (Type + Subtype) to the `dantata_town` app, seeded with Building/Infrastructure and their stage/category subtypes from the Garden Report.

**Architecture:** New `Project Subtype` doctype links up to the stock `Project Type`. A `project_subtype` Link custom field on `Project` is filtered via `link_filters` to subtypes of the selected type. Seed data, custom fields, property setters, and validators are all installed via the existing `setup.py` `after_install`/`after_migrate` hook, matching the pattern already used for BOQ/Site custom fields.

**Tech Stack:** Frappe Framework, ERPNext (Project doctype), Python 3 (server), JavaScript (client form scripts), `FrappeTestCase` for tests.

**Spec:** `docs/superpowers/specs/2026-04-20-project-type-refactor-design.md`

**Working directory:** `/home/okeke/clients/graceco/frappe-bench/apps/dantata_town`

**Test command:** `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_project_type_setup`

**Migrate command:** `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`

---

## File Structure

**Files created:**

| Path | Responsibility |
|---|---|
| `dantata_town/dantata_town/doctype/project_subtype/project_subtype.json` | DocType definition |
| `dantata_town/dantata_town/doctype/project_subtype/project_subtype.py` | DocType controller (empty for now) |
| `dantata_town/dantata_town/doctype/project_subtype/__init__.py` | Package marker |
| `dantata_town/dantata_town/doctype/project_subtype/test_project_subtype.py` | Optional per-doctype test stub |
| `dantata_town/dantata_town/tests/__init__.py` | Package marker for app-level tests |
| `dantata_town/dantata_town/tests/test_project_type_setup.py` | Tests for seeding, custom field, validator |

**Files modified:**

| Path | Change |
|---|---|
| `dantata_town/dantata_town/setup.py` | Add `project_subtype` custom field, `project_type` reqd property setter, `_seed_project_types_and_subtypes()` helper |
| `dantata_town/dantata_town/utils.py` | Add `validate_project_subtype_matches_type` |
| `dantata_town/hooks.py` | Turn `doc_events["Project"]["validate"]` into a list of both validators |
| `dantata_town/public/js/project.js` | Add `project_type` change handler that clears `project_subtype` |

---

## Task 1: Create the `Project Subtype` doctype

**Files:**
- Create: `dantata_town/dantata_town/doctype/project_subtype/project_subtype.json`
- Create: `dantata_town/dantata_town/doctype/project_subtype/project_subtype.py`
- Create: `dantata_town/dantata_town/doctype/project_subtype/__init__.py`
- Create: `dantata_town/dantata_town/doctype/project_subtype/test_project_subtype.py`

- [ ] **Step 1: Create the package marker**

File: `dantata_town/dantata_town/doctype/project_subtype/__init__.py`

```python
```

(empty file)

- [ ] **Step 2: Create the DocType JSON**

File: `dantata_town/dantata_town/doctype/project_subtype/project_subtype.json`

```json
{
 "actions": [],
 "allow_rename": 1,
 "autoname": "field:subtype_name",
 "creation": "2026-04-20 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "subtype_name",
  "project_type"
 ],
 "fields": [
  {
   "fieldname": "subtype_name",
   "fieldtype": "Data",
   "in_list_view": 1,
   "label": "Subtype Name",
   "reqd": 1,
   "unique": 1
  },
  {
   "fieldname": "project_type",
   "fieldtype": "Link",
   "in_list_view": 1,
   "in_standard_filter": 1,
   "label": "Project Type",
   "options": "Project Type",
   "reqd": 1
  }
 ],
 "index_web_pages_for_search": 1,
 "links": [],
 "modified": "2026-04-20 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Dantata Town",
 "name": "Project Subtype",
 "naming_rule": "By fieldname",
 "owner": "Administrator",
 "permissions": [
  {
   "create": 1,
   "delete": 1,
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "System Manager",
   "share": 1,
   "write": 1
  },
  {
   "create": 1,
   "delete": 1,
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "Projects Manager",
   "share": 1,
   "write": 1
  },
  {
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "Projects User",
   "share": 1
  }
 ],
 "quick_entry": 1,
 "row_format": "Dynamic",
 "sort_field": "project_type",
 "sort_order": "ASC",
 "states": [],
 "track_changes": 1
}
```

- [ ] **Step 3: Create the DocType controller**

File: `dantata_town/dantata_town/doctype/project_subtype/project_subtype.py`

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

from frappe.model.document import Document


class ProjectSubtype(Document):
	pass
```

- [ ] **Step 4: Create the doctype test stub**

File: `dantata_town/dantata_town/doctype/project_subtype/test_project_subtype.py`

```python
# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase


class TestProjectSubtype(FrappeTestCase):
	pass
```

- [ ] **Step 5: Run migrate so Frappe picks up the new DocType**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`
Expected: Migration completes without errors. Output includes a line like `Creating DocType... Project Subtype`.

- [ ] **Step 6: Verify the DocType exists**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com execute frappe.client.get --kwargs "{'doctype':'DocType','name':'Project Subtype'}"`
Expected: JSON output with `"name": "Project Subtype"` and the two fields present.

- [ ] **Step 7: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/doctype/project_subtype/
git commit -m "feat: add Project Subtype doctype"
```

---

## Task 2: Seed Project Types and Subtypes on install/migrate

**Files:**
- Create: `dantata_town/dantata_town/tests/__init__.py`
- Create: `dantata_town/dantata_town/tests/test_project_type_setup.py`
- Modify: `dantata_town/dantata_town/setup.py`

- [ ] **Step 1: Create the tests package marker**

File: `dantata_town/dantata_town/tests/__init__.py`

```python
```

(empty file)

- [ ] **Step 2: Write the failing test for seed data**

File: `dantata_town/dantata_town/tests/test_project_type_setup.py`

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_project_type_setup`
Expected: Both tests FAIL. `test_seed_creates_types_and_subtypes` fails because Building/Infrastructure don't exist yet.

- [ ] **Step 4: Implement the seed helper in setup.py**

File: `dantata_town/dantata_town/setup.py`

Replace the entire file contents with:

```python
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


PROJECT_TYPE_SEED = {
	"Building": ["PLOT", "DPC", "CARCASS", "SHELL", "FINISHED"],
	"Infrastructure": [
		"Roads", "Drainages", "Kerbstone", "Water Reticulation", "Electrification",
	],
}


def create_boq_custom_fields():
	"""Create custom fields on ERPNext doctypes for BOQ and Site traceability,
	and seed Dantata Town project classification data."""
	_create_custom_fields()
	_create_property_setters()
	_cleanup_broken_project_links()
	_seed_project_types_and_subtypes()


def _create_custom_fields():
	custom_fields = {
		"Material Request": [
			{
				"fieldname": "boq",
				"fieldtype": "Link",
				"label": "Bill of Quantities",
				"options": "Bill of Quantities",
				"insert_after": "material_request_type",
				"read_only": 1,
				"reqd": 1,
				"module": "Dantata Town",
			},
		],
		"Material Request Item": [
			{
				"fieldname": "boq",
				"fieldtype": "Link",
				"label": "Bill of Quantities",
				"options": "Bill of Quantities",
				"insert_after": "project",
				"read_only": 1,
				"module": "Dantata Town",
			},
			{
				"fieldname": "boq_detail",
				"fieldtype": "Data",
				"label": "BOQ Detail Reference",
				"insert_after": "boq",
				"hidden": 1,
				"read_only": 1,
				"module": "Dantata Town",
			},
		],
		"Project": [
			{
				"fieldname": "site",
				"fieldtype": "Link",
				"label": "Site",
				"options": "Site",
				"insert_after": "project_name",
				"read_only": 1,
				"reqd": 1,
				"module": "Dantata Town",
			},
		],
	}
	create_custom_fields(custom_fields, update=True)


def _create_property_setters():
	"""Set customer as mandatory and allow in quick entry on Project."""
	property_setters = [
		("Project", "customer", "reqd", "1", "Check"),
		("Project", "customer", "allow_in_quick_entry", "1", "Check"),
	]
	for doctype, fieldname, prop, value, prop_type in property_setters:
		frappe.make_property_setter({
			"doctype": doctype,
			"fieldname": fieldname,
			"property": prop,
			"value": value,
			"property_type": prop_type,
		}, is_system_generated=False)


def _cleanup_broken_project_links():
	"""Remove any broken DocType Links on Project for Site."""
	for link in frappe.get_all("DocType Link", filters={
		"parent": "Project",
		"link_doctype": "Site",
	}, pluck="name"):
		frappe.delete_doc("DocType Link", link, force=True)
	frappe.clear_cache(doctype="Project")


def _seed_project_types_and_subtypes():
	"""Seed the Building/Infrastructure types and their subtypes.

	Idempotent: existing Internal/External/Other are never touched.
	"""
	for project_type, subtypes in PROJECT_TYPE_SEED.items():
		if not frappe.db.exists("Project Type", project_type):
			frappe.get_doc({
				"doctype": "Project Type",
				"project_type": project_type,
			}).insert(ignore_permissions=True)

		for subtype in subtypes:
			if not frappe.db.exists("Project Subtype", subtype):
				frappe.get_doc({
					"doctype": "Project Subtype",
					"subtype_name": subtype,
					"project_type": project_type,
				}).insert(ignore_permissions=True)
```

- [ ] **Step 5: Run tests again to verify they pass**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_project_type_setup`
Expected: Both tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/setup.py dantata_town/dantata_town/tests/
git commit -m "feat: seed Building/Infrastructure project types and subtypes"
```

---

## Task 3: Add `project_subtype` custom field and require `project_type`

**Files:**
- Modify: `dantata_town/dantata_town/setup.py`
- Modify: `dantata_town/dantata_town/tests/test_project_type_setup.py`

- [ ] **Step 1: Add failing tests for the custom field and property setter**

Append to `dantata_town/dantata_town/tests/test_project_type_setup.py` inside `TestProjectTypeSetup`:

```python
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
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_project_type_setup`
Expected: `test_project_subtype_custom_field_exists` FAILS (field not found) and `test_project_type_is_required` FAILS (property setter missing).

- [ ] **Step 3: Add the custom field and property setter in `setup.py`**

In `dantata_town/dantata_town/setup.py`:

1. Inside the `"Project"` list in `_create_custom_fields()`, after the existing `site` entry and before the closing `]`, append:

```python
			{
				"fieldname": "project_subtype",
				"fieldtype": "Link",
				"label": "Project Subtype",
				"options": "Project Subtype",
				"insert_after": "project_type",
				"depends_on": "eval:doc.project_type",
				"link_filters": '[["Project Subtype","project_type","=","eval:doc.project_type"]]',
				"module": "Dantata Town",
			},
```

2. In `_create_property_setters()`, add one entry to the `property_setters` list:

```python
		("Project", "project_type", "reqd", "1", "Check"),
```

So the list becomes:

```python
	property_setters = [
		("Project", "customer", "reqd", "1", "Check"),
		("Project", "customer", "allow_in_quick_entry", "1", "Check"),
		("Project", "project_type", "reqd", "1", "Check"),
	]
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_project_type_setup`
Expected: All four tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/setup.py dantata_town/dantata_town/tests/test_project_type_setup.py
git commit -m "feat: add project_subtype custom field and require project_type"
```

---

## Task 4: Add server validator for subtype/type consistency

**Files:**
- Modify: `dantata_town/dantata_town/utils.py`
- Modify: `dantata_town/hooks.py`
- Modify: `dantata_town/dantata_town/tests/test_project_type_setup.py`

- [ ] **Step 1: Write failing tests for the validator**

Append to `dantata_town/dantata_town/tests/test_project_type_setup.py` inside `TestProjectTypeSetup`:

```python
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
```

These tests exercise the validator in isolation using `frappe._dict` (a dict with attribute access), so no Site/Company fixtures are needed — the validator only reads `project_type` and `project_subtype`.

- [ ] **Step 2: Run tests — the three validator tests should fail on import**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_project_type_setup`
Expected: `ImportError: cannot import name 'validate_project_subtype_matches_type' from 'dantata_town.dantata_town.utils'`.

- [ ] **Step 3: Add the validator in `utils.py`**

In `dantata_town/dantata_town/utils.py`, append after `validate_project_has_site`:

```python
def validate_project_subtype_matches_type(doc, method=None):
	"""Reject a Project whose subtype belongs to a different parent type."""
	if not doc.project_subtype:
		return
	parent_type = frappe.db.get_value(
		"Project Subtype", doc.project_subtype, "project_type"
	)
	if parent_type != doc.project_type:
		frappe.throw(_(
			"Project Subtype {0} does not belong to Project Type {1}"
		).format(doc.project_subtype, doc.project_type))
```

- [ ] **Step 4: Wire the validator into `hooks.py`**

In `dantata_town/hooks.py`, replace the `"Project"` entry in `doc_events` with:

```python
	"Project": {
		"validate": [
			"dantata_town.dantata_town.utils.validate_project_has_site",
			"dantata_town.dantata_town.utils.validate_project_subtype_matches_type",
		],
	},
```

(Frappe supports a list of dotted paths for a single event. Leave the other entries — `Purchase Receipt` and `Stock Entry` — untouched.)

- [ ] **Step 5: Run tests to verify all pass**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_project_type_setup`
Expected: All seven tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/dantata_town/utils.py dantata_town/hooks.py dantata_town/dantata_town/tests/test_project_type_setup.py
git commit -m "feat: validate project subtype belongs to selected project type"
```

---

## Task 5: Clear subtype on type change (client-side UX)

**Files:**
- Modify: `dantata_town/public/js/project.js`

- [ ] **Step 1: Replace the contents of `project.js`**

File: `dantata_town/public/js/project.js`

```javascript
frappe.ui.form.on("Project", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.site) {
			frm.add_custom_button(__("Create BOQ"), () => {
				frappe.new_doc("Bill of Quantities", {
					site: frm.doc.site,
					project: frm.doc.name,
				});
			});
		}
	},

	project_type(frm) {
		frm.set_value("project_subtype", null);
	},
});
```

- [ ] **Step 2: Clear the asset cache so the browser picks up the new JS**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com clear-cache && bench build --app dantata_town`
Expected: Build finishes without errors.

- [ ] **Step 3: Commit**

```bash
cd /home/okeke/clients/graceco/frappe-bench/apps/dantata_town
git add dantata_town/public/js/project.js
git commit -m "feat: clear project_subtype when project_type changes"
```

---

## Task 6: Full migration + manual smoke test

**Files:** none (verification only)

- [ ] **Step 1: Run a full migrate against the target site**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com migrate`
Expected: Migration completes cleanly. Watch for any message about failed patches or custom field creation errors.

- [ ] **Step 2: Verify seed data exists in the database**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com execute frappe.client.get_list --kwargs "{'doctype':'Project Type','fields':['name']}"`
Expected: Output includes `Building`, `Infrastructure`, `Internal`, `External`, `Other`.

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com execute frappe.client.get_list --kwargs "{'doctype':'Project Subtype','fields':['name','project_type'],'limit_page_length':20}"`
Expected: 10 entries — 5 under Building (`PLOT, DPC, CARCASS, SHELL, FINISHED`) and 5 under Infrastructure (`Roads, Drainages, Kerbstone, Water Reticulation, Electrification`).

- [ ] **Step 3: Run the full test module one more time**

Run: `cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com run-tests --app dantata_town --module dantata_town.dantata_town.tests.test_project_type_setup`
Expected: All seven tests PASS.

- [ ] **Step 4: Manual browser smoke test**

Open the site in a browser, navigate to `/app/project/new`, and verify:

1. Project Type dropdown lists: `Building, External, Infrastructure, Internal, Other`. Field is marked required (asterisk).
2. Pick `Building`. A new Project Subtype field appears below it. Dropdown shows exactly: `CARCASS, DPC, FINISHED, PLOT, SHELL`.
3. Pick `SHELL`. Save the project (with a Site). Save succeeds.
4. Open the saved project, change Project Type to `Infrastructure`. The Project Subtype field clears automatically. Dropdown now shows: `Drainages, Electrification, Kerbstone, Roads, Water Reticulation`.
5. Pick `Roads`, save. Save succeeds.

- [ ] **Step 5: Manual API-level mismatch test**

Run (this simulates a write that bypasses the client):

```bash
cd /home/okeke/clients/graceco/frappe-bench && bench --site home.com execute frappe.client.set_value --kwargs "{'doctype':'Project','name':'<the project you just saved>','fieldname':'project_subtype','value':'PLOT'}"
```

Replace `<the project you just saved>` with the actual project name (e.g. `PROJ-0004`).

Expected: The call fails with `ValidationError: Project Subtype PLOT does not belong to Project Type Infrastructure`.

- [ ] **Step 6: Final commit if any trailing fixes were needed; otherwise stop**

If any manual test failed and required a follow-up change, commit it with a descriptive message. Otherwise, the work is complete — no additional commit needed.
