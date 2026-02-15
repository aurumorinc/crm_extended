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
    settings_doctype = f"{integration_name} Settings"
    
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
    # Prepare payload data (always minimal)
    data = {
        "doctype": doc.doctype,
        "name": doc.name,
        "event": method # Track event type if needed later
    }

    # Queue logic: Push to Redis List
    # We always push to queue now, and the scheduler handles the rate limiting/sending
    if integration_name == "Apollo":
        queue_key = "apollo_sync_queue"
    elif integration_name == "Teable":
        queue_key = "teable_sync_queue"
    else:
        # Fallback or unknown integration
        return

    try:
        # Store as JSON string in Redis List
        frappe.cache().rpush(queue_key, json.dumps(data))
    except Exception as e:
        frappe.log_error(f"Error pushing to {integration_name} queue: {str(e)}", "Integration Error")


def process_apollo_queue():
    _process_integration_queue("Apollo", "apollo_sync_queue")

def process_teable_queue():
    _process_integration_queue("Teable", "teable_sync_queue")

def _process_integration_queue(integration_name, queue_key):
    """
    Generic function to process queued items for an integration, respecting rate limits.
    """
    settings_doctype = f"{integration_name} Settings"
    if not frappe.db.exists("DocType", settings_doctype):
        return

    settings = frappe.get_single(settings_doctype)
    if not settings.enabled:
        return

    # Rate Limit Configuration
    # rate_limit_count: Max requests per interval
    # rate_limit_interval (Frequency): Interval in seconds (default 60s)
    # We'll use a minute-based cron, so 'interval' effectively defines the window for the count.
    # Ideally, if cron runs every minute, we process up to 'rate_limit_count' items.
    
    limit_count = cint(settings.rate_limit_count) or 60
    
    # Frequency Handling (Schedule Check)
    # The job runs every minute (* * * * *). We need to check if the current time matches the selected schedule.
    # If the schedule is "All", we process every minute.
    # If "Daily", we process only if it's midnight (or a specific time).
    # This logic mimics standard Cron behavior within our minute-by-minute worker.
    
    frequency = settings.frequency or "All"
    should_run = False
    
    current_time = now_datetime()
    
    if frequency == "All":
        should_run = True
    elif frequency == "Daily":
        # Run at midnight (00:00)
        if current_time.hour == 0 and current_time.minute == 0:
            should_run = True
    elif frequency == "Weekly":
        # Run on Sunday at midnight
        if current_time.weekday() == 6 and current_time.hour == 0 and current_time.minute == 0:
            should_run = True
    elif frequency == "Monthly":
        # Run on 1st of month at midnight
        if current_time.day == 1 and current_time.hour == 0 and current_time.minute == 0:
            should_run = True
    elif frequency == "Hourly":
        # Run at the start of every hour
        if current_time.minute == 0:
            should_run = True
    elif frequency == "Cron":
        # Validate and check custom cron expression
        if settings.cron_format:
            from croniter import croniter
            try:
                # Check if current time matches the cron expression
                # croniter doesn't have a direct "is_now" match, so we check if the *previous* schedule was exactly a minute ago (or less).
                # Actually, simpler way for minute-resolution cron:
                # Iterate and see if 'now' is a valid trigger time.
                # Since we run every minute, we can just check if cron matches current time.
                if croniter.match(settings.cron_format, current_time):
                    should_run = True
            except Exception:
                frappe.log_error(f"Invalid Cron Expression for {settings_doctype}: {settings.cron_format}", "Integration Schedule Error")
    
    if not should_run:
        return

    # Locking: Prevent overlapping runs if previous job is still running
    lock_key = f"lock:{queue_key}"
    # Use cache.get_value to check, but ideally we want setnx (set if not exists)
    # frappe.cache().set_value supports expires_in_sec, but relies on Redis SETEX
    # We implement a simple lock check.
    
    if frappe.cache().get_value(lock_key):
        return # Job is already running

    # Set lock with 5-minute expiry (failsafe)
    frappe.cache().set_value(lock_key, 1, expires_in_sec=300)

    try:
        # We are running this job every minute via cron.
        # So we will fetch up to `limit_count` items from the Redis list and process them.
        # This acts as a leaky bucket / throttled consumer.
        
        processed_count = 0
        
        while processed_count < limit_count:
            # Pop one item from the head of the queue
            item_data_str = frappe.cache().lpop(queue_key)
            
            if not item_data_str:
                break # Queue is empty
                
            try:
                if isinstance(item_data_str, bytes):
                    item_data_str = item_data_str.decode('utf-8')
                    
                item_data = json.loads(item_data_str)
                
                # Reconstruct context needed for sending (e.g. headers, url generation)
                # We need to fetch the doc again to get fresh data/context
                if frappe.db.exists(item_data["doctype"], item_data["name"]):
                    doc = frappe.get_doc(item_data["doctype"], item_data["name"])
                    
                    # Now actually send the webhook
                    # We reuse the logic but now it's "safe" to send immediately
                    _send_integration_webhook(settings, doc, item_data.get("event"), integration_name)
                    
                processed_count += 1
                
            except Exception as e:
                frappe.log_error(f"Error processing queue item for {settings_doctype}: {str(e)}", "Integration Queue Error")
                # If it failed, do we re-queue? For now, we log and move on to prevent blocking.
        
        if processed_count > 0:
            frappe.db.set_value(settings_doctype, settings.name, "processed", now_datetime())

    finally:
        # Release lock
        frappe.cache().delete_value(lock_key)


def _send_integration_webhook(settings, doc, method, integration_name):
    """
    Helper to prepare and send the actual webhook request.
    This is called by the queue processor.
    """
    try:
        request_url = settings.request_url
        if settings.is_dynamic_url or "{{" in request_url:
            request_url = frappe.render_template(settings.request_url, get_context(doc))

        headers = {}
        if settings.webhook_headers:
            for h in settings.webhook_headers:
                headers[h.key] = h.value

        data = {
            "doctype": doc.doctype,
            "name": doc.name,
            "event": method
        }

        # Security: Add HMAC Signature if enabled
        if settings.enable_security and settings.webhook_secret:
            import hmac
            import hashlib
            
            secret = settings.webhook_secret.encode('utf-8')
            payload_string = json.dumps(data) if isinstance(data, (dict, list)) else str(data or "")
            signature = hmac.new(secret, payload_string.encode('utf-8'), hashlib.sha256).hexdigest()
            headers['X-Frappe-Signature'] = signature

        timeout = settings.timeout or 5
        
        # We can now send directly since we are already in a background worker (scheduler)
        # OR we can enqueue to the 'default' queue to offload the network IO from the scheduler thread
        # Enqueuing is safer to prevent the scheduler from timing out if external API is slow.
        
        queue_name = settings.background_jobs_queue or 'default'
        
        frappe.enqueue(
            method="crm_extended.crm_extended.integrations.utils.send_webhook_request",
            queue=queue_name,
            timeout=300,
            event=method,
            is_async=True,
            job_name=f"{integration_name}-{doc.doctype}-{doc.name}",
            # Args
            url=request_url,
            request_method="POST",
            headers=headers,
            data=data,
            integration_name=integration_name,
            request_timeout=timeout
        )
        
    except Exception as e:
        frappe.log_error(f"Error preparing webhook for {integration_name}: {str(e)}", "Integration Error")


def send_webhook_request(url, request_method, headers, data, integration_name=None, request_timeout=5):
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
                timeout=request_timeout
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
