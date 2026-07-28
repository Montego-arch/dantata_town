frappe.ui.form.on("Visitor Log", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.time_out) {
			return;
		}

		frm.add_custom_button(__("Check Out"), () => {
			frm.call("check_out").then(() => frm.reload_doc());
		});
	},
});
