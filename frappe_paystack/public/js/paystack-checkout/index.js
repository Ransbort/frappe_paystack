const isEmail = str => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(str);
const { createApp } = Vue
createApp({
  delimiters: ['[%', '%]'],
  data() {
    return {
        id: '',
        payment_data: {},
        gateway: '',
        showDiv: false,
        doc: window.doc,
    }
  },
  methods: {
    payWithPaystack(){
        let me = this;
        let handler = PaystackPop.setup({
            key: doc.public_key, 
            amount: doc.payment_amount * 100,
            // ref: me.payment_data.name+'_'+Math.floor((Math.random() * 1000000000) + 1), // generates a pseudo-unique reference. Please replace with a reference you generated. Or remove the line entirely so our API will generate one for you
            currency: doc.currency,
            email: doc.email,
            metadata: {
                reference_doctype:doc.reference_doctype,
                reference_docname:doc.reference_docname,
                customer:doc.customer,
                reference:doc.reference,
                email: doc.email
            },
            // label: "Optional string that replaces customer email"
            onClose: function(){
                alert('Payment Terminated.');
            },
            callback: function(response){
                $('#paymentBTN').hide();
                // Verify synchronously rather than relying solely on the
                // webhook, which can't reach a local/dev host without a
                // public tunnel — and redirect afterward so the page
                // re-renders with the real status instead of dead-ending
                // on this alert.
                frappe.call("frappe_paystack.api.verify_transaction", {
                    reference: doc.reference,
                    trxref: response.reference
                }).then(res => {
                    let status = res.message && res.message.status;
                    if (status === "Processed") {
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
            }
        });
        handler.openIframe();
    },
    getData(){
        let me = this;
        frappe.call("frappe_paystack.api.validate_payment_link", {"docname": doc.reference}).then(res=>{
            let data = res.message;
            if (data.order_status in ["Completed", "Closed'", "Paid"]) {
                errors = "Paid or Completed"
            } else if (["Processed", "Completed"].includes(data.status)){
                errors = "Payment already processed."
            } else if ([0, 2].includes(data.order_docstatus)) {
                errors = "Payment link expired or invalid."
            } else {
                errors = ""
            }
            if (errors){
                window.location.reload();
            } else {
                if (doc.email){
                    this.payWithPaystack();
                } else {
                    Swal.fire({
                        title: "Your email",
                        input: "text",
                        inputAttributes: {
                            autocapitalize: "off"
                        },
                        showCancelButton: false,
                        confirmButtonText: "Continue",
                        showLoaderOnConfirm: true,
                        allowOutsideClick: () => !Swal.isLoading()
                    }).then((value) => {
                        if (value.isConfirmed) {
                            if (isEmail(value.value)){
                                doc.email = value.value;
                                me.payWithPaystack();
                            } else {
                                Swal.fire({
                                    title: "Invalid Email",
                                    text: "Retry",
                                    icon: "warning"
                                });
                            }
                        }
                        
                    });
                }
            }
        })
    },
    formatCurrency(amount, currency){
        if(currency){
            return Intl.NumberFormat('en-US', {currency:currency, style:'currency'}).format(amount);
        } else {
            return Intl.NumberFormat('en-US').format(amount);
        }
    }
  },
  mounted(){
  }
}).mount('#app')
document.querySelector("paymentBTN")
