import frappe
from frappe.utils import get_url_to_form, fmt_money
from frappe_paystack.utils import require_portal_login, resolve_customer_by_email


def get_context(context):
    context.title = "My Payments"
    if require_portal_login("/my-payments"):
        return context
    # Was frappe.db.get_value("Contact", {"email_id": ...}, "customer") -
    # "customer" isn't a real column on Contact (a Customer links to a
    # Contact via the Dynamic Link child table, not a fetched field), so
    # this would have raised an "Unknown column" SQL error the first time
    # a real Contact record hit this page. See resolve_customer_by_email's
    # docstring in frappe_paystack/utils.py.
    customer = resolve_customer_by_email(frappe.session.user)

    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"customer": customer, "status": ["in", ["Unpaid", "Partly Paid"]]},
        fields=["name", "posting_date", "due_date", "outstanding_amount", "currency"],
        order_by="due_date asc",
    )
    for inv in invoices:
        inv["form_url"] = get_url_to_form("Sales Invoice", inv["name"])
        inv["outstanding_fmt"] = fmt_money(inv["outstanding_amount"], currency=inv["currency"])
        inv["posting_date"] = str(inv["posting_date"]) if inv["posting_date"] else ""
        inv["due_date"] = str(inv["due_date"]) if inv["due_date"] else ""

    # Scope payment history to this customer's own invoices. The old query
    # filtered only on linked_doctype="Sales Invoice" with no ownership
    # check at all, so any logged-in customer with a Contact record could
    # see every other customer's payment references, amounts and statuses
    # here - not just their own. customer_invoice_names covers every
    # invoice ever raised against this customer (not just Unpaid/Partly
    # Paid like the list above), since payment history should include
    # settled ones too.
    customer_invoice_names = frappe.get_all(
        "Sales Invoice", filters={"customer": customer}, pluck="name"
    ) if customer else []

    payments = frappe.get_all(
        "Paystack Payment Log",
        filters={
            "linked_doctype": "Sales Invoice",
            "linked_docname": ["in", customer_invoice_names or ["__none__"]],
        },
        # NOTE: was ["name", "reference", ...] - "reference" isn't a real
        # column on this doctype (see paystack_payment_log.json), so this
        # get_all() call would have errored with an unknown-column SQL
        # error the moment this page actually loaded. The reference shown
        # to payers everywhere else (get_data(), the checkout page's
        # payment link) is just the docname - so that's "name" here too.
        fields=["name", "linked_docname", "amount", "currency", "status", "modified"],
        order_by="modified desc",
        limit=20,
    )
    for log in payments:
        log["form_url"] = get_url_to_form("Sales Invoice", log["linked_docname"])
        log["detail_url"] = f"/my-payment/{log['name']}"
        log["amount_fmt"] = fmt_money(log["amount"], currency=log["currency"])
        log["modified"] = str(log["modified"]) if log["modified"] else ""

    context.invoices = invoices
    context.payments = payments
    context.customer = customer
    context.invoices_json = frappe.as_json(invoices)
    context.payments_json = frappe.as_json(payments)
    return context
