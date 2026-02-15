import frappe
from frappe import _
import requests
import json
import time
from frappe.utils import now_datetime, get_datetime, now, add_to_date, cint
from frappe.utils.jinja import validate_template
from frappe.integrations.doctype.webhook.webhook import get_context

def trigger_integration(doc, method, integration_name):
    """
    Trigger a specific integration (Apollo, Teable).
    Checks settings, conditions, and enqueues the request.
    """
    settings_doctype = integration_name # Already passed as full doctype name e.g., "Apollo Settings"
    
    if not frappe.db.exists("DocType", settings_doctype):
        return

    settings = frappe.get_single(settings_doctype)
    
    if not settings.enabled:
        return

    # Evaluate Condition
    if settings.condition:
        doc.has_value_changed_except = lambda ignore_fields: has_value_changed_except(doc, ignore_fields)
        context = get_context(doc)
        context["event"] = method
        
        if not frappe.safe_eval(settings.condition, context):
            return

    # Rate Limiting
    if settings.enable_rate_limit:
        rate_limit_key = f"crm_extended:rate_limit:{integration_name}"
        rate_limit_count = settings.rate_limit_count or 60
        rate_limit_interval = settings.rate_limit_interval or 60
        
        # Simple sliding window or fixed window counter using Redis
        current_count = frappe.cache().get_value(rate_limit_key) or 0
        if cint(current_count) >= cint(rate_limit_count):
            frappe.logger().info(f"Rate limit exceeded for {integration_name}. Skipping webhook.")
            return

        # Increment count and set expiry if new
        pipe = frappe.cache().pipeline()
        pipe.incr(rate_limit_key)
        if not current_count:
             pipe.expire(rate_limit_key, rate_limit_interval)
        pipe.execute()
        
        # Update last processed at (optional, for UI visibility)
        frappe.db.set_value(settings_doctype, settings.name, "last_processed_at", now_datetime())

    # Prepare Request
    try:
        request_url = settings.request_url
        # Check if URL needs rendering (simple check for {{)
        if "{{" in request_url:
            request_url = frappe.render_template(settings.request_url, get_context(doc))

        headers = {}
        if settings.webhook_headers:
            for h in settings.webhook_headers:
                headers[h.key] = h.value 

        data = None
        if settings.request_structure == "JSON":
             if settings.webhook_json:
                data = frappe.render_template(settings.webhook_json, get_context(doc))
                try:
                    data = json.loads(data)
                except Exception:
                    # If it fails to parse as JSON, keep it as string or log error? 
                    # frappe.enqueue handles serialization but requests.post(json=...) needs dict/list
                    # Let's try to pass it as dict if possible, otherwise it might fail later
                    pass 
        elif settings.webhook_data:
            data = {}
            for d in settings.webhook_data:
                data[d.key] = frappe.render_template(d.value, get_context(doc))

        # Enqueue the job with synchronous=False (async)
        queue_name = settings.background_jobs_queue or 'default'
        
        # Security: Add HMAC Signature if enabled
        if settings.enable_security and settings.webhook_secret:
            import hmac
            import hashlib
            
            secret = settings.webhook_secret.encode('utf-8')
            payload_string = json.dumps(data) if isinstance(data, (dict, list)) else str(data or "")
            signature = hmac.new(secret, payload_string.encode('utf-8'), hashlib.sha256).hexdigest()
            headers['X-Frappe-Signature'] = signature

        frappe.enqueue(
            method="crm_extended.crm_extended.integrations.utils.send_webhook_request",
            queue=queue_name,
            timeout=300, # Fixed timeout as 'timeout' field doesn't exist in settings yet
            event=method,
            is_async=True,
            job_name=f"{integration_name}-{doc.doctype}-{doc.name}",
            # Args
            url=request_url,
            request_method=settings.request_method,
            headers=headers,
            data=data,
            integration_name=integration_name
        )

    except Exception as e:
        frappe.log_error(f"Error triggering {integration_name} integration: {str(e)}", "Integration Error")


def send_webhook_request(url, request_method, headers, data, integration_name=None):
    """
    Worker function to send the actual request with retry logic.
    """
    max_retries = 3
    retry_delay = 5 # seconds

    for attempt in range(max_retries):
        try:
            # Determine payload format
            json_data = None
            form_data = None
            
            # Simple heuristic: if headers say JSON, or data is dict/list and structure was JSON
            # Ideally we check headers
            is_json = False
            if headers:
                ct = headers.get('Content-Type', '').lower()
                if 'application/json' in ct:
                    is_json = True
                elif 'application/x-www-form-urlencoded' in ct:
                    is_json = False
                else:
                    # Default behavior if no header
                    is_json = isinstance(data, (dict, list))
            else:
                 is_json = isinstance(data, (dict, list))

            if is_json:
                json_data = data
            else:
                form_data = data

            response = requests.request(
                method=request_method,
                url=url,
                headers=headers,
                json=json_data,
                data=form_data,
                timeout=10
            )
            
            response.raise_for_status()
            
            # If successful, break the retry loop
            return

        except Exception as e:
            if attempt < max_retries - 1:
                # Log warning and retry
                frappe.logger().warning(f"Webhook Attempt {attempt + 1} Failed ({integration_name}): {str(e)}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay * (attempt + 1)) # Linear backoff
            else:
                # Final failure log
                frappe.log_error(f"Webhook Failed ({integration_name}) after {max_retries} attempts: {str(e)}\nURL: {url}", "Webhook Error")
                # Ideally, we could raise here to let Redis Queue mark job as failed, 
                # but frappe.enqueue handles exceptions by logging them anyway.
                raise e

def has_value_changed_except(doc, ignore_fields):
    """
    Check if the document has changed, ignoring the specified fields.
    
    Args:
        doc (Document): The document to check.
        ignore_fields (list or str): A list or comma-separated string of fields to ignore.
        
    Returns:
        bool: True if the document has changed (excluding ignored fields), False otherwise.
    """
    if doc.is_new():
        return True

    doc_before_save = doc.get_doc_before_save()
    if not doc_before_save:
        # Should ideally be available on_update, but fallback
        return True

    if isinstance(ignore_fields, str):
        # Handle comma-separated string, stripping whitespace
        ignore_fields = [f.strip() for f in ignore_fields.split(",") if f.strip()]
    elif not isinstance(ignore_fields, list):
         # Default to empty list if None or invalid type to prevent errors
         ignore_fields = []

    # Get all fields that have changed
    for field in doc.meta.fields:
        fieldname = field.fieldname
        if fieldname in ignore_fields:
            continue
            
        old_value = doc_before_save.get(fieldname)
        new_value = doc.get(fieldname)
        
        if old_value != new_value:
             return True
             
    return False
