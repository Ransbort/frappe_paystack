import frappe
from frappe.utils import fmt_money, get_url_to_form
from frappe_paystack.utils import require_portal_login, resolve_customer_by_email

PAYMENT_LOG = "Paystack Payment Log"


def get_context(context):
    context.title = "Payment Status"
    if require_portal_login():
        return context

    reference = frappe.form_dict.get("reference")

    # Fallback for /my-payment/<name> links if the website_route_rules
    # entry (hooks.py) doesn't populate form_dict.reference for some
    # reason - same defensive pattern paystack-checkout's index.py uses
    # for its own path-segment links.
    if not reference:
        path = frappe.local.request.path or ""
        parts = [p for p in path.split("/") if p]
        if parts and parts[-1] != "my-payment":
            reference = parts[-1]

    context.reference = reference
    context.doc = None

    if reference and frappe.db.exists(PAYMENT_LOG, reference):
        log = frappe.get_doc(PAYMENT_LOG, reference)
        if _owns_payment(log):
            data = log.get_data()
            data.update(
                {
                    "amount_paid": log.amount_paid,
                    "currency_paid": log.currency_paid,
                    "payment_date": str(log.payment_date) if log.payment_date else None,
                    "transaction_id": log.transaction_id,
                    "modified": str(log.modified) if log.modified else None,
                    "order_amount_fmt": fmt_money(data.get("grand_total"), currency=data.get("order_currency")),
                    "amount_fmt": fmt_money(data.get("payment_amount"), currency=data.get("currency")),
                    "invoice_url": (
                        get_url_to_form(log.linked_doctype, log.linked_docname)
                        if log.linked_doctype and log.linked_docname
                        else None
                    ),
                }
            )
            if log.amount_paid:
                data["amount_paid_fmt"] = fmt_money(
                    log.amount_paid, currency=log.currency_paid or data.get("currency")
                )
            context.doc = data
        # If it exists but isn't theirs, fall through with context.doc
        # still None - same "not found" message either way, so a guessed
        # reference can't be used to distinguish someone else's payment
        # from one that simply doesn't exist.

    context.doc_json = frappe.as_json(context.doc) if context.doc else "null"
    context.reference_json = frappe.as_json(context.reference) if context.reference else "null"
    return context


def _owns_payment(log):
    """A payer should only ever see their own payment status here - never
    someone else's by guessing/incrementing a reference in the URL.
    Mirrors the ownership check my-payments/index.py's payment-history
    query already applies to the list view.
    """
    if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
        return True
    # Was frappe.db.get_value("Contact", {"email_id": ...}, "customer") -
    # "customer" isn't a real column on Contact; see
    # resolve_customer_by_email's docstring in frappe_paystack/utils.py.
    customer = resolve_customer_by_email(frappe.session.user)
    if not customer or not log.linked_doctype or not log.linked_docname:
        return False
    doc_customer = frappe.db.get_value(log.linked_doctype, log.linked_docname, "customer")
    return bool(doc_customer) and doc_customer == customer
