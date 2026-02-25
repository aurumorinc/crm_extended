import frappe

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
