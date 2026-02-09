# -*- coding: utf-8 -*-
# Copyright (c) 2026, hello@aurumor.com and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime

class JobOpening(Document):
    def before_save(self):
        self.set_state()

    def set_state(self):
        # Fix: Added as_datetime=True to ensure both sides are datetime objects
        if self.synced and not (
            get_datetime(self.modified or self.creation)
            > add_to_date(self.synced, seconds=30, as_datetime=True)
        ):
            self.state = "Current"
        else:
            self.state = "Draft"