from . import __version__ as app_version

app_name = "agriculture"
app_title = "Agriculture"
app_publisher = "AgriTheory"
app_description = "Agriculture field-operations system for Syova Seeds (CyveTech)"
app_icon = "🌱"
app_color = "green"
app_email = "pandikunta@frappe.io"
app_license = "GNU General Public License v3.0"

required_apps = ["erpnext"]

add_to_apps_screen = [
	{
		"name": "agriculture",
		"logo": "/assets/agriculture/images/agriculture.svg",
		"title": "Agriculture",
		"route": "/app/agriculture",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "agriculture.bundle.css"
app_include_js  = "/assets/agriculture/js/agriculture.js"

# include js, css files in header of web template
# web_include_css = "/assets/agriculture/css/agriculture.css"
# web_include_js = "/assets/agriculture/js/agriculture.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "agriculture/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "agriculture.utils.jinja_methods",
# 	"filters": "agriculture.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "agriculture.install.before_install"
after_install = "agriculture.agriculture.setup.setup_agriculture"

# Uninstallation
# ------------

# before_uninstall = "agriculture.uninstall.before_uninstall"
after_uninstall = "agriculture.agriculture.setup.cleanup_role_and_permissions"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "agriculture.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Field Activity Log": "agriculture.agriculture.permissions.field_activity_log_query",
	"Activity Plan": "agriculture.agriculture.permissions.activity_plan_query",
	"Demo Garden": "agriculture.agriculture.permissions.demo_garden_query",
	"Demo Garden Material Request": "agriculture.agriculture.permissions.material_request_query",
	"Demo Garden Planting Record": "agriculture.agriculture.permissions.planting_record_query",
	"Demo Garden Input Application": "agriculture.agriculture.permissions.input_application_query",
	"Demo Garden Monitoring Visit": "agriculture.agriculture.permissions.monitoring_visit_query",
	"Demo Garden Field Day": "agriculture.agriculture.permissions.field_day_query",
	"Farmer Training Event": "agriculture.agriculture.permissions.training_event_query",
	"Order Collection": "agriculture.agriculture.permissions.order_collection_query",
	"Promoter Stock Ledger": "agriculture.agriculture.permissions.stock_ledger_query",
	"Promoter KPI Target": "agriculture.agriculture.permissions.kpi_target_query",
	"Promoter Task": "agriculture.agriculture.permissions.promoter_task_query",
	"Material Receipt": "agriculture.agriculture.permissions.material_receipt_query",
}

has_permission = {
	"Field Activity Log": "agriculture.agriculture.permissions.field_activity_log_perm",
	"Activity Plan": "agriculture.agriculture.permissions.activity_plan_perm",
	"Demo Garden": "agriculture.agriculture.permissions.demo_garden_perm",
	"Demo Garden Material Request": "agriculture.agriculture.permissions.material_request_perm",
	"Demo Garden Planting Record": "agriculture.agriculture.permissions.planting_record_perm",
	"Demo Garden Input Application": "agriculture.agriculture.permissions.input_application_perm",
	"Demo Garden Monitoring Visit": "agriculture.agriculture.permissions.monitoring_visit_perm",
	"Demo Garden Field Day": "agriculture.agriculture.permissions.field_day_perm",
	"Farmer Training Event": "agriculture.agriculture.permissions.training_event_perm",
	"Order Collection": "agriculture.agriculture.permissions.order_collection_perm",
	"Promoter Stock Ledger": "agriculture.agriculture.permissions.stock_ledger_perm",
	"Promoter KPI Target": "agriculture.agriculture.permissions.kpi_target_perm",
	"Promoter Task": "agriculture.agriculture.permissions.promoter_task_perm",
	"Material Receipt": "agriculture.agriculture.permissions.material_receipt_perm",
}

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
	"Order Collection": {
		"on_update": "agriculture.agriculture.sap_integration.on_order_update",
	},
	"Demo Garden Material Request": {
		"on_update": "agriculture.agriculture.sap_integration.on_material_request_update",
	},
	"Customer": {
		"on_update": "agriculture.agriculture.customer_hooks.ensure_customer_warehouse",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"hourly": [
		"agriculture.agriculture.sap_integration.poll_mmr_receipts",
	],
	"daily": [
		"agriculture.agriculture.tasks.send_demo_garden_harvest_alerts",
		"agriculture.agriculture.tasks.alert_unreported_materials",
		"agriculture.agriculture.tasks.alert_unapplied_inputs",
		"agriculture.agriculture.tasks.alert_planned_not_executed",
		"agriculture.agriculture.tasks.alert_missing_weekly_plans",
		"agriculture.agriculture.sap_integration.scheduled_master_sync",
	],
}

# Testing
# -------

# before_tests = "agriculture.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "agriculture.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "agriculture.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


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
# 	"agriculture.auth.validate"
# ]

global_search_doctypes = {
	"Agriculture": [
		{"doctype": "Field Promoter", "index": 1},
		{"doctype": "Farmer", "index": 2},
		{"doctype": "Activity Plan", "index": 3},
		{"doctype": "Field Activity Log", "index": 4},
		{"doctype": "Demo Garden", "index": 5},
		{"doctype": "Demo Garden Material Request", "index": 6},
		{"doctype": "Demo Garden Field Day", "index": 7},
		{"doctype": "Farmer Training Event", "index": 8},
		{"doctype": "Order Collection", "index": 9},
		{"doctype": "Crop", "index": 10},
		{"doctype": "Disease", "index": 11},
		{"doctype": "Fertilizer", "index": 12},
		{"doctype": "Weather", "index": 13},
		{"doctype": "Soil Texture", "index": 14},
		{"doctype": "Water Analysis", "index": 15},
		{"doctype": "Soil Analysis", "index": 16},
		{"doctype": "Plant Analysis", "index": 17},
		{"doctype": "Agriculture Analysis Criteria", "index": 18},
	]
}

domains = {
	'Agriculture': 'agriculture.agriculture.agriculture',
}

