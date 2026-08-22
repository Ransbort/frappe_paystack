const { createApp } = Vue;

createApp({
  delimiters: ['[[', ']]'],
  data() {
    return {
      reference: window.reference,
      doc: window.doc,
    };
  },
  computed: {
    pageState() {
      return this.doc ? 'found' : 'not-found';
    },
    isSettled() {
      return !!this.doc && ['Completed', 'Processed'].includes(this.doc.status);
    },
    canRetry() {
      return !!this.doc && ['Pending', 'Failed'].includes(this.doc.status);
    },
    statusBadgeClass() {
      if (!this.doc) return '';
      if (this.isSettled) return 'pc-status-success';
      if (this.doc.status === 'Failed') return 'pc-status-failed';
      return 'pc-status-pending';
    },
    receiptUrl() {
      const params = new URLSearchParams({
        doctype: 'Paystack Payment Log',
        name: this.reference,
        format: 'Paystack Receipt',
        no_letterhead: '1',
      });
      return `/api/method/frappe.utils.print_format.download_pdf?${params.toString()}`;
    },
  },
}).mount('#app');
