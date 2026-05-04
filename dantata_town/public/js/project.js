frappe.ui.form.on("Project", {
	setup(frm) {
		frm.set_query("building_type", () => {
			if (!frm.doc.site) {
				return { filters: { name: ["in", []] } };
			}
			return {
				query: "dantata_town.dantata_town.project_aggregations.get_site_building_types",
				filters: { site: frm.doc.site },
			};
		});
	},

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

	customer(frm) {
		if (!frm.doc.customer) return;
		frappe.db.get_value("Customer", frm.doc.customer, "customer_name").then((r) => {
			const name = r?.message?.customer_name;
			if (name) frm.set_value("project_name", name);
		});
	},

	site(frm) {
		frm.set_value("building_type", null);
	},

	project_type(frm) {
		frm.set_value("project_subtype", null);
	},
});

// The Project quick-entry customization (field reorder, customer autofill,
// building_type filter) lives in public/js/project_quick_entry.js, which is
// loaded globally via app_include_js so it's available wherever quick-entry
// is triggered — not just the Project form view.
