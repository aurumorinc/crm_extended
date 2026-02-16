import frappe
from frappe.email.doctype.notification.notification import Notification, get_context
from frappe import _
import requests

class NtfyNotification(Notification):
	def send_notification_by_channel(self, doc, context):
		if self.channel == "ntfy":
			self.send_ntfy_message(doc, context)
		else:
			super().send_notification_by_channel(doc, context)

	def send_ntfy_message(self, doc, context):
		if not self.ntfy_topic:
			return

		try:
			ntfy_topic_doc = frappe.get_doc("ntfy Topic", self.ntfy_topic)
			
			subject = self.subject
			if "{" in subject:
				subject = frappe.render_template(self.subject, context)
			
			message = frappe.render_template(self.message, context)
			
			headers = {}
			if subject:
				headers["Title"] = subject.encode('utf-8')
			
			if ntfy_topic_doc.auth_header:
				headers["Authorization"] = ntfy_topic_doc.get_password("auth_header")
			
			if self.click_url:
				click_url = self.click_url
				if "{" in click_url:
					click_url = frappe.render_template(self.click_url, context)
				headers["Click"] = click_url.encode('utf-8')

			url = f"{ntfy_topic_doc.service_url}/{ntfy_topic_doc.topic_name}"
			
			response = requests.post(
				url,
				data=message.encode('utf-8'),
				headers=headers
			)
			response.raise_for_status()
			
		except Exception as e:
			self.log_error("Failed to send ntfy Notification")
