import razorpay
from app.core.config import settings
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class RazorpayService:
    def __init__(self):
        self.client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
    
    def create_order(self, amount: int, currency: str = "INR", receipt: str = None, notes: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a Razorpay order
        
        Args:
            amount: Amount in paise (e.g., 1000 for ₹10)
            currency: Currency code (default: INR)
            receipt: Receipt ID for the order
            notes: Additional notes for the order
            
        Returns:
            Dict containing order details
        """
        try:
            order_data = {
                "amount": amount,
                "currency": currency,
                "receipt": receipt or f"receipt_{receipt}",
                "notes": notes or {}
            }
            
            order = self.client.order.create(data=order_data)
            logger.info(f"Razorpay order created: {order['id']}")
            
            return {
                "success": True,
                "order": order,
                "message": "Order created successfully"
            }
            
        except Exception as e:
            logger.error(f"Error creating Razorpay order: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to create order"
            }
    
    def verify_payment(self, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> Dict[str, Any]:
        """
        Verify Razorpay payment signature
        
        Args:
            razorpay_order_id: Order ID from Razorpay
            razorpay_payment_id: Payment ID from Razorpay
            razorpay_signature: Signature from Razorpay
            
        Returns:
            Dict containing verification result
        """
        try:
            # Create the signature string
            signature_string = f"{razorpay_order_id}|{razorpay_payment_id}"
            
            # Verify the signature
            is_verified = self.client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })
            
            if is_verified:
                logger.info(f"Payment verified successfully: {razorpay_payment_id}")
                return {
                    "success": True,
                    "verified": True,
                    "message": "Payment verified successfully"
                }
            else:
                logger.warning(f"Payment verification failed: {razorpay_payment_id}")
                return {
                    "success": False,
                    "verified": False,
                    "message": "Payment verification failed"
                }
                
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            return {
                "success": False,
                "verified": False,
                "error": str(e),
                "message": "Failed to verify payment"
            }
    
    def get_payment_details(self, payment_id: str) -> Dict[str, Any]:
        """
        Get payment details from Razorpay
        
        Args:
            payment_id: Payment ID from Razorpay
            
        Returns:
            Dict containing payment details
        """
        try:
            payment = self.client.payment.fetch(payment_id)
            logger.info(f"Payment details fetched: {payment_id}")
            
            return {
                "success": True,
                "payment": payment,
                "message": "Payment details fetched successfully"
            }
            
        except Exception as e:
            logger.error(f"Error fetching payment details: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to fetch payment details"
            }
    
    def refund_payment(self, payment_id: str, amount: int = None, notes: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Refund a payment
        
        Args:
            payment_id: Payment ID to refund
            amount: Amount to refund in paise (if None, full refund)
            notes: Refund notes
            
        Returns:
            Dict containing refund details
        """
        try:
            refund_data = {
                "payment_id": payment_id,
                "notes": notes or {}
            }
            
            if amount:
                refund_data["amount"] = amount
            
            refund = self.client.payment.refund(refund_data)
            logger.info(f"Refund created: {refund['id']}")
            
            return {
                "success": True,
                "refund": refund,
                "message": "Refund created successfully"
            }
            
        except Exception as e:
            logger.error(f"Error creating refund: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to create refund"
            }

# Global Razorpay service instance
razorpay_service = RazorpayService()

