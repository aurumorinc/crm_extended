import frappe
from frappe import _
import requests
import json
import time
from frappe.utils import now_datetime, get_datetime, now, add_to_date, cint
from frappe.utils.jinja import validate_template
from frappe.integrations.doctype.webhook.webhook import get_context, get_webhook_headers, get_webhook_data
from croniter import croniter


def process_all_webhooks():
    """
    Scheduled job to process all rate-limited webhooks.
    """
    if not frappe.db.has_column("Webhook", "enable_rate_limit"):
        return

    webhooks = frappe.get_all("Webhook", 
        filters={"enabled": 1, "enable_rate_limit": 1}, 
        fields=["name"]
    )
    
    for webhook_data in webhooks:
        process_webhook_queue(webhook_data.name)

def process_webhook_queue(webhook_name):
    """
    Process the Redis queue for a specific Webhook.
    """
    try:
        webhook = frappe.get_doc("Webhook", webhook_name)
    except frappe.DoesNotExistError:
        return

    if not webhook.enabled:
        return

    queue_key = f"webhook_queue:{webhook.name}"
    
    limit_count = cint(webhook.rate_limit_count) or 60
    frequency = webhook.frequency or "All"
    
    if not check_schedule(frequency, webhook.cron_format, webhook.name):
        return

    # Use generic process_queue but adapt it for Webhook doc
    process_queue(queue_key, limit_count, webhook, "Webhook")

def check_schedule(frequency, cron_format, identifier):
    should_run = False
    current_time = now_datetime()
    
    if frequency == "All":
        should_run = True
    elif frequency == "Daily":
        if current_time.hour == 0 and current_time.minute == 0:
            should_run = True
    elif frequency == "Weekly":
        if current_time.weekday() == 6 and current_time.hour == 0 and current_time.minute == 0:
            should_run = True
    elif frequency == "Monthly":
        if current_time.day == 1 and current_time.hour == 0 and current_time.minute == 0:
            should_run = True
    elif frequency == "Hourly":
        if current_time.minute == 0:
            should_run = True
    elif frequency == "Cron":
        if cron_format:
            try:
                if croniter.match(cron_format, current_time):
                    should_run = True
            except Exception:
                frappe.log_error(f"Invalid Cron Expression for {identifier}: {cron_format}", "Integration Schedule Error")
    
    return should_run

def process_queue(queue_key, limit_count, settings_or_webhook, integration_name):
    """
    Generic queue processor.
    settings_or_webhook: The configuration document (Apollo Settings or Webhook).
    """
    lock_key = f"lock:{queue_key}"
    
    if frappe.cache().get_value(lock_key):
        return

    frappe.cache().set_value(lock_key, 1, expires_in_sec=300)

    try:
        processed_count = 0
        
        while processed_count < limit_count:
            item_data_str = frappe.cache().lpop(queue_key)
            
            if not item_data_str:
                break
                
            try:
                if isinstance(item_data_str, bytes):
                    item_data_str = item_data_str.decode('utf-8')
                    
                item_data = json.loads(item_data_str)
                
                if frappe.db.exists(item_data["doctype"], item_data["name"]):
                    doc = frappe.get_doc(item_data["doctype"], item_data["name"])
                    
                    if integration_name == "Webhook":
                        # Standard Webhook Sending
                        send_standard_webhook(settings_or_webhook, doc, item_data.get("event"))
                    
                processed_count += 1
                
            except Exception as e:
                frappe.log_error(f"Error processing queue item for {queue_key}: {str(e)}", "Integration Queue Error")
        
        # Update processed time if available
        if processed_count > 0 and hasattr(settings_or_webhook, "processed"):
             frappe.db.set_value(settings_or_webhook.doctype, settings_or_webhook.name, "processed", now_datetime())

    finally:
        frappe.cache().delete_value(lock_key)

def send_standard_webhook(webhook, doc, method):
    """
    Prepares and sends a standard Webhook using frappe's logic but inside our worker.
    """
    try:
        # Recalculate context-dependent values
        request_url = webhook.request_url
        if webhook.is_dynamic_url:
            request_url = frappe.render_template(webhook.request_url, get_context(doc))
            
        headers = get_webhook_headers(doc, webhook)
        data = get_webhook_data(doc, webhook)
        
        timeout = webhook.timeout or 5
        queue_name = webhook.background_jobs_queue or 'default'
        
        frappe.enqueue(
            method="crm_extended.crm_extended.integrations.utils.send_webhook_request",
            queue=queue_name,
            timeout=300,
            event=method,
            is_async=True,
            job_name=f"webhook-{webhook.name}-{doc.doctype}-{doc.name}",
            url=request_url,
            request_method=webhook.request_method,
            headers=headers,
            data=data,
            integration_name=webhook.name,
            request_timeout=timeout
        )
    except Exception as e:
        frappe.log_error(f"Error preparing standard webhook {webhook.name}: {str(e)}", "Webhook Error")



def send_webhook_request(url, request_method, headers, data, integration_name=None, request_timeout=5):
    """
    Worker function to send the actual request with retry logic.
    """
    max_retries = 3
    retry_delay = 5 

    for attempt in range(max_retries):
        try:
            json_data = None
            form_data = None
            
            is_json = False
            if headers:
                ct = headers.get('Content-Type', '').lower()
                if 'application/json' in ct:
                    is_json = True
                elif 'application/x-www-form-urlencoded' in ct:
                    is_json = False
                else:
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
            return

        except Exception as e:
            if attempt < max_retries - 1:
                frappe.logger().warning(f"Webhook Attempt {attempt + 1} Failed ({integration_name}): {str(e)}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay * (attempt + 1)) 
            else:
                frappe.log_error(f"Webhook Failed ({integration_name}) after {max_retries} attempts: {str(e)}\nURL: {url}", "Webhook Error")
                raise e

def has_value_changed_except(doc, ignore_fields):
    """
    Check if the document has changed, ignoring the specified fields.
    """
    if doc.is_new():
        return True

    doc_before_save = doc.get_doc_before_save()
    if not doc_before_save:
        return True

    if isinstance(ignore_fields, str):
        ignore_fields = [f.strip() for f in ignore_fields.split(",") if f.strip()]
    elif not isinstance(ignore_fields, list):
         ignore_fields = []

    for field in doc.meta.fields:
        fieldname = field.fieldname
        if fieldname in ignore_fields:
            continue
            
        old_value = doc_before_save.get(fieldname)
        new_value = doc.get(fieldname)
        
        if old_value != new_value:
             return True
             
    return False
