app_name = "crm_extended"
app_title = "CRM Extended"
app_publisher = "Aurumor"
app_description = "CRM Extended"
app_email = "hello@aurumor.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "crm_extended",
# 		"logo": "/assets/crm_extended/logo.png",
# 		"title": "CRM Extended",
# 		"route": "/crm_extended",
# 		"has_permission": "crm_extended.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/crm_extended/css/crm_extended.css"
# app_include_js = "/assets/crm_extended/js/crm_extended.js"

# include js, css files in header of web template
# web_include_css = "/assets/crm_extended/css/crm_extended.css"
# web_include_js = "/assets/crm_extended/js/crm_extended.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "crm_extended/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"CRM Lead": "public/js/crm_lead.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "crm_extended/public/icons.svg"

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

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": [
		"crm_extended.crm_extended.utils.jinja.get_sequence_message",
		"crm_extended.crm_extended.utils.jinja.get_lead_link"
	]
}

# Installation
# ------------

# before_install = "crm_extended.install.before_install"
# after_install = "crm_extended.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "crm_extended.uninstall.before_uninstall"
# after_uninstall = "crm_extended.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "crm_extended.utils.before_app_install"
# after_app_install = "crm_extended.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "crm_extended.utils.before_app_uninstall"
# after_app_uninstall = "crm_extended.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "crm_extended.notifications.get_notification_config"

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

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"CRM Lead": {
		"on_update": [
			"crm_extended.crm_extended.doctype.google_mail.google_mail.fetch_emails_for_lead"
		]
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		"* * * * *": [
			"crm_extended.crm_extended.integrations.utils.process_all_webhooks",
			"crm_extended.crm_extended.doctype.google_mail.google_mail.sync"
		]
	}
}

# Testing
# -------

# before_tests = "crm_extended.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "crm_extended.custom.task.CustomTaskMixin"
# }

override_doctype_class = {
	"Notification": "crm_extended.crm_extended.doctype.notification.notification.NtfyNotification"
}

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "crm_extended.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "crm_extended.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["crm_extended.utils.before_request"]
# after_request = ["crm_extended.utils.after_request"]

# Job Events
# ----------
# before_job = ["crm_extended.utils.before_job"]
# after_job = ["crm_extended.utils.after_job"]

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
# 	"crm_extended.auth.validate"
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

fixtures = [
	{"dt": "Custom Field", "filters": [["module", "=", "CRM Extended"]]},
	{"dt": "Property Setter", "filters": [["module", "=", "CRM Extended"]]}
]
