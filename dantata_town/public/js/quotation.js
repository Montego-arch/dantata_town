frappe.ui.form.on("Quotation", {
	refresh(frm) {
		if (
			frm.doc.payment_type === "Installment"
			&& frm.doc.docstatus === 0
			&& !frm.is_new()
			&& frm.doc.installment_deposit_amount
			&& frm.doc.installment_start_date
			&& frm.doc.installment_months
		) {
			frm.add_custom_button(__("Generate Installment Schedule"), () => {
				frappe.call({
					method: "dantata_town.dantata_town.quotation.generate_installment_schedule",
					args: { quotation_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Generating schedule..."),
					callback: () => frm.reload_doc(),
				});
			});
		}
	},

	payment_type(frm) {
		if (frm.doc.payment_type === "Outright") {
			frm.set_value("installment_deposit_amount", null);
			frm.set_value("installment_start_date", null);
			frm.set_value("installment_months", null);
		}
	},
});
