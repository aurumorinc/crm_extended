# Copyright (c) 2026, Aurumor and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class SequenceEmail(Document):
	def validate(self):
		self.set_apollo_ref_code()

	def set_apollo_ref_code(self):
		if self.reference_name:
			self.reference_apollo_ref_code = frappe.db.get_value("CRM Lead", self.reference_name, "apollo_ref_code")
		if self.sequence_contact:
			self.sequence_apollo_ref_code = frappe.db.get_value("Sequence Contact", self.sequence_contact, "sequence_apollo_ref_code")

	def onload(self):
		if self.reference_name:
			self.reference_apollo_ref_code = frappe.db.get_value("CRM Lead", self.reference_name, "apollo_ref_code")
		if self.sequence_contact:
			self.sequence_apollo_ref_code = frappe.db.get_value("Sequence Contact", self.sequence_contact, "sequence_apollo_ref_code")

def update_apollo_ref_code(doc, method):
	sequence_emails = frappe.get_all(
		"Sequence Email",
		filters={"reference_name": doc.name},
	)

	for sequence_email in sequence_emails:
		frappe.db.set_value(
			"Sequence Email",
			sequence_email.name,
			"reference_apollo_ref_code",
			doc.apollo_ref_code,
		)

def update_sequence_apollo_ref_code(doc, method):
	sequence_emails = frappe.get_all(
		"Sequence Email",
		filters={"sequence_contact": doc.name},
	)

	for sequence_email in sequence_emails:
		frappe.db.set_value(
			"Sequence Email",
			sequence_email.name,
			"sequence_apollo_ref_code",
			doc.sequence_apollo_ref_code,
		)
