// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Google Mail', {
	refresh: function(frm) {
		if (!frm.doc.__islocal && frm.doc.enable) {
			frm.add_custom_button(__('Sync Now'), function() {
				frappe.call({
					method: 'crm_extended.crm_extended.doctype.google_mail.google_mail.sync',
					args: {
						google_mail_name: frm.doc.name
					},
					freeze: true,
					callback: function(r) {
						if (!r.exc) {
							frappe.msgprint(__('Sync initiated in background'));
						}
					}
				});
			});
		}
	},

	authorize_google_mail_access: function(frm) {
		let reauthorize = 0;
		if(frm.doc.authorization_code) {
			reauthorize = 1;
		}

		frappe.call({
			method: "crm_extended.crm_extended.doctype.google_mail.google_mail.authorize_access",
			args: {
				google_mail_name: frm.doc.name,
				reauthorize: reauthorize
			},
			freeze: true,
			callback: function(r) {
				if(!r.exc && r.message && r.message.url) {
					window.location.href = r.message.url;
				}
			}
		});
	}
});
