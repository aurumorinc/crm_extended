import frappe
from frappe.utils import add_to_date, get_datetime

def crm_lead_before_save(doc, method):
    # Fix: Ensure comparison between datetime objects
    if doc.synced and not (
        get_datetime(doc.modified or doc.creation)
        > get_datetime(add_to_date(doc.synced, seconds=30))
    ):
        doc.state = "Current"
    else:
        doc.state = "Draft"

def crm_organization_before_save(doc, method):
    # Fix: Ensure comparison between datetime objects
    if doc.synced and not (
        get_datetime(doc.modified or doc.creation)
        > get_datetime(add_to_date(doc.synced, seconds=30))
    ):
        doc.state = "Current"
    else:
        doc.state = "Draft"