const isEmail = str => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(str);
const { createApp } = Vue;

createApp({
  delimiters: ['[[', ']]'],
  data() {
    return {
      reference: window.reference,
      doc: window.doc,
      paying: false,
    };
  },
  computed: {
    // Same precedence as the old Jinja if/elif chain this page used to
    // render server-side (see git history on index.html): gateway check
    // first, then "payment not settled but the order already is"
    // (invalid/expired), then "either side is settled" (completed), then
    // Failed, else the normal pay screen.
    pageState() {
      if (!this.reference || !this.doc) return 'no-reference';
      const d = this.doc;
      if (!d.public_key) return 'gateway-inactive';
      const orderSettled = ['Completed', "Closed'", 'Paid'].includes(d.order_status);
      const paymentSettled = ['Completed', 'Processed'].includes(d.status);
      if (!paymentSettled && orderSettled) return 'invalid-expired';
      if (paymentSettled || orderSettled) return 'completed';
      if (d.status === 'Failed') return 'failed';
      return 'summary';
    },
  },
  methods: {
    formatCurrency(amount, currency) {
      if (currency) {
        return Intl.NumberFormat('en-US', { currency, style: 'currency' }).format(amount);
      }
      return Intl.NumberFormat('en-US').format(amount);
    },
    payWithPaystack() {
      const me = this;
      const handler = PaystackPop.setup({
        key: this.doc.public_key,
        amount: this.doc.payment_amount * 100,
        // ref: a pseudo-unique reference. Leave unset so our API generates one for you.
        currency: this.doc.currency,
        email: this.doc.email,
        metadata: {
          reference_doctype: this.doc.reference_doctype,
          reference_docname: this.doc.reference_docname,
          customer: this.doc.customer,
          reference: this.doc.reference,
          email: this.doc.email,
        },
        // label: "Optional string that replaces customer email"
        onClose: function () {
          me.paying = false;
          Swal.fire('Payment Terminated', 'You closed the payment window before completing it.', 'info');
        },
        callback: function (response) {
          // Stays "paying" through verification, not just until the popup
          // closes - the popup reporting success isn't the same as our
          // own record being updated yet.
          // Verify synchronously rather than relying solely on the
          // webhook, which can't reach a local/dev host without a
          // public tunnel — and redirect afterward so the page
          // re-renders with the real status instead of dead-ending
          // on this alert.
          frappe.call('frappe_paystack.api.verify_transaction', {
            reference: me.doc.reference,
            trxref: response.reference,
          }).then(res => {
            const status = res.message && res.message.status;
            // Matches pageState()'s own paymentSettled check above ('Completed'
            // is a real success too, not just 'Processed') - verify_transaction()
            // sets the Paystack Payment Log to "Processed" and save()s it, but
            // for a Sales Invoice that gets fully settled, the log's own
            // on_update() runs inside that same save() and immediately bumps
            // status again, straight through to "Completed" (see
            // paystack_payment_log.py), before save() returns here. So the
            // normal, fully-paid-in-one-shot case comes back as "Completed",
            // not "Processed" - checking only 'Processed' treated every real
            // success as a failure and flashed "Payment Failed" right after a
            // successful charge.
            if (status === 'Processed' || status === 'Completed') {
              Swal.fire(
                'Successful',
                'Your payment was successful, we will issue you receipt shortly.',
                'success'
              ).then(() => {
                window.location.reload();
              });
            } else {
              Swal.fire(
                'Payment Failed',
                'We could not confirm your payment. Please contact support if you were charged.',
                'error'
              ).then(() => {
                window.location.reload();
              });
            }
          }).catch(() => {
            Swal.fire(
              'Verification Error',
              'Your payment may have succeeded but we could not confirm it automatically. Please contact support with your reference.',
              'warning'
            ).then(() => {
              window.location.reload();
            });
          });
        },
      });
      handler.openIframe();
    },
    getData() {
      const me = this;
      this.paying = true;
      frappe.call('frappe_paystack.api.validate_payment_link', { docname: this.doc.reference }).then(res => {
        const data = res.message || {};
        // Was `data.order_status in [...]` in the original - JS `in`
        // tests object/array *keys*, not membership, so that check never
        // actually matched anything. Fixed to .includes() like the other
        // two branches already correctly used.
        let error = '';
        if (['Completed', "Closed'", 'Paid'].includes(data.order_status)) {
          error = 'Paid or Completed';
        } else if (['Processed', 'Completed'].includes(data.status)) {
          error = 'Payment already processed.';
        } else if ([0, 2].includes(data.order_docstatus)) {
          error = 'Payment link expired or invalid.';
        }
        if (error) {
          window.location.reload();
          return;
        }
        if (me.doc.email) {
          me.payWithPaystack();
        } else {
          me.paying = false;
          Swal.fire({
            title: 'Your email',
            input: 'text',
            inputAttributes: {
              autocapitalize: 'off',
            },
            showCancelButton: false,
            confirmButtonText: 'Continue',
            showLoaderOnConfirm: true,
            allowOutsideClick: () => !Swal.isLoading(),
          }).then((value) => {
            if (value.isConfirmed) {
              if (isEmail(value.value)) {
                me.doc.email = value.value;
                me.paying = true;
                me.payWithPaystack();
              } else {
                Swal.fire({
                  title: 'Invalid Email',
                  text: 'Retry',
                  icon: 'warning',
                });
              }
            }
          });
        }
      }).catch(() => {
        me.paying = false;
      });
    },
  },
}).mount('#app');
