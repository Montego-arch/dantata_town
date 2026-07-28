# Visitor Log

**Date:** 2026-07-28
**Scope:** A `Visitor Log` doctype recording front-desk visitor traffic — who called, who they came to see, why, and when they arrived and left — with a check-out action and a dedicated front-desk role.

## Background

The signed Scope of Work names three custom-development deliverables. Objective 7 (CRM) lists a **Visitor Log Book** with the fields *Date, Address, Person to See, Purpose of Visit, Phone Number, Time In, Time Out*. It has not been built; the client raised it in correspondence on 2026-07-28 and is correct to.

The other two named deliverables (Customer History doctype, structured project folder system for drawings) remain outstanding and are out of scope here.

The SoW field list omits the visitor's name. A log recording an address and phone number for an unnamed person is not usable as a log book, so `visitor_name` is included. This is the deliverable's own evident intent, not added scope.

## Goals

- A standalone `Visitor Log` doctype in the Dantata Town module covering the seven SoW fields plus `visitor_name`.
- `time_in` stamped automatically at the moment the record is inserted.
- `time_out` written only by an explicit check-out action, never typed.
- A `Visitor Log User` role scoped to this doctype alone, able to log and correct but not delete.
- "Who is currently on site" answerable from the standard list view with no custom report.

## Non-Goals

- Visitor badge printing, pre-registration, or host notification.
- Linking a visit to a `Site`, `Project`, or `Customer`. Deliberately excluded to keep the build to the contracted seven fields; trivially added later.
- Visits spanning midnight. The SoW's Date + two Time fields cannot represent one.
- Recurring/repeat-visitor records. Each visit is an independent document; there is no Visitor master.

## Design

### 1. Doctype: `Visitor Log`

Module **Dantata Town**. Not submittable — a log book, not a transaction. `allow_rename: 0`, `track_changes: 1`, `autoname: "VLOG-.YYYY.-.#####"` (`naming_rule: "By \"Naming Series\" field"`, matching `Sub Contractor Payment Request`), `sort_field: "modified"`, `sort_order: "DESC"`.

| Field | Type | Attributes |
|---|---|---|
| `section_break_visitor` | Section Break | label "Visitor" |
| `visitor_name` | Data | reqd, `in_list_view` |
| `phone_number` | Data | `options: "Phone"`, reqd, `in_list_view` |
| `address` | Small Text | label "Address" |
| `column_break_visitor` | Column Break | |
| `date` | Date | reqd, `default: "Today"`, `in_list_view` |
| `person_to_see` | Link → `Employee` | reqd, `in_list_view`, `in_standard_filter` |
| `purpose_of_visit` | Small Text | reqd |
| `section_break_times` | Section Break | label "Visit Times" |
| `time_in` | Time | reqd, `read_only: 1`, `in_list_view` |
| `column_break_times` | Column Break | |
| `time_out` | Time | `read_only: 1`, `in_list_view` |

`person_to_see` links to `Employee`, which ships with HRMS. HRMS is installed on this bench (`sites/apps.txt`), so the link resolves. A visit to someone who is not an Employee record cannot be logged — accepted, in exchange for reportable traffic per staff member.

Both time fields are `read_only`; neither is ever typed. See §2.

### 2. Check-in and check-out

`dantata_town/dantata_town/doctype/visitor_log/visitor_log.py`:

- **`before_insert`** — set `time_in = frappe.utils.nowtime()` when unset. A form-level default is set when the form opens and drifts if the front desk is slow; the insert stamp cannot.
- **`validate`** — if `time_out` is set and is earlier than `time_in`, `frappe.throw`.
- **`check_out()`**, `@frappe.whitelist()` on the Document — throws if `time_out` is already set, otherwise sets `time_out = nowtime()` and saves. This is the only path that writes `time_out`.

`dantata_town/public/js/visitor_log.js` adds a **Check Out** button in `refresh`, shown only when `!frm.is_new() && !frm.doc.time_out`; it calls the method and reloads. Registered in `hooks.py` under the existing `doctype_js` map.

Visitors currently on site are the list view filtered on *Time Out is not set*. No report, no code.

### 3. Permissions and setup

Permissions declared in the doctype JSON:

| Role | read | write | create | delete | export/print/report/share/email |
|---|---|---|---|---|---|
| System Manager | ✓ | ✓ | ✓ | ✓ | ✓ |
| Visitor Log User | ✓ | ✓ | ✓ | — | ✓ |

No delete for the front desk: a logged visit can be corrected but not erased.

`_create_visitor_log_role()` in `dantata_town/dantata_town/setup.py` inserts the `Role` when absent (`desk_access: 1`), mirroring the existing `BOQ Approver` creation in `_create_boq_workflow`. It is called from `create_boq_custom_fields()`, the orchestrator already wired to both `after_install` and `after_migrate`. Assigning the role to users is an administrative step, not code.

### 4. Tests

`dantata_town/dantata_town/tests/test_visitor_log.py`, `FrappeTestCase` against the bench DB. No mocks — the doctype has no external boundary. One test per outcome:

1. Inserting a log stamps `time_in` and leaves `time_out` empty.
2. `check_out()` sets `time_out`.
3. `check_out()` on an already-checked-out visit raises.
4. Saving with `time_out` earlier than `time_in` raises.

`dantata_town/dantata_town/tests/_helpers.py` currently exposes `get_test_expense_account()` and `ensure_site_preconditions()` — no Employee fixture. Add `ensure_test_employee()` there, returning an idempotent `Employee` (first name, gender, date of birth, date of joining, company) for the tests to point `person_to_see` at.

## Decisions

| Decision | Alternatives rejected | Reason |
|---|---|---|
| `person_to_see` as Link → Employee | Plain Data; Link plus free-text fallback | Reportable traffic per staff member and no name-spelling drift. The fallback field was dropped as two fields plus a validation rule for a case that has not been reported. |
| `time_in` auto, `time_out` by button | Both typed by hand; two Datetime fields | Accurate stamps without relying on staff, and an unclosed log is visible in the list. Datetimes would handle midnight crossings but abandon the SoW's named field shape. |
| Dedicated `Visitor Log User` role | Reuse System Manager / Projects User | Least privilege. The front desk has no business editing project data, and Projects Users have none editing the visitor log. |
| Seven SoW fields, no Site link | Optional Link → Site | The deliverable is contracted and late; per-site reporting is unbilled scope. Additive later if asked. |
| Include `visitor_name` | Ship the literal seven fields | Without it the record cannot identify the visitor, defeating the deliverable. |

## Files

**New**
- `dantata_town/dantata_town/doctype/visitor_log/__init__.py`
- `dantata_town/dantata_town/doctype/visitor_log/visitor_log.json`
- `dantata_town/dantata_town/doctype/visitor_log/visitor_log.py`
- `dantata_town/public/js/visitor_log.js`
- `dantata_town/dantata_town/tests/test_visitor_log.py`

**Modified**
- `dantata_town/hooks.py` — `doctype_js["Visitor Log"]`
- `dantata_town/dantata_town/setup.py` — `_create_visitor_log_role()` plus its call in `create_boq_custom_fields()`
- `dantata_town/dantata_town/tests/_helpers.py` — `ensure_test_employee()`
