import frappe
from frappe.email.doctype.notification.notification import Notification, get_context
from frappe import _
import requests

class NtfyNotification(Notification):
	def send_notification_by_channel(self, doc, context):
		if self.channel == "ntfy":
			frappe.enqueue(
				"crm_extended.crm_extended.crm_extended.doctype.notification.notification.send_ntfy_message",
				queue="short",
				doc=doc,
				context=context,
				ntfy_topic=self.ntfy_topic,
				subject=self.subject,
				message=self.message,
				click_url=self.click_url
			)
		else:
			super().send_notification_by_channel(doc, context)

def send_ntfy_message(doc, context, ntfy_topic, subject, message, click_url=None):
	"""
	Background job to send ntfy notifications.
	"""
	if not ntfy_topic:
		return

	try:
		# context might be a dict or json string if queued?
		# frappe.enqueue handles basic types. doc is a dict-like or Document object.
		# But 'doc' passed to enqueue might lose some methods if it's just a dict.
		# However, render_template expects context.
		
		ntfy_topic_doc = frappe.get_doc("ntfy Topic", ntfy_topic)
		
		if subject and "{" in subject:
			subject = frappe.render_template(subject, context)
		
		if message:
			message = frappe.render_template(message, context)
		
		headers = {}
		if subject:
			headers["Title"] = subject.encode('utf-8')
		
		if ntfy_topic_doc.auth_header:
			headers["Authorization"] = ntfy_topic_doc.get_password("auth_header")
		
		if click_url:
			if "{" in click_url:
				click_url = frappe.render_template(click_url, context)
			headers["Click"] = click_url.encode('utf-8')

		url = f"{ntfy_topic_doc.service_url}/{ntfy_topic_doc.topic_name}"
		
		response = requests.post(
			url,
			data=message.encode('utf-8') if message else b"",
			headers=headers,
			timeout=10
		)
		response.raise_for_status()
		
	except Exception:
		frappe.log_error(title="Failed to send ntfy Notification")
