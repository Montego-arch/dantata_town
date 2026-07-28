app_name = "dantata_town"
app_title = "Dantata Town"
app_publisher = "Montego-arch"
app_description = "Utility Application for Dantata Town Developers"
app_email = "mmanuelmiles@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "dantata_town",
# 		"logo": "/assets/dantata_town/logo.png",
# 		"title": "Dantata Town",
# 		"route": "/dantata_town",
# 		"has_permission": "dantata_town.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/dantata_town/css/dantata_town.css"
# project_quick_entry.js must load globally (not just on the Project form view)
# because quick-entry can be triggered from list views, link dialogs, etc.
app_include_js = ["/assets/dantata_town/js/project_quick_entry.js"]

# include js, css files in header of web template
# web_include_css = "/assets/dantata_town/css/dantata_town.css"
# web_include_js = "/assets/dantata_town/js/dantata_town.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "dantata_town/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Project": "public/js/project.js",
	"Sales Order": "public/js/sales_order.js",
	"Allocation Letter": "public/js/allocation_letter.js",
	"Quotation": "public/js/quotation.js",
	"Customer Payment Report Settings": "public/js/customer_payment_report_settings.js",
	"Bill of Quantities": "public/js/bill_of_quantities.js",
	"Visitor Log": "public/js/visitor_log.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "dantata_town/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "dantata_town.utils.jinja_methods",
# 	"filters": "dantata_town.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "dantata_town.install.before_install"
after_install = "dantata_town.dantata_town.setup.create_boq_custom_fields"
after_migrate = "dantata_town.dantata_town.setup.create_boq_custom_fields"

# Uninstallation
# ------------

# before_uninstall = "dantata_town.uninstall.before_uninstall"
# after_uninstall = "dantata_town.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "dantata_town.utils.before_app_install"
# after_app_install = "dantata_town.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "dantata_town.utils.before_app_uninstall"
# after_app_uninstall = "dantata_town.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "dantata_town.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Project": {
		"validate": [
			"dantata_town.dantata_town.utils.validate_project_has_site",
			"dantata_town.dantata_town.utils.validate_project_subtype_matches_type",
		],
		"on_update": "dantata_town.dantata_town.project.auto_link_orphan_sales_orders",
	},
	"Quotation": {
		"validate": [
			"dantata_town.dantata_town.quotation.validate_quotation_payment_type",
			"dantata_town.dantata_town.quotation.check_sellable_cap",
		],
	},
	"Purchase Receipt": {
		"on_submit": "dantata_town.dantata_town.utils.update_boq_consumed_qty",
		"on_cancel": "dantata_town.dantata_town.utils.reverse_boq_consumed_qty",
	},
	"Stock Entry": {
		"on_submit": "dantata_town.dantata_town.utils.update_boq_consumed_qty_from_stock_entry",
		"on_cancel": "dantata_town.dantata_town.utils.reverse_boq_consumed_qty_from_stock_entry",
	},
	"Purchase Invoice": {
		"on_submit": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
		"on_cancel": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
	},
	"Expense Claim": {
		"on_submit": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
		"on_cancel": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
	},
	"Journal Entry": {
		"on_submit": [
			"dantata_town.dantata_town.project_aggregations.recalc_for_doc",
			"dantata_town.dantata_town.payment_allocation.recalc_for_je",
		],
		"on_cancel": [
			"dantata_town.dantata_town.project_aggregations.recalc_for_doc",
			"dantata_town.dantata_town.payment_allocation.recalc_for_je",
		],
	},
	"Payment Entry": {
		"on_submit": [
			"dantata_town.dantata_town.project_aggregations.recalc_for_doc",
			"dantata_town.dantata_town.payment_allocation.recalc_for_pe",
		],
		"on_cancel": [
			"dantata_town.dantata_town.project_aggregations.recalc_for_doc",
			"dantata_town.dantata_town.payment_allocation.recalc_for_pe",
		],
	},
	"Bill of Quantities": {
		"validate": [
			"dantata_town.dantata_town.boq_progress.validate_stage_dates",
			"dantata_town.dantata_town.boq_progress.recalc_boq_progress",
		],
		"on_update_after_submit": [
			"dantata_town.dantata_town.boq_progress.recalc_boq_progress",
		],
	},
	"Sales Order": {
		"before_validate": "dantata_town.dantata_town.sales_order.fetch_from_project",
		"validate": [
			"dantata_town.dantata_town.sales_order.enforce_one_so_per_project",
			"dantata_town.dantata_town.sales_order.check_reservations",
		],
		"on_submit": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
		"on_cancel": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
		# Editing a submitted SO (e.g., setting site for the first time, or
		# changing site/project) must re-roll the totals on every affected
		# Project — both the previous Site/Project and the current one.
		"on_update_after_submit": "dantata_town.dantata_town.project_aggregations.recalc_for_doc",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"dantata_town.tasks.all"
# 	],
# 	"daily": [
# 		"dantata_town.tasks.daily"
# 	],
# 	"hourly": [
# 		"dantata_town.tasks.hourly"
# 	],
# 	"weekly": [
# 		"dantata_town.tasks.weekly"
# 	],
# 	"monthly": [
# 		"dantata_town.tasks.monthly"
# 	],
# }

scheduler_events = {
	"daily": [
		"dantata_town.dantata_town.reports.send_monthly_customer_payment_report",
	],
}

# Testing
# -------

# before_tests = "dantata_town.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "dantata_town.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {
	"Project": "dantata_town.dantata_town.overrides.get_project_dashboard_data",
	"Sales Order": "dantata_town.dantata_town.overrides.get_sales_order_dashboard_data",
	"Bill of Quantities": "dantata_town.dantata_town.overrides.get_bill_of_quantities_dashboard_data",
}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["dantata_town.utils.before_request"]
# after_request = ["dantata_town.utils.after_request"]

# Job Events
# ----------
# before_job = ["dantata_town.utils.before_job"]
# after_job = ["dantata_town.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"dantata_town.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

