# Copyright (c) 2026, Montego-arch and Contributors
# See license.txt

import frappe
from frappe import _


def build_customer_payment_report_rows():
	"""Return a list of dicts, one per outstanding (customer, invoice) row,
	ordered by customer asc, posting_date asc. Each row contains:
	  customer, customer_name, name (invoice), posting_date, due_date,
	  outstanding_amount, property_type, property_description, plot_number.
	Property fields default to "—" when there's no linked Allocation Letter.
	"""
	sis = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "outstanding_amount": (">", 0)},
		fields=["name", "customer", "customer_name", "posting_date",
		        "due_date", "outstanding_amount"],
		order_by="customer asc, posting_date asc",
	)
	so_to_al = {}
	rows = []
	for si in sis:
		so = frappe.db.get_value(
			"Sales Invoice Item",
			{"parent": si.name, "sales_order": ("!=", "")},
			"sales_order",
		)
		if so and so not in so_to_al:
			al_name = frappe.db.get_value(
				"Allocation Letter",
				{"sales_order": so, "docstatus": 1},
				"name",
				order_by="letter_date desc",
			)
			so_to_al[so] = frappe.db.get_value(
				"Allocation Letter", al_name,
				["property_type", "property_description", "plot_number"],
				as_dict=True,
			) if al_name else None
		al = so_to_al.get(so) if so else None
		rows.append({
			**si,
			"property_type": (al or {}).get("property_type") or "—",
			"property_description": (al or {}).get("property_description") or "—",
			"plot_number": (al or {}).get("plot_number") or "—",
		})
	return rows


_EMAIL_TEMPLATE = """
<h3>Monthly Customer Payment Report — {{ month_label }}</h3>
{% if rows %}
<table cellpadding="8" cellspacing="0" border="1" style="border-collapse:collapse;">
  <thead>
    <tr>
      <th>Customer</th><th>Invoice</th><th>Due Date</th>
      <th>Outstanding</th><th>Property Type</th><th>Description</th><th>Plot</th>
    </tr>
  </thead>
  <tbody>
  {% for r in rows %}
    <tr>
      <td>{{ r.customer_name or r.customer }}</td>
      <td>{{ r.name }}</td>
      <td>{{ frappe.format(r.due_date, {'fieldtype': 'Date'}) }}</td>
      <td style="text-align:right;">{{ frappe.utils.fmt_money(r.outstanding_amount, currency='NGN') }}</td>
      <td>{{ r.property_type }}</td>
      <td>{{ r.property_description }}</td>
      <td>{{ r.plot_number }}</td>
    </tr>
  {% endfor %}
  </tbody>
  <tfoot>
    <tr>
      <td colspan="3" style="text-align:right;"><b>Total Outstanding</b></td>
      <td style="text-align:right;"><b>{{ frappe.utils.fmt_money(total, currency='NGN') }}</b></td>
      <td colspan="3"></td>
    </tr>
  </tfoot>
</table>
{% else %}
<p>No outstanding balances this month.</p>
{% endif %}
"""


def _send_report_email(settings, today):
	rows = build_customer_payment_report_rows()
	total = sum(frappe.utils.flt(r["outstanding_amount"]) for r in rows)
	month_label = today.strftime("%B %Y")
	html = frappe.render_template(_EMAIL_TEMPLATE, {
		"rows": rows, "total": total, "month_label": month_label,
	})
	recipients = [
		line.strip() for line in (settings.recipient_emails or "").splitlines()
		if line.strip()
	]
	if not recipients:
		frappe.throw(_("No recipient emails configured."))
	frappe.sendmail(
		recipients=recipients,
		subject=_("Monthly Customer Payment Report — {0}").format(month_label),
		message=html,
		now=True,
	)


def _record_status(settings, status, sent_date=None):
	updates = {"last_sent_status": status}
	if sent_date:
		updates["last_sent_date"] = sent_date
	frappe.db.set_value(
		"Customer Payment Report Settings", None, updates, update_modified=False
	)
