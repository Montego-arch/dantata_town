# Site Template Data Field, Sellable Quantity, and Sales Order Amount Refresh

**Date:** 2026-05-22
**Scope:** Convert Site's per-row template_item to a free-text field that auto-creates Items, introduce a Sellable Quantity column with a Quotation-level cap, fix the Project's Sales Order Amount column so it updates on SO submit/cancel, and auto-link orphan SOs when a Project is created from a Site.

## Background

Phase 4 (shipped 2026-05-14) tightened the Project↔SO↔Payment↔BOQ chain. Two follow-up tweaks landed shortly after: notify on per-site Item auto-creation, and mirror `reserved_unit` to the per-site Item.

Field users have now surfaced four issues with day-to-day operation:

1. **Sales Order Amount never appears on the Project.** ERPNext's `Project.update_sales_amount()` only runs from `Project.validate()`. Submitting an SO does not re-save the Project, so the column stays at 0. Property setters in Phase 4 exposed and re-labeled the field but never wired a recompute trigger.
2. **Template Item Link field is friction.** Users want to type the name of a property type directly (e.g. "3-Bedroom Bungalow") rather than first creating an Item record and then picking it. The system should create the Item on save.
3. **No upstream cap on quotations.** SO save is capped against `(total_units - reserved_unit)`, but quotations can already over-promise the same units. Sales staff want the cap enforced one stage earlier.
4. **Project↔SO link gap.** Current workflow: users create the SO against a Site first, then create the Project from the Site dashboard. `SO.project` stays blank, so even with the recompute fix in (1) there is no path from the SO back to the new Project.

## Goals

- Replace `Project Unit Item.template_item` Link with a Data field, with on-save auto-creation of the per-site Item using hardcoded defaults.
- Add a stored `sellable_unit` column to `Project Unit Item`, computed as `unit - reserved_unit`, surfaced in the grid.
- Cap quotation qty per Site item against `sellable_unit`, summing draft + submitted quotations (cancelled excluded).
- Hook `Sales Order` `on_submit` / `on_cancel` into the project totals recompute so `total_sales_amount` reflects reality.
- Reposition `total_sales_amount` to the top of the existing Financials section on the Project form.
- When a Project is saved with a Site link, auto-link a single matching orphan SO if one exists; throw with a candidate list if more than one matches.

## Non-Goals

- Changing how `building_type` is derived (still auto-set from per-site Item).
- Per-site Item Group / warehouse configurability — defaults are hardcoded.
- Quotation cap enforcement after submit (e.g. amendments) — relies on Frappe's standard amendment flow producing a fresh doc that the cap re-validates.
- Manual Project↔SO relinking UX — `Auto-link on Project save` covers the documented flow; the "Manual link" and "Create Project from SO" alternatives were considered and dropped (see Decisions).

## Design

### 1. Schema: `Project Unit Item`

| Field            | Before              | After                                                 |
|------------------|---------------------|-------------------------------------------------------|
| `template_item`  | Link → Item, reqd   | **Data**, reqd, label "Template Item" (unchanged)     |
| `building_type`  | Link → Item, read_only | unchanged                                          |
| `unit`           | Float "Total Units" | unchanged                                             |
| `reserved_unit`  | Float "Reserved"    | unchanged                                             |
| `sellable_unit`  | —                   | **NEW** Float "Sellable", read_only, in_list_view, computed in `Site.calculate_totals()` |
| `uom`, `rate`, `amount` | —            | unchanged                                             |

Field order in the grid: `template_item, building_type, unit, reserved_unit, sellable_unit, [column break], uom, rate, amount`.

Bump the doctype `modified` timestamp so `bench migrate` re-imports the schema.

**Migration of existing data:** Frappe converting a Link field to Data preserves the stored string. Existing rows still hold the former Item code (e.g. `ITEM-001`); the per-site Item naming convention `{site} - {template_item}` continues to resolve to the already-existing per-site Item record. No data backfill required. The `if not frappe.db.exists` guard in `_ensure_per_site_items` keeps re-save idempotent.

### 2. Per-site Item auto-creation

In `dantata_town/dantata_town/doctype/site/site.py:_ensure_per_site_items`:

- Drop the `frappe.get_doc("Item", row.template_item)` + `frappe.copy_doc(template)` path entirely.
- Build `target_name = f"{self.site_name} - {row.template_item}"` from the typed string directly.
- If `target_name` doesn't exist as an Item, insert with these hardcoded defaults:

