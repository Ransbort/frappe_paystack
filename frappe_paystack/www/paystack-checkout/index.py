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
        context.doc = None
    else:
        if frappe.db.exists(PAYMENT_LOG, {"name": reference}):
            doc = frappe.get_doc(PAYMENT_LOG, reference)
            context.doc = doc.get_data()
            context.reference = reference
        else:
            context.reference = None
            context.doc = None

    # index.html used to embed this page's state with `{{ doc | safe }}`
    # straight into a <script> tag. That relied on Python's dict repr
    # happening to look enough like a JS object literal to parse (single
    # quotes are valid JS, but None/True/False aren't - str(None) is the
    # bareword `None`, which is a JS SyntaxError) - and it broke outright
    # whenever doc was unset, since `context.doc` was never assigned in
    # that branch and an undefined Jinja var renders as '', producing
    # `window.doc = ;`. Precomputing real JSON here (rendered with
    # frappe.as_json(...) | safe in the template) is what the Vue rewrite
    # actually consumes as its initial state.
    context.doc_json = frappe.as_json(context.doc) if context.doc else "null"
    context.reference_json = frappe.as_json(context.reference) if context.reference else "null"

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
