# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.integrations.doctype.google_settings.google_settings import get_auth_url
from frappe.integrations.google_oauth import GoogleOAuth
from frappe.utils import get_url, now_datetime
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import requests
import base64
from email.utils import parseaddr, parsedate_to_datetime

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

class GoogleMail(Document):
	def validate(self):
		if not frappe.db.get_single_value("Google Settings", "enable"):
			frappe.throw(frappe._("Enable Google Settings first."))

	def get_access_token(self):
		if not self.refresh_token:
			frappe.throw(frappe._("Google Mail is not authorized. Please authorize access first."))
		
		google_settings = frappe.get_doc("Google Settings")
		
		data = {
			"client_id": google_settings.client_id,
			"client_secret": google_settings.get_password(fieldname="client_secret"),
			"refresh_token": self.get_password(fieldname="refresh_token"),
			"grant_type": "refresh_token",
		}
		
		try:
			r = requests.post("https://oauth2.googleapis.com/token", data=data).json()
		except Exception as e:
			frappe.throw(frappe._("Error during access token generation: {0}").format(str(e)))

		if "error" in r:
			frappe.throw(frappe._("Error during access token generation: {0}").format(r.get("error_description")))

		return r.get("access_token")

@frappe.whitelist()
def authorize_access(google_mail_name, reauthorize=False):
	"""
	Generates the authorization URL for Google OAuth.
	"""
	oauth2 = frappe.utils.oauth.OAuth2(
		"Google Settings",
		scopes="https://www.googleapis.com/auth/gmail.readonly",
		redirect_uri=get_url("/api/method/crm_extended.crm_extended.doctype.google_mail.google_mail.google_callback"),
		state={"google_mail_name": google_mail_name}
	)
	
	return oauth2.get_auth_url()

@frappe.whitelist()
def google_callback(code=None, state=None):
	"""
	Handles the callback from Google OAuth.
	"""
	if not code or not state:
		frappe.throw(frappe._("Authorization code or state missing."))

	google_mail_name = state.get("google_mail_name")
	if not google_mail_name:
		frappe.throw(frappe._("Invalid state."))

	google_mail = frappe.get_doc("Google Mail", google_mail_name)
	
	oauth2 = frappe.utils.oauth.OAuth2(
		"Google Settings",
		scopes="https://www.googleapis.com/auth/gmail.readonly",
		redirect_uri=get_url("/api/method/crm_extended.crm_extended.doctype.google_mail.google_mail.google_callback"),
	)
	
	token = oauth2.get_access_token(code)
	
	if not token.get("refresh_token"):
		frappe.throw(frappe._("Refresh token not found. Please revoke access from Google Account settings and try again."))
	
	google_mail.authorization_code = code
	google_mail.refresh_token = token.get("refresh_token")
	google_mail.save()
	
	frappe.db.commit()
	
	return {
		"message": frappe._("Authorization Successful"),
		"redirect_to": f"/app/google-mail/{google_mail_name}"
	}

@frappe.whitelist()
def sync():
	"""
	Scheduled job to sync emails for all enabled Google Mail accounts.
	"""
	google_mails = frappe.get_all("Google Mail", filters={"enable": 1}, pluck="name")
	for google_mail_name in google_mails:
		try:
			sync_emails(google_mail_name)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Google Mail Sync Failed: {google_mail_name}")

def get_google_mail_object(google_mail_name):
	"""
	Returns a built Google Gmail service object.
	"""
	google_settings = frappe.get_doc("Google Settings")
	google_mail = frappe.get_doc("Google Mail", google_mail_name)
	access_token = google_mail.get_access_token()
	
	creds = Credentials(
		token=access_token,
		refresh_token=google_mail.get_password(fieldname="refresh_token"),
		token_uri="https://oauth2.googleapis.com/token",
		client_id=google_settings.client_id,
		client_secret=google_settings.get_password(fieldname="client_secret"),
		scopes=SCOPES
	)
	
	service = build("gmail", "v1", credentials=creds, cache_discovery=False)
	
	return service, google_mail

