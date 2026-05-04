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
