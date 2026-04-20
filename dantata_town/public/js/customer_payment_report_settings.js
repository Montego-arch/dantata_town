frappe.ui.form.on("Customer Payment Report Settings", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Send Now"), () => {
				frappe.confirm(
					__("Send the report to all configured recipients now?"),
					() => {
						frappe.call({
							method: "dantata_town.dantata_town.reports.send_report_now",
							freeze: true,
							freeze_message: __("Sending..."),
							callback: () => {
								frappe.show_alert({
									message: __("Report sent"),
									indicator: "green",
								});
								frm.reload_doc();
							},
						});
					},
				);
			});
		}
	},
});