def sync_emails(google_mail_name):
	"""
	Incremental sync using historyId.
	"""
	service, google_mail = get_google_mail_object(google_mail_name)
	
	# Get list of all Lead emails to filter against
	lead_emails = get_all_lead_emails()
	if not lead_emails:
		return

	history_id = google_mail.get_password("next_sync_token")
	
	if not history_id:
		# First run or reset: fetch recent messages (e.g., last 30 days) or full sync?
		# For safety/performance, maybe just start tracking from now or fetch last X messages.
		# But the requirement says "Initial Sync: Fetch all previous emails for existing leads".
		# That logic might be heavy if run here.
		# Let's assume 'fetch_emails_for_lead' handles specific lead history.
		# Here we just want to catch up on RECENT emails if history_id is missing.
		# OR, we can list messages.
		
		# Strategy: List messages (filtered by leads if possible, but Gmail API 'q' param is limited length).
		# We'll list messages from 'me' and 'to me'.
		
		# Actually, for the general sync loop, we should rely on history if available, else list messages.
		results = service.users().messages().list(userId="me", maxResults=50).execute()
	else:
		try:
			results = service.users().history().list(userId="me", startHistoryId=history_id).execute()
		except Exception:
			# History ID might be invalid/expired
			results = service.users().messages().list(userId="me", maxResults=50).execute()

	messages = []
	if "history" in results:
		for history in results.get("history", []):
			messages.extend(history.get("messagesAdded", []))
	elif "messages" in results:
		messages.extend(results.get("messages", []))

	# Deduplicate
	message_ids = {m["id"] for m in messages}
	
	for msg_id in message_ids:
		process_message(service, msg_id, lead_emails, google_mail.user)

	# Update historyId
	# Note: history.list returns a new historyId, but messages.list doesn't directly return the *latest* historyId easily without a separate call or checking the profile.
	# But for simplicity, let's get the profile's current historyId to store for next time.
	profile = service.users().getProfile(userId="me").execute()
	new_history_id = profile.get("historyId")
	
	google_mail.db_set("next_sync_token", new_history_id)
	google_mail.db_set("last_sync_on", now_datetime())
	frappe.db.commit()

def process_message(service, msg_id, lead_emails, user):
	try:
		message = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
	except Exception:
		return

	headers = message.get("payload", {}).get("headers", [])
	
	sender = ""
	recipients = []
	subject = ""
	date_time = ""
	message_id = ""
	
	for header in headers:
		name = header.get("name", "").lower()
		value = header.get("value", "")
		if name == "from":
			sender = parseaddr(value)[1]
		elif name == "to":
			recipients.extend([parseaddr(x)[1] for x in value.split(",")])
		elif name == "cc":
			recipients.extend([parseaddr(x)[1] for x in value.split(",")])
		elif name == "subject":
			subject = value
		elif name == "received" and not date_time:
			try:
				# Extract date from Received header (e.g., "...; Wed, 07 Jan 2026 03:07:47 -0800 (PST)")
				received_date_str = value.split(';')[-1].strip()
				date_time = parsedate_to_datetime(received_date_str)
			except Exception:
				pass
		elif name == "date" and not date_time:
			try:
				date_time = parsedate_to_datetime(value)
			except Exception:
				pass
		elif name == "message-id":
			message_id = value.strip().strip('<>').strip()

	if not date_time:
		date_time = now_datetime()

	# Check if any participant is a Lead
	participants = set([sender] + recipients)
	matched_leads = participants.intersection(lead_emails)
	
	if not matched_leads:
		return # Security Layer: Skip unrelated emails

	# Determine content
	payload = message.get("payload", {})
	content = get_message_body(payload)
	
	# If body is empty, try to get snippet
	if not content:
		content = message.get("snippet", "")
	
	# Create Communication
	# We link to the FIRST matched lead found (or create multiple communications? Usually one linked to one lead is standard, or link to multiple if possible. Communication allows 'reference_doctype' and 'reference_name').
	# If multiple leads match, we might need logic. For now, pick one.
	
	# Also check if Communication already exists (idempotency)
	# Check against both Gmail ID and Message-ID header
	if frappe.db.exists("Communication", {"message_id": msg_id}) or (message_id and frappe.db.exists("Communication", {"message_id": message_id})):
		return

	# Find the lead ID
	lead_email = list(matched_leads)[0]
	lead_name = frappe.db.get_value("CRM Lead", {"email": lead_email}, "name")

	if not lead_name:
		return

	communication = frappe.get_doc({
		"doctype": "Communication",
		"communication_type": "Communication",
		"communication_medium": "Email",
		"subject": subject,
		"content": content,
		"sender": sender,
		"recipients": ", ".join(recipients),
		"sent_or_received": "Received" if sender not in lead_emails else "Sent", # Logic needs refinement: if sender is the Google Mail user, it's Sent. If sender is Lead, it's Received.
		"reference_doctype": "CRM Lead",
		"reference_name": lead_name,
		"message_id": message_id or msg_id,
		"read_receipt": 1,
		"communication_date": date_time
	})
	
	# Determine direction properly
	# We need the connected user's email addresses (including aliases if possible) to know if it's Sent or Received.
	# For now, if sender is in matched_leads, it's likely Received from that Lead.
	# If sender is NOT in matched_leads (meaning it's me or someone else), and one of the recipients IS a Lead, it's Sent.
	
	if sender in matched_leads:
		communication.sent_or_received = "Received"
	else:
		communication.sent_or_received = "Sent"

	communication.insert(ignore_permissions=True)


