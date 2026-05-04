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

	site(frm) {
		frm.set_value("building_type", null);
	},

	project_type(frm) {
		frm.set_value("project_subtype", null);
	},
});
