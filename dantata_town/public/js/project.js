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
