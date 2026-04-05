// Copyright (c) 2026, Montego-arch and contributors
// For license information, please see license.txt

frappe.ui.form.on("BOQ Item Detail", {
	refresh(frm) {
		frm.toggle_reqd("item", frm.doc.description_type === "Material");
	},

	description_type(frm) {
		frm.toggle_reqd("item", frm.doc.description_type === "Material");
		if (frm.doc.description_type === "Labour") {
			frm.set_value("item", "");
			frm.set_value("item_name", "");
		}
	},
});
