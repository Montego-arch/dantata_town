// Copyright (c) 2026, Montego-arch and contributors
// For license information, please see license.txt

frappe.ui.form.on("Site", {
	refresh(frm) {
		frm.set_query("unit_type", "project_units", () => {
			return {
				filters: { item_group: "PROPERTIES" },
			};
		});

		if (!frm.is_new()) {
			frm.add_custom_button(__("Create Project"), () => {
				let items = (frm.doc.project_units || [])
					.map((row) => row.unit_type)
					.filter(Boolean);

				if (!items.length) {
					frappe.msgprint(
						__("Please add at least one item in Project Units table")
					);
					return;
				}

				frappe.new_doc("Project", {
					project_name: items.join(", "),
					site: frm.doc.name,
					expected_start_date: frm.doc.expected_start_date,
					expected_end_date: frm.doc.expected_end_date,
				});
			});
		}
	},
});

frappe.ui.form.on("Project Unit Item", {
	unit_type(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.unit_type) {
			frappe.db.get_value("Item", row.unit_type, "stock_uom", (r) => {
				if (r) {
					frappe.model.set_value(cdt, cdn, "uom", r.stock_uom);
				}
			});
		} else {
			frappe.model.set_value(cdt, cdn, "uom", "");
		}
	},
});
