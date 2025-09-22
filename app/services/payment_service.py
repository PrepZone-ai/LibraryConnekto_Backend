import razorpay
import hashlib
import hmac
import json
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self):
        self.razorpay_client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
    
    def create_order(self, amount: int, currency: str = "INR", receipt: str = None) -> Dict[str, Any]:
        """Create a Razorpay order"""
        try:
            data = {
                "amount": amount,
                "currency": currency,
                "receipt": receipt or f"receipt_{datetime.now().timestamp()}"
            }
            
            order = self.razorpay_client.order.create(data=data)
            
            return {
                "success": True,
                "order": order,
                "message": "Order created successfully"
            }
            
        except Exception as e:
            logger.error(f"Error creating Razorpay order: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to create order"
            }
    
    def verify_payment(self, razorpay_order_id: str, razorpay_payment_id: str, 
                      razorpay_signature: str) -> Dict[str, Any]:
        """Verify Razorpay payment signature"""
        try:
            # Create the signature string
            body = f"{razorpay_order_id}|{razorpay_payment_id}"
            
            # Generate expected signature
            expected_signature = hmac.new(
                settings.RAZORPAY_KEY_SECRET.encode('utf-8'),
                body.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Verify signature
            if hmac.compare_digest(expected_signature, razorpay_signature):
                return {
                    "success": True,
                    "message": "Payment verified successfully",
                    "payment_id": razorpay_payment_id,
                    "order_id": razorpay_order_id
                }
            else:
                return {
                    "success": False,
                    "error": "Invalid signature",
                    "message": "Payment verification failed"
                }
                
        except Exception as e:
            logger.error(f"Error verifying payment: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Payment verification failed"
            }
    
    def get_payment_details(self, payment_id: str) -> Dict[str, Any]:
        """Get payment details from Razorpay"""
        try:
            payment = self.razorpay_client.payment.fetch(payment_id)
            
            return {
                "success": True,
                "payment": payment,
                "message": "Payment details retrieved successfully"
            }
            
        except Exception as e:
            logger.error(f"Error fetching payment details: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to fetch payment details"
            }
    
    def refund_payment(self, payment_id: str, amount: int = None) -> Dict[str, Any]:
        """Refund a payment"""
        try:
            refund_data = {"payment_id": payment_id}
            if amount:
                refund_data["amount"] = amount
            
            refund = self.razorpay_client.payment.refund(payment_id, refund_data)
            
            return {
                "success": True,
                "refund": refund,
                "message": "Refund processed successfully"
            }
            
        except Exception as e:
            logger.error(f"Error processing refund: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to process refund"
            }
