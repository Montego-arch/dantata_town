### Dantata Town

Utility Application for Dantata Town Developers

## Overview

Dantata Town is a Frappe/ERPNext custom app for managing construction projects, with a focus on Bill of Quantities (BOQ) tracking, material procurement, and consumption monitoring across construction sites.

## Core Modules

### Site Management
- Create and manage construction sites with project units, expected timelines, and notes
- Each site serves as the starting point for BOQ creation
- Quick-action "Create BOQ" button on the Site form

### Bill of Quantities (BOQ)
- Linked to a Site and optionally to an ERPNext Project
- Supports up to 7 construction stages (e.g., Setting Out, Work Up to DPC, DPC to 1st Floor Slab, etc.)
- Each stage contains a table of BOQ Items with planned quantities, rates, and amounts
- Auto-calculated summary table breaking down Labour vs Material costs per stage
- Submittable document with amendment support

### BOQ Item Detail (Description Master)
- Master list of BOQ descriptions (e.g., "Trench for concrete foundation", "CEMENT", "Carpenter @ 5000 per day")
- Each description is classified as either **Labour** or **Material**
- Material descriptions must be linked to an ERPNext inventory Item
- Labour descriptions do not require an inventory Item mapping
- Unit of Measurement (UOM) is defined here and inherited by BOQ Items

### BOQ Items (Child Table)
- Line items within each BOQ stage
- **Planned fields**: description, unit, planned_quantity, rate, amount (auto-calculated)
- **Tracking fields**: consumed_quantity, remaining_quantity, variation_quantity, actual_quantity
- **Actual cost fields**: actual_rate, variation_rate, actual_amount
- **Create button**: Generates Material Requests directly from BOQ line items (Material type only)

## Key Workflows

### Material Request from BOQ
1. User clicks "Create" button on a Material-type BOQ Item row
2. System shows a dialog with item info and remaining quantity
3. Quantity validation checks requested qty against remaining (planned - consumed)
4. If qty exceeds remaining, higher-role approval is required
5. Material Request is created with traceability back to the BOQ via custom fields (`boq`, `boq_detail`) on Material Request Item

### Automatic Consumption Tracking
- **Purchase Receipt submission**: When a Purchase Receipt linked to a BOQ Material Request is submitted, the consumed_quantity on the BOQ Item row is automatically updated
- **Stock Entry (Material Transfer/Issue)**: When a Stock Entry linked to a BOQ Material Request is submitted, consumption is tracked automatically
- **Cancellation reversal**: Cancelling a Purchase Receipt or Stock Entry reverses the consumed quantity
- Remaining quantity, actual quantity, and actual amount are recalculated on each update

### Quantity Formulas
- `amount = planned_quantity x rate`
- `remaining_quantity = planned_quantity - consumed_quantity`
- `actual_quantity = consumed_quantity + variation_quantity`
- `actual_amount = consumed_quantity x actual_rate`

## DocType Reference

| DocType | Type | Purpose |
|---------|------|---------|
| Site | Document | Construction site master |
| Bill of Quantities | Submittable | BOQ with 7 stages and summary |
| BOQ Item Detail | Submittable | Description master (Labour/Material) |
| BOQ Items | Child Table | Line items in each BOQ stage |
| BOQ Summary Item | Child Table | Auto-calculated stage summary |
| Project Unit Item | Child Table | Site project unit definitions |

## Custom Fields (on ERPNext DocTypes)

| DocType | Field | Purpose |
|---------|-------|---------|
| Material Request Item | `boq` (Link) | Reference to Bill of Quantities |
| Material Request Item | `boq_detail` (Data, hidden) | Reference to specific BOQ Items row |

## Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app dantata_town
```

After installation, run `bench migrate` to create custom fields on ERPNext doctypes.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/dantata_town
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
