// Customizes the Project quick-entry dialog. Loaded via `app_include_js` so
// it's available wherever quick-entry is triggered (list view, link dialogs,
// etc.) — `doctype_js` would only load on the form view.
//
// - Reorders so Customer appears before Project Name (selecting a customer
//   auto-fills project_name).
// - Wires the customer → project_name autofill directly on the dialog field
//   (frappe.ui.form.on events don't fire inside quick-entry dialogs).
// - Filters the Building Type list by the selected Site (the form-level
//   set_query in project.js doesn't reach the quick-entry dialog).

frappe.provide("frappe.ui.form");

frappe.ui.form.ProjectQuickEntryForm = class ProjectQuickEntryForm extends frappe.ui.form.QuickEntryForm {
	set_meta_and_mandatory_fields() {
		super.set_meta_and_mandatory_fields();
		const fields = this.mandatory;
		const customer_idx = fields.findIndex((f) => f.fieldname === "customer");
		const project_name_idx = fields.findIndex((f) => f.fieldname === "project_name");
		if (customer_idx > -1 && project_name_idx > -1 && customer_idx > project_name_idx) {
			const [customer] = fields.splice(customer_idx, 1);
			fields.splice(project_name_idx, 0, customer);
		}
	}

	render_dialog() {
		super.render_dialog();

		const bt = this.dialog.fields_dict.building_type;
		if (bt) {
			bt.get_query = () => {
				const site = this.dialog.get_value("site");
				if (!site) return { filters: { name: ["in", []] } };
				return {
					query: "dantata_town.dantata_town.project_aggregations.get_site_building_types",
					filters: { site },
				};
			};
		}

		const customer_field = this.dialog.fields_dict.customer;
		if (customer_field) {
			customer_field.df.onchange = async () => {
				const customer = this.dialog.get_value("customer");
				if (!customer) return;
				const r = await frappe.db.get_value("Customer", customer, "customer_name");
				const name = r?.message?.customer_name;
				if (name) this.dialog.set_value("project_name", name);
			};
		}
	}
};
