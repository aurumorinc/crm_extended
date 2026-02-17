# Copyright (c) 2026, Aurumor and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class SequenceContact(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		reference_docname: DF.DynamicLink
		reference_doctype: DF.Link
		sequence: DF.Link
	# end: auto-generated types

	def validate(self):
		self.set_apollo_ref_code()
		self.check_duplicate()

	def set_apollo_ref_code(self):
		if self.reference_doctype == "CRM Lead" and self.reference_name:
			self.reference_apollo_ref_code = frappe.db.get_value("CRM Lead", self.reference_name, "apollo_ref_code")
		if self.sequence:
			self.sequence_apollo_ref_code = frappe.db.get_value("Sequence", self.sequence, "apollo_ref_code")

	def onload(self):
		if self.reference_doctype == "CRM Lead" and self.reference_name:
			self.reference_apollo_ref_code = frappe.db.get_value("CRM Lead", self.reference_name, "apollo_ref_code")
		if self.sequence:
			self.sequence_apollo_ref_code = frappe.db.get_value("Sequence", self.sequence, "apollo_ref_code")

	def check_duplicate(self):
		if not (self.sequence and self.reference_doctype and self.reference_name):
			return

		duplicate = frappe.db.exists(
			"Sequence Contact",
			{
				"sequence": self.sequence,
				"reference_doctype": self.reference_doctype,
				"reference_name": self.reference_name,
				"name": ["!=", self.name],
			},
		)

		if duplicate:
			frappe.throw(
				_("{0} {1} is already added to Sequence {2}").format(
					self.reference_doctype,
					frappe.bold(self.reference_name),
					frappe.bold(self.sequence),
				),
				title=_("Duplicate Entry"),
			)

def update_apollo_ref_code(doc, method):
	sequence_contacts = frappe.get_all(
		"Sequence Contact",
		filters={"reference_doctype": "CRM Lead", "reference_name": doc.name},
	)

	for sequence_contact in sequence_contacts:
		frappe.db.set_value(
			"Sequence Contact",
			sequence_contact.name,
			"reference_apollo_ref_code",
			doc.apollo_ref_code,
		)

def update_sequence_apollo_ref_code(doc, method):
	sequence_contacts = frappe.get_all(
		"Sequence Contact",
		filters={"sequence": doc.name},
	)

	for sequence_contact in sequence_contacts:
		frappe.db.set_value(
			"Sequence Contact",
			sequence_contact.name,
			"sequence_apollo_ref_code",
			doc.apollo_ref_code,
		)
		# Trigger update for Sequence Email
		contact_doc = frappe.get_doc("Sequence Contact", sequence_contact.name)
		contact_doc.sequence_apollo_ref_code = doc.apollo_ref_code
		# This will trigger the hook for Sequence Contact -> Sequence Email
		contact_doc.save()
