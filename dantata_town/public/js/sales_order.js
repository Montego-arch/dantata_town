frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && !frm.is_new()) {
			frm.add_custom_button(__("Allocation Letter"), () => {
				frappe.model.open_mapped_doc({
					method: "dantata_town.dantata_town.doctype.allocation_letter.allocation_letter.make_allocation_letter",
					frm: frm,
				});
			}, __("Create"));
		}
	},
});
