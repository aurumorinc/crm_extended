from __future__ import unicode_literals
import frappe
from frappe.integrations.doctype.webhook import webhook
from crm_extended.crm_extended.integrations.utils import has_value_changed_except

# --- Monkey Patch: Enqueue Webhook ---
# We intercept the standard enqueue process to check for rate limiting.
# If rate limiting is enabled, we push to our custom Redis queue instead of executing immediately.

_original_enqueue = webhook.enqueue_webhook

def custom_enqueue_webhook(doc, webhook_doc):
    # Ensure we have the full document object
    if not isinstance(webhook_doc, frappe.model.document.Document):
        webhook_doc = frappe.get_doc("Webhook", webhook_doc.get("name"))

    # Check for custom rate limit flag
    # We use .get() safely in case the field doesn't exist yet during migration
    if webhook_doc.get("enable_rate_limit"):
        try:
            # Prepare data payload for the queue
            data = {
                "doctype": doc.doctype,
                "name": doc.name,
                "event": webhook_doc.webhook_docevent # Pass the event that triggered this
            }
            
            # Use unique queue key per webhook
            queue_key = f"webhook_queue:{webhook_doc.name}"
            
            # Push to Redis
            frappe.cache().rpush(queue_key, frappe.as_json(data))
            
            # Log for debugging (optional, can be removed in prod)
            # frappe.logger().debug(f"Queued rate-limited webhook {webhook_doc.name} for {doc.name}")
            
            return # Stop here, do not execute standard logic
            
        except Exception as e:
            frappe.log_error(f"Failed to enqueue rate-limited webhook {webhook_doc.name}: {str(e)}", "Webhook Queue Error")
            # If queuing fails, maybe fall back to standard execution? 
            # For now, let's fail safe and log.

    # If no rate limit, proceed with standard Frappe behavior
    return _original_enqueue(doc, webhook_doc)

webhook.enqueue_webhook = custom_enqueue_webhook


# --- Monkey Patch: Context ---
# We inject helper functions like 'has_value_changed_except' into the safe_eval context.

_original_get_context = webhook.get_context

def custom_get_context(doc):
    context = _original_get_context(doc)
    
    # Add helper function to global context
    context['has_value_changed_except'] = has_value_changed_except
    
    # Add helper to document instance for cleaner syntax: doc.has_value_changed_except(...)
    if doc:
        doc.has_value_changed_except = lambda ignore_fields: has_value_changed_except(doc, ignore_fields)
        
    return context

webhook.get_context = custom_get_context
