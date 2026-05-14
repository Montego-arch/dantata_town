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

	async project(frm) {
		if (!frm.doc.project) return;
		const r = await frappe.call({
			method: "dantata_town.dantata_town.sales_order.existing_so_for_project",
			args: {
				project: frm.doc.project,
				current_so: frm.is_new() ? null : frm.doc.name,
			},
		});
		const existing = r?.message;
		if (existing) {
			frappe.msgprint({
				title: __("Project already linked"),
				message: __("Sales Order {0} already uses project {1}. Saving will be blocked.", [existing, frm.doc.project]),
				indicator: "red",
			});
		}
	},
});
