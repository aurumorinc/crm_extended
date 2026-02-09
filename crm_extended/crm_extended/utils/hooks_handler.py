import frappe
from frappe.utils import add_to_date, get_datetime

def crm_lead_before_save(doc, method):
    # Added as_datetime=True
    if doc.synced and not (
        get_datetime(doc.modified or doc.creation)
        > add_to_date(doc.synced, seconds=30, as_datetime=True)
    ):
        doc.state = "Current"
    else:
        doc.state = "Draft"

def crm_organization_before_save(doc, method):
    # Added as_datetime=True
    if doc.synced and not (
        get_datetime(doc.modified or doc.creation)
        > add_to_date(doc.synced, seconds=30, as_datetime=True)
    ):
        doc.state = "Current"
    else:
        doc.state = "Draft"