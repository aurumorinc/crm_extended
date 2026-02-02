import frappe

def get_sequence_message(lead_name, sequence_name, step, test):
    """
    Fetches the email body for the specified sequence and step.
    """
    # 1. Find the Sequence Contact record
    # Note: Assuming 'reference_name' stores the Lead ID
    seq_contact = frappe.db.get_value("Sequence Contact",
        {"reference_name": lead_name, "sequence": sequence_name},
        "name"
    )
    
    if not seq_contact:
        return ""

    # 2. Fetch the content linked to this enrollment and step
    content = frappe.db.get_value("Sequence Email",
        {"sequence_contact": seq_contact, "step": step, "test": test},
        "message"
    )
    
    return content or ""

def get_lead_link(lead_name, title):
    """
    Fetches a personalized URL for a lead by title from the Child Table.
    """
    # Querying the child table directly
    url = frappe.db.get_value("CRM Lead Link", 
        {"parent": lead_name, "title": title}, 
        "url"
    )
    return url or "#"
