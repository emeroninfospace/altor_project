app_name = "altor_project"
app_title = "Altor Project"
app_publisher = "Emeron Infospace"
app_description = "Altor Project"
app_email = "info@emeron.io"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "altor_project",
# 		"logo": "/assets/altor_project/logo.png",
# 		"title": "Altor Project",
# 		"route": "/altor_project",
# 		"has_permission": "altor_project.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/altor_project/css/altor_project.css"
# app_include_js = "/assets/altor_project/js/altor_project.js"

# include js, css files in header of web template
# web_include_css = "/assets/altor_project/css/altor_project.css"
# web_include_js = "/assets/altor_project/js/altor_project.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "altor_project/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Project": "public/js/project.js",
	"Material Request": "public/js/material_request.js",
	"Task": "public/js/task.js",
	"Lead": "public/js/lead.js",
	"Timesheet": "public/js/timesheet.js",
	"Item": "public/js/item.js",
	"Sales Order": "public/js/sales_order.js",
	"Purchase Order": "public/js/purchase_order.js",
}

override_doctype_class = {
	"Quotation": "altor_project.events.quotation.CustomQuotation",
	"Lead": "altor_project.events.lead.CustomLead",
}

doctype_list_js = {"Project": "public/js/project_list.js", "Lead": "public/js/lead_list.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "altor_project/public/icons.svg"

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
jinja = {
	"methods": [
		"altor_project.print_utils.altor_company",
		"altor_project.print_utils.altor_party",
		"altor_project.print_utils.altor_lines",
		"altor_project.print_utils.altor_item_taxes",
		"altor_project.print_utils.altor_item_groups",
		"altor_project.print_utils.altor_validity_days",
		"altor_project.print_forms.altor_print_form",
	]
}

# jinja = {
# 	"methods": "altor_project.utils.jinja_methods",
# 	"filters": "altor_project.utils.jinja_filters"
# }

# Installation
# ------------

after_install = "altor_project.setup.after_install"
# Hide Frappe School / marketplace shortcuts and onboarding panels that ERPNext adds back on updates
after_migrate = "altor_project.custom_and_property_setter.workspace_cleanup.hide_frappe_links"
before_uninstall = "altor_project.setup.before_uninstall"

# Uninstallation
# ------------

# before_uninstall = "altor_project.uninstall.before_uninstall"
# after_uninstall = "altor_project.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "altor_project.utils.before_app_install"
# after_app_install = "altor_project.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "altor_project.utils.before_app_uninstall"
# after_app_uninstall = "altor_project.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "altor_project.notifications.get_notification_config"

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

permission_query_conditions = {
	"Task": "altor_project.altor_project.permissions.task_permission.get_permission_query_conditions"
}

# has_permission = {
#     "Task": "altor_project.altor_project.permissions.task_permission.has_permission"
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

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }
doc_events = {
	"Sales Invoice": {
		"on_submit": "altor_project.events.sales_invoice.on_submit",
		"on_cancel": "altor_project.events.sales_invoice.on_cancel",
	},
	"Task": {"on_update": "altor_project.events.task.update_parent_task_progress"},
	"Site Visit": {
		"on_submit": "altor_project.events.lead.on_site_visit_submit",
		"on_cancel": "altor_project.events.lead.on_site_visit_cancel",
	},
	# Item Group wise Project Budget: checks and live figures
	"Material Request": {"validate": "altor_project.budget.validate_budget"},
	"Purchase Order": {
		"validate": "altor_project.budget.validate_budget",
		"on_submit": "altor_project.budget.on_transaction_change",
		"on_cancel": "altor_project.budget.on_transaction_change",
	},
	"Purchase Invoice": {
		"on_submit": "altor_project.budget.on_transaction_change",
		"on_cancel": "altor_project.budget.on_transaction_change",
	},
	"Subcontract Work Order": {
		"on_submit": "altor_project.budget.on_transaction_change",
		"on_cancel": "altor_project.budget.on_transaction_change",
	},
	"Subcontract Invoice": {
		"on_submit": "altor_project.budget.on_transaction_change",
		"on_cancel": "altor_project.budget.on_transaction_change",
	},
	# Timesheet labour cost: normal / OT 1 / OT 2 hours, own staff and outsourced
	"Timesheet": {
		"validate": [
			"altor_project.labour.calculate_timesheet",
			"altor_project.labour.validate_employee_overlap",
		],
		"on_submit": "altor_project.labour.on_timesheet_change",
		"on_cancel": "altor_project.labour.on_timesheet_change",
	},
	# ERPNext Asset of a "Project Asset" item <-> Project Asset (ERPNext keeps the accounts)
	"Asset": {
		"on_submit": "altor_project.asset_accounting.on_asset_submit",
		"on_cancel": "altor_project.asset_accounting.on_asset_cancel",
	},
	"Item": {"validate": "altor_project.asset_accounting.validate_item"},
	# a Sales Order comes from a Quotation (Altor Settings > Sales Order Only from Quotation)
	"Sales Order": {
		"validate": "altor_project.events.sales_order.require_quotation",
		"on_submit": "altor_project.events.sales_order.on_submit",
		"on_update_after_submit": "altor_project.events.project.sync_lpo_to_projects",
	},
	# a project comes from a submitted Sales Order and takes its customer LPO
	"Project": {
		"before_insert": "altor_project.events.project.division_from_sales_order",
		"validate": "altor_project.events.project.validate_project",
		"after_insert": "altor_project.events.project.set_sales_amount",
	},
	# a quotation is for a Lead; the lead's status follows its quotations
	"Quotation": {
		"validate": "altor_project.events.quotation.require_lead",
		"after_insert": "altor_project.events.lead.refresh_quotation_status",
		"on_submit": "altor_project.events.lead.refresh_quotation_status",
		"on_cancel": "altor_project.events.lead.refresh_quotation_status",
		"on_trash": "altor_project.events.lead.refresh_quotation_status",
	},
	# the new Lead Owner gets a notification
	"Lead": {"on_update": "altor_project.notifications.on_lead_update"},
}

