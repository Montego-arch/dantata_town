// Copyright (c) 2026, Montego-arch and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sub Contractor Payment Request", {
	refresh(frm) {
		set_pi_button(frm);
	},

	before_submit(frm) {
		const diffs = collect_row_diffs(frm.doc);
		if (diffs.length === 0) return;
		return new Promise((resolve, reject) => {
			const dialog = new frappe.ui.Dialog({
				title: __("Confirm changes before submitting"),
				fields: [{ fieldtype: "HTML", fieldname: "diff_html" }],
				primary_action_label: __("Proceed"),
				primary_action: () => { dialog.hide(); resolve(); },
				secondary_action_label: __("Cancel"),
				secondary_action: () => { dialog.hide(); reject(); },
			});
			dialog.fields_dict.diff_html.$wrapper.html(render_diff_html(diffs));
			dialog.on_hide = () => reject();
			dialog.show();
		});
	},
});

frappe.ui.form.on("Sub Contractor Payment Request Item", {
	quantity(frm, cdt, cdn) {
		recalc_amount(frm, cdt, cdn);
	},
	rate(frm, cdt, cdn) {
		recalc_amount(frm, cdt, cdn);
	},
});

function recalc_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const amount = flt(row.quantity) * flt(row.rate);
	frappe.model.set_value(cdt, cdn, "amount", amount);
	const total = (frm.doc.items || []).reduce(
		(s, r) => s + flt(r.amount), 0
	);
	frm.set_value("total_amount", total);
}

function set_pi_button(frm) {
	if (frm.doc.docstatus !== 1) return;
	if (frm.doc.workflow_state && frm.doc.workflow_state !== "Approved") return;
	if (!frm.doc.workflow_state) {
		// No workflow installed → still allow PI creation only when explicitly Approved
		// is set, or fall back to docstatus=1. For production sites, the workflow
		// will populate workflow_state. For dev/test sites without a workflow, the
		// button is hidden by default to avoid bypassing the gate accidentally.
		return;
	}
	frm.add_custom_button(__("Create Purchase Invoice"), () => create_pi(frm));
}

function create_pi(frm) {
	frappe.call({
		method: "dantata_town.dantata_town.sub_contractor.make_purchase_invoice",
		args: { request_name: frm.doc.name },
		freeze: true,
		freeze_message: __("Creating Purchase Invoice..."),
		callback: (r) => {
			if (r.message) {
				frappe.set_route("Form", "Purchase Invoice", r.message);
			}
		},
	});
}

function collect_row_diffs(doc) {
	const diffs = [];
	for (const row of doc.items || []) {
		const orig_q = flt(row.original_quantity);
		const orig_r = flt(row.original_rate);
		const new_q = flt(row.quantity);
		const new_r = flt(row.rate);
		const qty_changed = orig_q !== new_q
			? { from: orig_q, to: new_q }
			: null;
		const rate_changed = orig_r !== new_r
			? { from: orig_r, to: new_r }
			: null;
		if (qty_changed || rate_changed) {
			diffs.push({
				stage_label: row.stage_label || "",
				description: row.description || "",
				qty_changed,
				rate_changed,
			});
		}
	}
	return diffs;
}

function render_diff_html(diffs) {
	const fmt = (v) => format_currency(v);
	const lines = diffs
		.map((d) => {
			const parts = [];
			if (d.qty_changed) {
				parts.push(`Qty ${d.qty_changed.from} → ${d.qty_changed.to}`);
			}
			if (d.rate_changed) {
				parts.push(
					`Rate ${fmt(d.rate_changed.from)} → ${fmt(d.rate_changed.to)}`
				);
			}
			return `
				<tr>
					<td>${frappe.utils.escape_html(d.stage_label)}</td>
					<td>${frappe.utils.escape_html(d.description)}</td>
					<td>${parts.join("<br>")}</td>
				</tr>`;
		})
		.join("");
	return `
		<p>${__("These rows changed since the request was generated:")}</p>
		<div class="table-responsive">
			<table class="table table-bordered">
				<thead>
					<tr>
						<th>${__("Stage")}</th>
						<th>${__("Description")}</th>
						<th>${__("Changes")}</th>
					</tr>
				</thead>
				<tbody>${lines}</tbody>
			</table>
		</div>
	`;
}
