# -*- coding: utf-8 -*-
# Copyright (c) 2026, hello@aurumor.com and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime

class JobOpening(Document):
    def before_save(self):
        self.set_state()

    def set_state(self):
        # Fix: Ensure comparison between datetime objects
        if self.synced and not (
            get_datetime(self.modified or self.creation)
            > get_datetime(add_to_date(self.synced, seconds=30))
        ):
            self.state = "Current"
        else:
            self.state = "Draft"