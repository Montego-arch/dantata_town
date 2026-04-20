frappe.ui.form.on("Allocation Letter", {
	refresh(frm) {
		const state = frm.doc.workflow_state;
		const can_print = state === "Approved" || state === "Submitted";
		if (frm.page.btn_print_action) {
			frm.page.btn_print_action.toggle(can_print);
		}
	},

	purchase_price_option(frm) {
		if (frm.doc.purchase_price_option === "Outright") {
			frm.clear_table("installment_schedule");
			frm.set_value("payment_duration", null);
			frm.refresh_field("installment_schedule");
		}
	},
});
