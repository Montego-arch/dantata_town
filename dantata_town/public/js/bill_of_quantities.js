// Stage number -> parentfield map. Mirror of dantata_town.dantata_town.boq_progress.STAGE_TABLES.
const STAGE_TABLES = {
	1: "table_txao",
	2: "description2",
	3: "description3",
	4: "description4",
	5: "description5",
	6: "description6",
	7: "description7",
};
const PARENTFIELD_TO_STAGE = Object.fromEntries(
	Object.entries(STAGE_TABLES).map(([stage, field]) => [field, Number(stage)])
);

function recalc_stage(frm, stage_no) {
	const rows = frm.doc[STAGE_TABLES[stage_no]] || [];
	const total = rows.length;
	const done = rows.filter((r) => r.completed).length;
	const progress = total ? (100 * done) / total : 0;
	frm.set_value(`stage_${stage_no}_progress`, progress);
	frm.set_value(
		`stage_${stage_no}_status`,
		total && progress === 100 ? "Completed" : ""
	);
	const start = frm.doc[`stage_${stage_no}_start_date`];
	const end = frm.doc[`stage_${stage_no}_end_date`];
	if (start && end) {
		frm.set_value(
			`stage_${stage_no}_duration`,
			frappe.datetime.get_diff(end, start)
		);
	} else {
		frm.set_value(`stage_${stage_no}_duration`, 0);
	}
}

frappe.ui.form.on("Bill of Quantities", {
	refresh(frm) {
		for (const stage_no of Object.keys(STAGE_TABLES)) {
			recalc_stage(frm, Number(stage_no));
		}
	},
});

// Hook every per-stage start/end date field.
for (let stage_no = 1; stage_no <= 7; stage_no++) {
	frappe.ui.form.on("Bill of Quantities", {
		[`stage_${stage_no}_start_date`]: (frm) => recalc_stage(frm, stage_no),
		[`stage_${stage_no}_end_date`]: (frm) => recalc_stage(frm, stage_no),
	});
}

// Live recompute on the line-item completed toggle.
frappe.ui.form.on("BOQ Items", {
	completed(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		const stage_no = PARENTFIELD_TO_STAGE[row.parentfield];
		if (stage_no) {
			recalc_stage(frm, stage_no);
		}
	},
});

// ---------------------------------------------------------------------------
// Sub Contractor Payment Request — modal picker on submitted BOQs.
// ---------------------------------------------------------------------------

frappe.ui.form.on("Bill of Quantities", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Create Sub Contractor Payment Request"), () => {
				open_sub_contractor_modal(frm);
			});
		}
	},
});

function open_sub_contractor_modal(frm) {
	const sub_rows = collect_sub_contractor_rows(frm);
	if (sub_rows.length === 0) {
		frappe.msgprint(__("No sub-contractor lines on this BOQ."));
		return;
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Create Sub Contractor Payment Request"),
		fields: [
			{
				fieldtype: "Link",
				fieldname: "supplier",
				label: __("Supplier"),
				options: "Supplier",
				reqd: 1,
			},
			{
				fieldtype: "Date",
				fieldname: "date",
				label: __("Date"),
				default: frappe.datetime.get_today(),
				reqd: 1,
			},
			{ fieldtype: "Section Break", label: __("Items") },
			{ fieldtype: "HTML", fieldname: "items_html" },
		],
		primary_action_label: __("Create"),
		primary_action: (values) => {
			const selected = collect_checked_rows(dialog, sub_rows);
			if (selected.length === 0) {
				frappe.msgprint(__("Select at least one item."));
				return;
			}
			frappe.call({
				method: "dantata_town.dantata_town.sub_contractor.make_request_from_boq",
				args: {
					boq: frm.doc.name,
					supplier: values.supplier,
					date: values.date,
					selected: JSON.stringify(selected),
				},
				freeze: true,
				freeze_message: __("Creating request..."),
				callback: (r) => {
					if (r.message) {
						dialog.hide();
						frappe.set_route("Form", "Sub Contractor Payment Request", r.message);
					}
				},
			});
		},
	});
	dialog.fields_dict.items_html.$wrapper.html(render_picker_grid(sub_rows));
	dialog.show();
}

function collect_sub_contractor_rows(frm) {
	const out = [];
	for (const [stage_no, fieldname] of Object.entries(STAGE_TABLES)) {
		const stage_title = frm.doc[`stage_${stage_no}`] || "";
		const stage_label = stage_title
			? `Stage ${stage_no} — ${stage_title}`
			: `Stage ${stage_no}`;
		for (const row of frm.doc[fieldname] || []) {
			if (row.assignment_type === "Sub Contractor") {
				out.push({
					stage_label,
					boq_item_name: row.name,
					description: row.description,
					unit: row.unit || "",
					quantity: row.planned_quantity,
					rate: row.rate,
					amount: row.amount,
				});
			}
		}
	}
	return out;
}

function render_picker_grid(rows) {
	const fmt_money = (v) => format_currency(v);
	const lines = rows
		.map(
			(r, i) => `
			<tr>
				<td><input type="checkbox" data-idx="${i}" checked></td>
				<td>${frappe.utils.escape_html(r.stage_label)}</td>
				<td>${frappe.utils.escape_html(r.description)}</td>
				<td>${frappe.utils.escape_html(r.unit)}</td>
				<td class="text-right">${r.quantity}</td>
				<td class="text-right">${fmt_money(r.rate)}</td>
				<td class="text-right">${fmt_money(r.amount)}</td>
			</tr>`
		)
		.join("");
	return `
		<div class="table-responsive">
			<table class="table table-bordered scpr-picker">
				<thead>
					<tr>
						<th></th>
						<th>${__("Stage")}</th>
						<th>${__("Description")}</th>
						<th>${__("Unit")}</th>
						<th class="text-right">${__("Qty")}</th>
						<th class="text-right">${__("Rate")}</th>
						<th class="text-right">${__("Amount")}</th>
					</tr>
				</thead>
				<tbody>${lines}</tbody>
			</table>
		</div>
	`;
}

function collect_checked_rows(dialog, all_rows) {
	const checks = dialog.$wrapper.find(".scpr-picker input[type=checkbox]");
	const selected = [];
	checks.each(function () {
		if (this.checked) {
			const idx = parseInt($(this).data("idx"), 10);
			selected.push(all_rows[idx]);
		}
	});
	return selected;
}
