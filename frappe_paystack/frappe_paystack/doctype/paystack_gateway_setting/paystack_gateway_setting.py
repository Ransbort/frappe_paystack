# Copyright (c) 2024, Ransford Borketey and contributors
# For license information, please see license.txt

from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.utils import call_hook_method, get_url, get_url_to_form
from frappe.model.document import Document

class PaystackGatewaySetting(Document):
	supported_currencies = ['NGN', 'GHS', 'ZAR', 'USD']
	
	def validate(self):
		self.check_enabled()

	def get_secret_key(self):
		return self.get_password('secret_key')

	def check_enabled(self):
		"""
			Ensure only one gateway is enabled for each gate type.
		"""
		if self.enabled:
			enabled_gateway = frappe.db.get_list(self.doctype, filters={
				"enabled":1,
				"company":self.company,
				"name":["!=", self.name]
			},
			fields=["name"])
			if enabled_gateway:
				frappe.throw(f"""
					Another gateway is enabled, disable it before enabling this one.<br>
					<a class="text-danger" href="{get_url_to_form(self.doctype, enabled_gateway[0].name)}">{enabled_gateway[0].name}</a>
				""")
	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(
				_(
					"Please select another payment method. Paystack does not support transactions in currency '{0}'"
				).format(currency)
			)
	
	def get_supported_currency(self):
		return self.supported_currencies
	
	def get_payment_url(self, **kwargs):
		# ERPNext core's Payment Request flow (payment_request.py:get_payment_url)
		# calls this method directly with its own kwarg set (payer_email,
		# payer_name, order_id, reference_doctype="Payment Request",
		# reference_docname=<Payment Request name>, ...) instead of going
		# through our create_payment_link()/Paystack Payment Log flow. That
		# meant no Paystack Payment Log ever got created for these links, so
		# index.py's `reference` lookup always failed ("Invalid Payment
		# Reference"). Detect that shape here and create/reuse a Paystack
		# Payment Log so both flows converge on the same resolvable
		# ?reference= URL format.
		if kwargs.get("reference_doctype") == "Payment Request" or "order_id" in kwargs:
			return self._get_payment_url_from_payment_request(kwargs)
		return get_url(f"./paystack-checkout?{urlencode(kwargs)}")

	def _get_payment_url_from_payment_request(self, kwargs):
		pr_name = kwargs.get("reference_docname") or kwargs.get("order_id")
		payment_request = frappe.get_doc("Payment Request", pr_name)

		# The Payment Request's own reference_doctype/reference_name point
		# to the actual Sales Order / Sales Invoice being paid for — that's
		# what Paystack Payment Log.get_data() expects as linked_doctype/
		# linked_docname (not "Payment Request" itself).
		linked_doctype = payment_request.reference_doctype
		linked_docname = payment_request.reference_name

		# Reuse an existing pending log instead of creating a duplicate
		# every time the payment link is regenerated for the same order.
		existing = frappe.db.get_value(
			"Paystack Payment Log",
			{
				"linked_doctype": linked_doctype,
				"linked_docname": linked_docname,
				"status": "Pending",
			},
			"name",
		)
		if existing:
			log_name = existing
		else:
			log = frappe.new_doc("Paystack Payment Log")
			log.company = self.company
			log.linked_doctype = linked_doctype
			log.linked_docname = linked_docname
			log.amount = kwargs.get("amount")
			log.currency = kwargs.get("currency") or "NGN"
			log.status = "Pending"
			log.insert(ignore_permissions=True)
			log_name = log.name

		return get_url(f"./paystack-checkout?{urlencode({'reference': log_name})}")
