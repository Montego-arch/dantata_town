// Copyright (c) 2026, Montego-arch and contributors
// For license information, please see license.txt

frappe.ui.form.on("Site", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Create BOQ"), () => {
				frappe.new_doc("Bill of Quantities", {
					site: frm.doc.name,
					date: frappe.datetime.nowdate(),
				});
			});
		}
	},
});
