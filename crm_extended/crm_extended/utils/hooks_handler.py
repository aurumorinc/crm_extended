import frappe
from frappe.utils import add_to_date, get_datetime

def queue_sync(doc, method):
    # 2. Load Settings
    settings = frappe.get_single("Sync Settings")
    
    # 3. Check for Ignored Fields
    # If the user only updated fields that are in the "Ignored Fields" list, stop.
    if settings.ignored_fields:
        ignored_fields = [f.strip() for f in settings.ignored_fields.split(",")]
        # Also ignore standard fields that shouldn't trigger sync logic
        ignored_fields.extend(["modified", "modified_by", "idx", "docstatus"])
        
        if doc.has_value_changed(doc.get_doc_before_save()) and not doc.has_value_changed([f for f in doc.as_dict().keys() if f not in ignored_fields]):
             return

    # 4. Find Matching Configurations
    # We look for rows in 'sync_configs' that match the current DocType and are Enabled
    services_to_sync = []
    if settings.sync_configs:
        for row in settings.sync_configs:
            if row.reference_doctype == doc.doctype and row.enabled:
                services_to_sync.append(row.service)

    # 5. Add to Queue
    for service in services_to_sync:
        # Check if already queued to prevent duplicates
        exists = frappe.db.exists("Sync Queue", {
            "reference_doctype": doc.doctype,
            "reference_name": doc.name,
            "service": service,
            "status": "Queued"
        })
        
        if not exists:
            frappe.get_doc({
                "doctype": "Sync Queue",
                "reference_doctype": doc.doctype,
                "reference_name": doc.name,
                "service": service,
                "status": "Queued"
            }).insert(ignore_permissions=True)