# Division numbering: CRM-SCF-LEAD-2026-0001 -> QT-SCF-2026-0001 -> SO-... -> PRJ-... (and SV-... for site visits)
for _doctype in ("Lead", "Quotation", "Sales Order", "Project", "Site Visit"):
	_events = doc_events.setdefault(_doctype, {})
	_events["autoname"] = "altor_project.custom_and_property_setter.division_naming.set_division_name"
	_existing = _events.get("validate") or []
	_events["validate"] = ["altor_project.custom_and_property_setter.division_naming.keep_ref_on_amend"] + (
		[_existing] if isinstance(_existing, str) else list(_existing)
	)

# Division (Cost Center): rows without their own division take the document's.
# Runs first in validate so the budget checks see the final rows.
for _doctype in (
	"Sales Order",
	"Delivery Note",
	"Sales Invoice",
	"Material Request",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Stock Entry",
):
	_events = doc_events.setdefault(_doctype, {})
	_existing = _events.get("validate") or []
	_events["validate"] = ["altor_project.custom_and_property_setter.division.apply_division_to_rows"] + (
		[_existing] if isinstance(_existing, str) else list(_existing)
	)

app_include_js = [
	"/assets/altor_project/js/project_calendar.js",
	"/assets/altor_project/js/workspace_supervisor.js",
	"/assets/altor_project/js/notification_count.js",
]

fixtures = [
	{
		"dt": "Custom HTML Block",
		"filters": [
			[
				"name",
				"in",
				[
					"My Assignments",
					"Project Overview Dashboard",
					"HR Dashboard",
					"Stock Overview Dashboard",
					"Accounts Overview Dashboard",
				],
			]
		],
	}
]


# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"altor_project.assets.refresh_open_allocations",
		"altor_project.budget.refresh_all_budgets",
	],
	# 1st of the month: last month's project asset depreciation to projects (when enabled)
	"monthly": ["altor_project.asset_accounting.scheduled_allocation"],
	# assignment notifications Frappe did not create (lead re-assigned, task assigned, ...)
	"cron": {"* * * * *": ["altor_project.notifications.notify_missed_assignments"]},
}

# scheduler_events = {
# 	"all": [
# 		"altor_project.tasks.all"
# 	],
# 	"daily": [
# 		"altor_project.tasks.daily"
# 	],
# 	"hourly": [
# 		"altor_project.tasks.hourly"
# 	],
# 	"weekly": [
# 		"altor_project.tasks.weekly"
# 	],
# 	"monthly": [
# 		"altor_project.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "altor_project.install.before_tests"

# Overriding Methods
# ------------------------------
#
# Quotation > Create > Sales Order: a lead's Existing Customer is used (no duplicate customer)
override_whitelisted_methods = {
	"erpnext.selling.doctype.quotation.quotation.make_sales_order": "altor_project.events.quotation.make_sales_order",
	# Assign To: the assignee's notification is written at once (not via a background job)
	"frappe.desk.form.assign_to.add": "altor_project.notifications.add_assignment",
	"frappe.desk.form.assign_to.add_multiple": "altor_project.notifications.add_multiple_assignments",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {
	"Project": "altor_project.events.dashboards.project",
	"Quotation": "altor_project.events.dashboards.quotation",
	"Lead": "altor_project.events.dashboards.lead",
	"Asset": "altor_project.events.dashboards.asset",
	"Supplier": "altor_project.events.dashboards.supplier",
	"Employee": "altor_project.events.dashboards.employee",
}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["altor_project.utils.before_request"]
# after_request = ["altor_project.utils.after_request"]

# Job Events
# ----------
# before_job = ["altor_project.utils.before_job"]
# after_job = ["altor_project.utils.after_job"]

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
# 	"altor_project.auth.validate"
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
