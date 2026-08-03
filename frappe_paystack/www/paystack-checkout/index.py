import frappe

PAYMENT_LOG = "Paystack Payment Log"

def get_context(context):
    context.title = "Paystack Checkout"
    reference = frappe.form_dict.get("reference")

    # Fallback: some links may still be generated as
    # /paystack-checkout/<name> (path segment) rather than
    # /paystack-checkout?reference=<name> (query param). If no query
    # param was supplied, check for a trailing path segment so those
    # links don't dead-end on "Invalid Payment Reference".
    if not reference:
        path = frappe.local.request.path or ""
        parts = [p for p in path.split("/") if p]
        if parts and parts[-1] != "paystack-checkout":
            reference = parts[-1]

    if not reference:
        context.reference = None
    else:
        if frappe.db.exists(PAYMENT_LOG, {"name": reference}):
            doc = frappe.get_doc(PAYMENT_LOG, reference)
            context.doc = doc.get_data()
            context.reference = reference
        else:
            context.reference = None

    return context


@frappe.whitelist(allow_guest=True)
def get_payment_request(reference_doctype, reference_docname):
    if not (reference_doctype and reference_docname):
        return {'error':"Invalid payment link."}
    payment_request = frappe.db.get_value(
        reference_doctype, {
            "name":reference_docname,
            "docstatus":1,
            "status":["=", "Requested"],
            "payment_request_type": "Inward"
        }, 
        "*", as_dict=1
    )
    if not payment_request:
        return {'error':"Invalid payment link."}
    if payment_request.status=='Paid':
        return {'error':"Payment has already been made."}
    public_key = frappe.db.get_value(
        "Paystack Gateway Setting",
        {'enabled':1,},
        ["public_key"]
    )
    if not public_key:
        return {'error':"Payment method is unavailable at the moment, please contact us directly.."}
    payment_request.public_key = public_key
    return payment_request
