# Project Type Refactor — Design Spec

**Date:** 2026-04-20
**App:** `dantata_town`
**Scope:** Introduce a two-level Project classification (Type + Subtype) aligned with Dantata Town Developers' internal reporting. This is the first piece of the Phase 2 customization; Allocation Letters, quotation installments, and monthly reports are out of scope here.

## Background

The client tracks work across two broad categories — **Building** and **Infrastructure** — each with its own progression/category breakdown. The classification already appears in the weekly field report (see `GARDEN REPORT APRIL WEEK 1.pdf`), but Frappe's standard `Project` doctype only ships with `Internal / External / Other` as Project Types and has no subtype concept.

## Goals

1. Make every Project classifiable as Building or Infrastructure.
2. Capture a second-level stage/category (e.g. `SHELL`, `Roads`) that is specific to the chosen type.
3. Keep existing ERPNext defaults (`Internal`, `External`, `Other`) available for projects that don't fit the new classification.
4. Match the existing `dantata_town` setup conventions — custom fields and property setters installed via `setup.py` from `after_install` / `after_migrate`.

## Non-goals

- Migrating existing projects (none reference `project_type` on the current site — clean slate).
- Reporting UI, dashboards, or printable documents that consume the new classification. Those arrive in later Phase 2 tickets.
- Touching Allocation Letters, installment quotations, or monthly reports.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Building subtypes: `PLOT, DPC, CARCASS, SHELL, FINISHED` | Matches the 5-stage progression in the Garden Report's "Status of Building Units" tables |
| 2 | Infrastructure subtypes: `Roads, Drainages, Kerbstone, Water Reticulation, Electrification` | Matches the 5 infrastructure categories tracked in the Garden Report |
| 3 | Subtype model: new `Project Subtype` doctype linked to `Project Type` | Lets admins add subtypes from the UI later without code changes; supports type- and subtype-level grouping for reports |
| 4 | `project_type` is required on Project; `project_subtype` is optional | Classification is mandatory; leaf granularity is not always applicable |
| 5 | Internal / External / Other are preserved | Building and Infrastructure are added alongside, not as replacements |
| 6 | Seed data lives in `setup.py` (not fixtures, not patches) | Matches how the app already bootstraps custom fields and property setters; idempotent re-run on every `after_migrate` |

## Architecture

Three moving parts:

1. **New doctype `Project Subtype`** in the Dantata Town module, keyed by its `subtype_name` and linked up to a `Project Type`.
2. **Custom field `project_subtype`** on `Project`, a `Link` to `Project Subtype` with `link_filters` that narrow the dropdown to subtypes of the selected Project Type.
3. **Property setter** making `Project.project_type` required, plus a validator that rejects a subtype whose parent type doesn't match the Project's type.

### Doctype `Project Subtype`

| Fieldname | Type | Notes |
|---|---|---|
| `subtype_name` | Data | Required, unique. `autoname: field:subtype_name` so the record name equals the label. |
| `project_type` | Link → Project Type | Required. Establishes the parent type. |

DocType options:

- `track_changes: 1`
- `quick_entry: 1`
- `allow_rename: 1`
- `sort_field: project_type`, `sort_order: ASC`
- `module: Dantata Town`

Permissions (mirrors stock `Project Type`):

- `System Manager` — full CRUD
- `Projects Manager` — full CRUD
- `Projects User` — read-only

### Custom field on `Project`

Installed via `create_custom_fields` in `setup.py`:

```python
"Project": [
    {
        "fieldname": "project_subtype",
        "fieldtype": "Link",
        "label": "Project Subtype",
        "options": "Project Subtype",
        "insert_after": "project_type",
        "depends_on": "eval:doc.project_type",
        "link_filters": '[["Project Subtype","project_type","=",doc.project_type]]',
        "module": "Dantata Town",
    },
]
```

### Property setter

```python
("Project", "project_type", "reqd", "1", "Check"),
```

Added alongside the existing `customer` property setters in `_create_property_setters()`.

### Seed data

New `_seed_project_types_and_subtypes()` helper called from `create_boq_custom_fields()`. Idempotent via `frappe.db.exists(...)` checks.

Project Types:

- `Building`
- `Infrastructure`

Project Subtypes:

| Subtype | Project Type |
|---|---|
| PLOT | Building |
| DPC | Building |
| CARCASS | Building |
| SHELL | Building |
| FINISHED | Building |
| Roads | Infrastructure |
| Drainages | Infrastructure |
| Kerbstone | Infrastructure |
| Water Reticulation | Infrastructure |
| Electrification | Infrastructure |

### Validation and client behavior

Server validator added to the existing `Project.validate` chain in `hooks.py`:

```python
doc_events = {
    "Project": {
        "validate": [
            "dantata_town.dantata_town.utils.validate_project_has_site",
            "dantata_town.dantata_town.utils.validate_project_subtype_matches_type",
        ],
        ...
    },
}
```

```python
# utils.py
def validate_project_subtype_matches_type(doc, method=None):
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

Client handler added to `public/js/project.js`:

```javascript
frappe.ui.form.on("Project", {
    refresh(frm) { /* existing BOQ button */ },
    project_type(frm) {
        frm.set_value("project_subtype", null);
    },
});
```

## Data Flow

1. User opens a new Project.
2. `project_type` is required — they must pick one of: Building, Infrastructure, Internal, External, Other.
3. If they pick Building or Infrastructure, the `project_subtype` field becomes visible (`depends_on`), and its dropdown is filtered by `link_filters` to subtypes of that type.
4. If they later switch `project_type`, `project_subtype` is auto-cleared by the JS handler so a stale selection can't survive.
5. On save, the server validator re-checks the subtype's parent type matches the project's type (defense in depth for API writes).

## Error Handling

- **Missing `project_type`:** standard Frappe required-field error from the property setter.
- **Subtype mismatch:** explicit `frappe.throw` from `validate_project_subtype_matches_type` with a human-readable message naming both values.
- **Deleted subtype referenced by a Project:** Frappe's built-in link validation prevents deletion if references exist, same as for any other Link field. No extra handling needed.

## Testing

### Unit tests (new `tests/test_project_type_setup.py`)

1. **Seed creates records.** Call `create_boq_custom_fields()`; assert `Building` and `Infrastructure` Project Types exist and all 10 subtypes exist with the correct `project_type`.
2. **Seed is idempotent.** Call it twice; count of types and subtypes is unchanged, no exceptions.
3. **Validator rejects mismatched subtype.** Project with `project_type="Building"` and `project_subtype="Roads"` raises `frappe.ValidationError`.
4. **Validator accepts matching subtype.** `Building` + `SHELL` saves.
5. **Validator accepts empty subtype.** `Building` with no subtype saves (decision 4).
6. **Link filter present.** The `project_subtype` custom field's `link_filters` value exactly matches the expected string.

### Manual smoke test

- `bench --site home.com migrate` completes without errors.
- New Project form:
  - Project Type dropdown lists Building, Infrastructure, Internal, External, Other. Field is marked required.
  - Selecting Building reveals Project Subtype with 5 options: PLOT, DPC, CARCASS, SHELL, FINISHED.
  - Switching to Infrastructure clears the subtype and now shows: Roads, Drainages, Kerbstone, Water Reticulation, Electrification.
  - Saving with matching type/subtype succeeds.
- Via backend/API, force a mismatch (e.g. via `frappe.db.set_value` to bypass the client) and save → rejected with the validation message.

## File-change summary

- **New:** `dantata_town/dantata_town/doctype/project_subtype/project_subtype.json` (+ `.py`, `__init__.py`)
- **New:** `dantata_town/dantata_town/tests/__init__.py`, `dantata_town/dantata_town/tests/test_project_type_setup.py`
- **Edit:** `dantata_town/dantata_town/setup.py` — add `project_subtype` to `_create_custom_fields`, add `project_type` reqd property setter, add `_seed_project_types_and_subtypes()`
- **Edit:** `dantata_town/dantata_town/utils.py` — add `validate_project_subtype_matches_type`
- **Edit:** `dantata_town/hooks.py` — extend `doc_events["Project"]["validate"]` to a list
- **Edit:** `dantata_town/public/js/project.js` — add `project_type` change handler