```python
new_item = frappe.new_doc("Item")
new_item.item_code = target_name
new_item.item_name = target_name
new_item.item_group = "PROPERTIES"
new_item.stock_uom = "Unit"
new_item.is_stock_item = 1
new_item.is_purchase_item = 1
new_item.is_sales_item = 1
new_item.grant_commission = 1
new_item.append("item_defaults", {
    "company": frappe.defaults.get_user_default("company") or frappe.db.get_single_value("Global Defaults", "default_company"),
    "default_warehouse": "Stores - DTD",
})
new_item.insert(ignore_permissions=True)
```

- After the `if not exists` block, the existing `row.building_type = target_name` + `frappe.db.set_value("Item", target_name, "reserved_unit", ...)` mirror logic is unchanged.
- Add a setup precondition check at the top of `_ensure_per_site_items`: if Item Group "PROPERTIES" or Warehouse "Stores - DTD" is missing, `frappe.throw` with a clear message naming the missing record. Avoids a generic "Could not find" failure deep in the Item insert.

### 3. Sellable Quantity (stored)

In `Site.calculate_totals`:

```python
for row in self.get("project_units") or []:
    row.amount = flt(row.unit) * flt(row.rate)
    row.sellable_unit = flt(row.unit) - flt(row.reserved_unit)
    total += flt(row.unit)
```

Stored (not virtual) so the Quotation validator can sum/join against `tabProject Unit Item.sellable_unit` directly. Recomputed every Site save.

### 4. Quotation cap

New file `dantata_town/dantata_town/quotation.py` (already exists for `validate_quotation_payment_type` — extend it).

```python
def check_sellable_cap(doc, method=None):
    """Block save when sum of qty across draft+submitted Quotation Items
    (excluding this Quotation) plus this Quotation's qty would exceed
    the Sellable cap on the matching Site row."""
    this_qty: dict[str, float] = {}
    for row in doc.items:
        this_qty[row.item_code] = this_qty.get(row.item_code, 0) + flt(row.qty)

    for item_code, qty_on_this in this_qty.items():
        site_row = frappe.db.sql("""
            SELECT parent AS site, sellable_unit
            FROM `tabProject Unit Item`
            WHERE parenttype = 'Site' AND building_type = %s
            LIMIT 1
        """, (item_code,), as_dict=True)
        if not site_row:
            continue
        cap = flt(site_row[0].sellable_unit)

        other = frappe.db.sql("""
            SELECT COALESCE(SUM(qi.qty), 0)
            FROM `tabQuotation Item` qi
            JOIN `tabQuotation` q ON q.name = qi.parent
            WHERE q.docstatus != 2
              AND q.name != %s
              AND qi.item_code = %s
        """, (doc.name or "", item_code))
        other_qty = flt(other[0][0] if other else 0)

        if (other_qty + qty_on_this) > cap:
            available = cap - other_qty
            frappe.throw(_(
                "Cannot quote {0} of {1}: only {2} sellable on {3} (already on other quotations: {4})."
            ).format(qty_on_this, item_code, available, site_row[0].site, other_qty))
```

Hook wiring (`hooks.py`):

```python
"Quotation": {
    "validate": [
        "dantata_town.dantata_town.quotation.validate_quotation_payment_type",
        "dantata_town.dantata_town.quotation.check_sellable_cap",
    ],
},
```

The SO-level `check_reservations` in `sales_order.py` is left untouched as a defense-in-depth check for SOs not derived from a quotation. Both checks use the same `(unit - reserved_unit) == sellable_unit` cap so they are consistent.

### 5. Sales Order Amount recompute

Extend `dantata_town/dantata_town/project_aggregations.py`:

```python
def recalc_project_totals(project):
    ...
    expenses = ...
    payment = ...
    sales = _sum_sales_orders(project)
    frappe.db.set_value("Project", project, {
        "project_expenses": expenses,
        "project_payment": payment,
        "total_sales_amount": sales,
    }, update_modified=False)

def _sum_sales_orders(project):
    rows = frappe.db.sql("""
        SELECT COALESCE(SUM(base_net_total), 0)
        FROM `tabSales Order`
        WHERE project = %s AND docstatus = 1
    """, (project,))
    return flt(rows[0][0]) if rows else 0
```

Extend `_projects_touched_by`:

```python
elif dt == "Sales Order":
    if doc.get("project"):
        projects.add(doc.project)
```

Hook (`hooks.py`):

```python
"Sales Order": {
    "before_validate": "dantata_town.dantata_town.sales_order.fetch_from_project",
    "validate": [
        "dantata_town.dantata_town.sales_order.enforce_one_so_per_project",
        "dantata_town.dantata_town.sales_order.check_reservations",
    ],
    "on_submit": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
    "on_cancel": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
},
```

