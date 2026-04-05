// Copyright (c) 2026, Montego-arch and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bill of Quantities", {
	refresh(frm) {
		if (frm.doc.site) {
			frm.dashboard.add_indicator(
				__("Site: {0}", [frm.doc.site]), "blue"
			);
		}
	},
});

frappe.ui.form.on("BOQ Items", {
	description(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.description) {
			frappe.db.get_value("BOQ Item Detail", row.description,
				["unit", "description_type", "item", "item_name"],
				(r) => {
					if (r) {
						frappe.model.set_value(cdt, cdn, {
							unit: r.unit,
							description_type: r.description_type,
							item: r.item,
							item_name: r.item_name,
						});
					}
				}
			);
		}
	},

	planned_quantity(frm) {
		frm.dirty();
	},

	rate(frm) {
		frm.dirty();
	},

	create(frm, cdt, cdn) {
		let row = locals[cdt][cdn];

		if (frm.is_new()) {
			frappe.msgprint(__("Please save the BOQ before creating Material Requests."));
			return;
		}

		if (row.description_type !== "Material") {
			frappe.msgprint(__("Material Requests can only be created for Material type items."));
			return;
		}

		if (!row.item) {
			frappe.msgprint(__("No inventory Item linked. Please check the BOQ Item Detail."));
			return;
		}

		let remaining = (row.planned_quantity || 0) - (row.consumed_quantity || 0);

		let dialog = new frappe.ui.Dialog({
			title: __("Create Material Request"),
			fields: [
				{
					fieldname: "item_info",
					fieldtype: "HTML",
					options: `<div class="mb-3">
						<strong>${__("Item")}:</strong> ${row.item_name || row.item}<br>
						<strong>${__("Planned")}:</strong> ${row.planned_quantity || 0}<br>
						<strong>${__("Consumed")}:</strong> ${row.consumed_quantity || 0}<br>
						<strong>${__("Remaining")}:</strong> ${remaining}
					</div>`,
				},
				{
					fieldname: "qty",
					fieldtype: "Float",
					label: __("Quantity"),
					default: Math.max(remaining, 0),
					reqd: 1,
				},
			],
			primary_action_label: __("Create"),
			primary_action(values) {
				dialog.hide();
				frappe.call({
					method: "dantata_town.dantata_town.doctype.bill_of_quantities.bill_of_quantities.create_material_request",
					args: {
						boq_name: frm.doc.name,
						child_docname: row.name,
						qty: values.qty,
					},
					callback(r) {
						if (r.message) {
							frm.reload_doc();
						}
					},
				});
			},
		});
		dialog.show();
	},
});