def get_message_body(payload):
	body = ""
	if "parts" in payload:
		for part in payload["parts"]:
			if part.get("mimeType") == "text/html":
				data = part.get("body", {}).get("data")
				if data:
					body = base64.urlsafe_b64decode(data).decode()
					break
			elif part.get("mimeType") == "text/plain":
				data = part.get("body", {}).get("data")
				if data:
					body = base64.urlsafe_b64decode(data).decode()
			elif part.get("mimeType") == "multipart/alternative":
				# Recursively get body from nested parts
				body = get_message_body(part)
				if body:
					break
	else:
		data = payload.get("body", {}).get("data")
		if data:
			body = base64.urlsafe_b64decode(data).decode()
	return body

def get_all_lead_emails():
	return set(frappe.get_all("CRM Lead", pluck="email"))

@frappe.whitelist()
def fetch_emails_for_lead(doc, method=None):
	"""
	Fetches historical emails for a specific lead.
	Triggered on Lead creation/update.
	"""
	if isinstance(doc, str):
		lead_name = doc
		lead_email = frappe.db.get_value("CRM Lead", lead_name, "email")
	else:
		lead_name = doc.name
		lead_email = doc.email

	if not lead_email:
		return

	# If google_mail_name is not provided, we might need to iterate all enabled Google Mail accounts
	# or find the one belonging to the Lead owner?
	# Requirement says: "We will create a new DocType named Google Mail... to manage Gmail configurations per user."
	# So we probably want to sync with the Google Mail account of the Lead's owner or current user.
	
	# Let's try to find a Google Mail linked to the current user (if triggered via UI) or Lead Owner.
	# For background jobs, we might want to check ALL enabled Google Mails because any user might have communicated with this Lead.
	# But checking ALL might be expensive API wise.
	
	# Let's check enabled Google Mails.
	google_mails = frappe.get_all("Google Mail", filters={"enable": 1}, pluck="name")
	
	for gm_name in google_mails:
		try:
			service, google_mail = get_google_mail_object(gm_name)
			
			# Search for messages involving this lead email
			# Initial sync: Query messages using 'q' parameter to find emails from or to the lead
			query = f"from:{lead_email} OR to:{lead_email}"
			results = service.users().messages().list(userId="me", q=query).execute()
			
			messages = results.get("messages", [])
			
			for msg in messages:
				process_message(service, msg["id"], {lead_email}, google_mail.user)
				
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Google Mail Lead Sync Failed: {gm_name} for {lead_email}")
