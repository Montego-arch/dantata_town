frappe.ui.form.on("Visitor Log", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || frm.doc.time_out) {
			return;
		}

		frm.add_custom_button(__("Check Out"), () => {
			frm.call("check_out").then(() => frm.reload_doc());
		});
	},
});