**Reposition `total_sales_amount` to top of Financials** via property setter in `setup.py:_create_property_setters`:

```python
("Project", "total_sales_amount", "insert_after", "dt_financials_section", "Data"),
```

This puts it as the first field of the Financials section, above `project_expenses` in the left column.

**Backfill patch** at `dantata_town/patches/v1/recalc_sales_amount_for_existing_projects.py`:

```python
import frappe
from dantata_town.dantata_town.project_aggregations import recalc_project_totals

def execute():
    projects = frappe.db.sql_list("""
        SELECT DISTINCT project FROM `tabSales Order`
        WHERE docstatus = 1 AND IFNULL(project, '') != ''
    """)
    for p in projects:
        recalc_project_totals(p)
```

Register in `patches.txt`.

### 6. Auto-link orphan SOs on Project save

New module `dantata_town/dantata_town/project.py`:

```python
import frappe
from frappe import _
from dantata_town.dantata_town.project_aggregations import recalc_project_totals


def auto_link_orphan_sales_orders(doc, method=None):
    if not doc.site:
        return
    candidates = frappe.db.sql("""
        SELECT DISTINCT so.name
        FROM `tabSales Order` so
        JOIN `tabSales Order Item` soi ON soi.parent = so.name
        JOIN `tabProject Unit Item` pui
             ON pui.building_type = soi.item_code
            AND pui.parenttype = 'Site'
            AND pui.parent = %(site)s
        WHERE so.docstatus = 1
          AND (so.project IS NULL OR so.project = '')
    """, {"site": doc.site}, as_dict=True)

    if not candidates:
        return
    if len(candidates) > 1:
        names = ", ".join(c.name for c in candidates)
        frappe.throw(_(
            "Multiple unlinked Sales Orders match Site {0}: {1}. "
            "Open the correct one and set its Project field manually."
        ).format(doc.site, names))

    so_name = candidates[0].name
    frappe.db.set_value("Sales Order", so_name, "project", doc.name, update_modified=False)
    recalc_project_totals(doc.name)
    frappe.msgprint(
        _("Linked Sales Order {0} to this Project.").format(
            frappe.utils.get_link_to_form("Sales Order", so_name)
        ),
        alert=True, indicator="blue",
    )
```

Hook (`hooks.py` — extend existing Project entry):

```python
"Project": {
    "validate": [...existing two...],
    "on_update": "dantata_town.dantata_town.project.auto_link_orphan_sales_orders",
},
```

The function is idempotent: already-linked SOs are excluded by `so.project IS NULL`. `enforce_one_so_per_project` is bypassed by `db.set_value` here but is logically safe because the candidate query only matches SOs without any project assignment.

## Data Flow

```
1. User saves Site with project_units rows
   └─ Site.validate
      ├─ _ensure_per_site_items: typed template_item → per-site Item created (PROPERTIES, Unit, Stores - DTD)
      └─ calculate_totals: row.sellable_unit = unit - reserved_unit; total_units summed

2. User drafts Quotation citing per-site Items
   └─ Quotation.validate
      ├─ validate_quotation_payment_type
      └─ check_sellable_cap: sum(other non-cancelled Quotation Items) + this.qty <= sellable_unit

3. User submits Sales Order with Site items, project still blank
   └─ SO.validate: check_reservations (existing) caps against unit-reserved_unit
   └─ SO.on_submit: project_aggregations.recalc_for_doc
       └─ no-op: doc.project is empty, _projects_touched_by returns empty set

4. User creates Project from Site dashboard with site=X
   └─ Project.on_update: auto_link_orphan_sales_orders
       ├─ Find orphan SOs matching Site X
       ├─ If 1 → set SO.project = Project.name (db.set_value), call recalc_project_totals
       └─ Project.total_sales_amount, project_expenses, project_payment all refresh

5. Future amendments / payments
   └─ Existing PI/JE/PE/Expense Claim/Sales Order on_submit/on_cancel → recalc_project_totals
```

## Error Handling

| Scenario                                                   | Behavior                                                                                       |
|------------------------------------------------------------|------------------------------------------------------------------------------------------------|
| Item Group "PROPERTIES" missing                            | `frappe.throw` on Site save with setup hint                                                    |
| Warehouse "Stores - DTD" missing                           | `frappe.throw` on Site save with setup hint                                                    |
| Quotation qty would exceed Sellable                        | `frappe.throw` naming Site, item, available qty                                                |
| Multiple orphan SOs match Site on Project save             | `frappe.throw` listing candidates; user must link manually via SO form                         |
| Project saved with no Site link                            | `auto_link_orphan_sales_orders` no-ops silently                                                |
| Existing rows after migration (Link → Data)                | Strings preserved; per-site Items already exist; re-save is idempotent                         |

