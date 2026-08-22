const { createApp } = Vue;

createApp({
  delimiters: ['[[', ']]'],
  data() {
    return {
      invoices: window.invoices || [],
      payments: window.payments || [],
      payingFor: null,
    };
  },
  methods: {
    receiptUrl(logName) {
      const params = new URLSearchParams({
        doctype: 'Paystack Payment Log',
        name: logName,
        format: 'Paystack Receipt',
        no_letterhead: '1',
      });
      return `/api/method/frappe.utils.print_format.download_pdf?${params.toString()}`;
    },
    payNow(inv) {
      this.payingFor = inv.name;
      frappe.call('frappe_paystack.api.create_payment_link', {
        doctype: 'Sales Invoice',
        docname: inv.name,
      }).then(r => {
        if (r.message) {
          window.open(r.message, '_blank');
        } else {
          Swal.fire('Error', 'Could not create a payment link. Please try again.', 'error');
        }
      }).catch(() => {
        Swal.fire('Error', 'Could not create a payment link. Please try again.', 'error');
      }).finally(() => {
        this.payingFor = null;
      });
    },
  },
}).mount('#app');
