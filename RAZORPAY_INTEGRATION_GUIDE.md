# 💳 Razorpay Integration Guide

## 🎯 Overview
This guide explains how to integrate Razorpay payment gateway with the Library Connekto booking system.

## 🔧 Backend Setup

### 1. Configuration
Update your environment variables or `config.py`:

```python
# In config.py or environment variables
RAZORPAY_KEY_ID = "rzp_test_your_key_id_here"
RAZORPAY_KEY_SECRET = "your_secret_key_here"
```

### 2. New API Endpoints

#### Create Razorpay Order
```http
POST /api/v1/booking/create-razorpay-order
Content-Type: application/json

{
  "booking_id": "booking-uuid-here",
  "amount": 100000,  // ₹1000 in paise
  "currency": "INR",
  "notes": {
    "custom_field": "value"
  }
}
```

**Response:**
```json
{
  "id": "order_razorpay_id",
  "amount": 100000,
  "currency": "INR",
  "receipt": "booking_booking-uuid-here",
  "status": "created",
  "created_at": 1640995200,
  "notes": {
    "booking_id": "booking-uuid-here",
    "student_name": "Student Name",
    "library_id": "library-uuid-here"
  }
}
```

#### Verify Payment
```http
POST /api/v1/booking/verify-razorpay-payment
Content-Type: application/json

{
  "booking_id": "booking-uuid-here",
  "razorpay_order_id": "order_razorpay_id",
  "razorpay_payment_id": "pay_razorpay_id",
  "razorpay_signature": "signature_from_razorpay"
}
```

## 📱 Frontend Integration

### 1. Install Razorpay SDK
```html
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
```

### 2. JavaScript Integration
```javascript
// Function to create and process payment
async function processRazorpayPayment(bookingId, amount) {
  try {
    // Step 1: Create Razorpay order
    const orderResponse = await fetch('/api/v1/booking/create-razorpay-order', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        booking_id: bookingId,
        amount: amount * 100, // Convert to paise
        currency: 'INR'
      })
    });

    if (!orderResponse.ok) {
      throw new Error('Failed to create payment order');
    }

    const order = await orderResponse.json();

    // Step 2: Open Razorpay checkout
    const options = {
      key: 'rzp_test_your_key_id_here', // Your Razorpay key
      amount: order.amount,
      currency: order.currency,
      name: 'Library Connekto',
      description: 'Seat Booking Payment',
      order_id: order.id,
      handler: async function (response) {
        // Step 3: Verify payment
        await verifyPayment(bookingId, response);
      },
      prefill: {
        name: 'Student Name',
        email: 'student@example.com',
        contact: '9876543210'
      },
      theme: {
        color: '#3399cc'
      }
    };

    const rzp = new Razorpay(options);
    rzp.open();

  } catch (error) {
    console.error('Payment error:', error);
    alert('Payment failed. Please try again.');
  }
}

// Function to verify payment
async function verifyPayment(bookingId, razorpayResponse) {
  try {
    const verifyResponse = await fetch('/api/v1/booking/verify-razorpay-payment', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        booking_id: bookingId,
        razorpay_order_id: razorpayResponse.razorpay_order_id,
        razorpay_payment_id: razorpayResponse.razorpay_payment_id,
        razorpay_signature: razorpayResponse.razorpay_signature
      })
    });

    if (verifyResponse.ok) {
      const result = await verifyResponse.json();
      alert('Payment successful! You have been added to the library.');
      // Redirect to success page or dashboard
      window.location.href = '/student/dashboard';
    } else {
      throw new Error('Payment verification failed');
    }
  } catch (error) {
    console.error('Verification error:', error);
    alert('Payment verification failed. Please contact support.');
  }
}
```

### 3. React Integration Example
```jsx
import { useEffect } from 'react';

const PaymentComponent = ({ bookingId, amount }) => {
  useEffect(() => {
    // Load Razorpay script
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    document.body.appendChild(script);

    return () => {
      document.body.removeChild(script);
    };
  }, []);

  const handlePayment = async () => {
    // Same logic as above JavaScript example
    await processRazorpayPayment(bookingId, amount);
  };

  return (
    <button onClick={handlePayment} className="bg-blue-600 text-white px-6 py-2 rounded">
      Pay with Razorpay
    </button>
  );
};
```

## 🔄 Complete Payment Flow

### 1. Booking Submission
```javascript
// Student submits booking
const booking = await apiClient.post('/booking/anonymous-seat-booking', bookingData);
// Status: 'pending'
```

### 2. Admin Approval
```javascript
// Admin approves booking
await apiClient.put(`/booking/seat-bookings/${bookingId}`, { status: 'approved' });
// Status: 'approved' (no student account created yet)
```

### 3. Payment Processing
```javascript
// Student initiates payment
await processRazorpayPayment(bookingId, amount);
// Creates Razorpay order → Opens checkout → Verifies payment
```

### 4. Payment Verification
```javascript
// After successful payment
// Status: 'active' + Student account created + Subscription activated
```

## 🔒 Security Features

### 1. Payment Signature Verification
- All payments are verified using Razorpay's signature verification
- Prevents payment tampering and fraud

### 2. Order Validation
- Orders are created only for approved bookings
- Duplicate payment prevention
- Amount validation

### 3. Secure API Endpoints
- Proper authentication and authorization
- Input validation and sanitization
- Error handling and logging

## 🧪 Testing

### 1. Test Mode
Use Razorpay test credentials:
- Key ID: `rzp_test_...`
- Test cards available in Razorpay dashboard

### 2. Test Cards
```
Card Number: 4111 1111 1111 1111
Expiry: Any future date
CVV: Any 3 digits
```

### 3. Test Scenarios
- Successful payment
- Failed payment
- Network errors
- Invalid signatures

## 📊 Error Handling

### Common Errors
1. **Booking not found**: Invalid booking ID
2. **Booking not approved**: Payment attempted before approval
3. **Payment already completed**: Duplicate payment attempt
4. **Invalid signature**: Payment verification failed

### Error Responses
```json
{
  "detail": "Booking must be approved before payment"
}
```

## 🚀 Production Deployment

### 1. Environment Variables
```bash
RAZORPAY_KEY_ID=rzp_live_your_live_key_id
RAZORPAY_KEY_SECRET=your_live_secret_key
```

### 2. Webhook Setup (Optional)
Configure Razorpay webhooks for additional security:
- Payment captured
- Payment failed
- Refund processed

### 3. Monitoring
- Monitor payment success rates
- Track failed payments
- Set up alerts for critical errors

## 📞 Support

For Razorpay integration issues:
1. Check Razorpay dashboard for transaction logs
2. Verify API credentials
3. Test with Razorpay test environment
4. Contact Razorpay support for payment gateway issues

---

**🎉 Your Razorpay integration is now ready! Students can make secure online payments for their library seat bookings.**