## Testing

### `tests/test_site_template_data.py` (new)

- Site with `template_item="3-Bedroom Bungalow"` (typed) → on save, Item `{site} - 3-Bedroom Bungalow` exists with `item_group=PROPERTIES`, `stock_uom=Unit`, `is_stock_item=1`, `is_purchase_item=1`, `is_sales_item=1`, `grant_commission=1`, `item_defaults[0].default_warehouse=Stores - DTD`.
- Idempotency: save the Site twice → exactly one Item exists.
- Missing "PROPERTIES" Item Group → `frappe.throw` (use `frappe.db.exists` monkeypatch or remove fixture).
- Legacy data: `template_item` already containing a former Item code (e.g. `ITEM-001`) → save resolves `{site} - ITEM-001` correctly without erroring.

### `tests/test_sellable_cap.py` (new)

- Site with `unit=10`, `reserved_unit=2` → after save `sellable_unit == 8`.
- Quotation A draft, qty=5 → saves.
- Quotation B draft, qty=4 → throws (5+4>8); message names the Site.
- Cancel A (docstatus=2) → B qty=4 now saves.
- Submit A (docstatus=1) → another draft qty=4 throws.
- Quotation with a non-site item → no error.

### Extend `tests/test_project_aggregations.py`

- Existing project + payment tests still pass (regression).
- Project with site, submit SO with `project=<Project>`, `base_net_total=1,000,000` → `Project.total_sales_amount == 1,000,000`.
- Cancel the SO → `total_sales_amount == 0`.
- **Auto-link case:** submit an SO against Site X with `project` blank; then create+save a Project with `site=X` → SO gets linked; Project total_sales_amount reflects SO.
- **Multi-orphan case:** two SOs against Site X with project blank; save Project for Site X → throws with both names.
- **No-orphan case:** orphan SO on Site A; save a Project for Site B → no link, no error.

### Manual smoke test (not automated)

1. Create Site "Block C" with one row `template_item="2-Bedroom Flat"`, unit=10, reserved=1.
2. Save → verify Item "Block C - 2-Bedroom Flat" auto-created with documented defaults; Sellable column shows 9.
3. Draft a Quotation for 5 units → saves. Try a second Quotation for 5 units → blocked at 9-cap.
4. Submit first Quotation, convert to Sales Order (project blank), submit SO.
5. From Site "Block C" dashboard, create new Project → on save, SO auto-links; open Project → Financials section shows Sales Order Amount at the top with the SO's base_net_total.

## Decisions / Alternatives Considered

| Decision                                                  | Chosen                                                       | Alternatives rejected                                                                       |
|-----------------------------------------------------------|--------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| Per-site Item naming                                      | `{site} - {typed}`                                           | Use typed name only globally (breaks per-site reservation model)                            |
| Item defaults source                                      | Hardcoded constants                                          | Designated template Item; UOM from row (user picked hardcoded)                              |
| Quotation cap scope                                       | Draft + Submitted (non-cancelled)                            | Submitted only; submitted + drafts only on same Site                                        |
| Sales Order Amount position                               | Top of Financials, left column                               | Right column above Project Payment; bottom of Financials                                    |
| SO↔Project link mechanism                                 | Auto-link on Project save                                    | Manual SO.project edit after submit; reverse the flow (create Project from SO)              |
| `sellable_unit` storage                                   | Stored field (computed in Site.calculate_totals)             | Virtual field (harder to SQL-join in Quotation cap)                                         |

## Setup Tasks (per `bench migrate`)

- `Project Unit Item` schema bumped (template_item → Data; sellable_unit added)
- `Item Group "PROPERTIES"` must exist (manual or seeded — added to install hint)
- `Warehouse "Stores - DTD"` must exist (manual — already in production)
- Property setter: `total_sales_amount.insert_after = dt_financials_section`
- Patch: `recalc_sales_amount_for_existing_projects` runs once
- Hooks added: Quotation.validate.check_sellable_cap, Sales Order.on_submit/on_cancel.recalc_for_doc, Project.on_update.auto_link_orphan_sales_orders

## Out of Scope

- Customer History doctype (still pending from Phase 2).
- Allowing per-Site overrides of Item defaults.
- Renaming/deleting per-site Items when the user edits `template_item` on an existing row (already an open concern pre-this-change).
