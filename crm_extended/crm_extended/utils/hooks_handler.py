import frappe
from crm_extended.crm_extended.integrations.utils import trigger_integration

def handle_integration_trigger(doc, method):
    trigger_integration(doc, method, "Apollo Settings")
    trigger_integration(doc, method, "Teable Settings")
