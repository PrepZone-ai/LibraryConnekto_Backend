from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any
from datetime import datetime, timedelta
import uuid
import logging

from app.database import get_db
from app.auth.dependencies import get_current_student
from app.models.student import Student
from app.models.subscription import SubscriptionPlan
from app.services.payment_service import PaymentService
from app.services.subscription_notification_service import SubscriptionNotificationService
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/create-order")
async def create_payment_order(
    order_data: dict,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Create a payment order for subscription purchase"""
    try:
        # Validate order data
        plan_id = order_data.get("plan_id")
        amount = order_data.get("amount")
        
        if not plan_id or not amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Plan ID and amount are required"
            )
        
        # Verify plan exists and is active
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.library_id == current_student.admin_id,
            SubscriptionPlan.is_active == True
        ).first()
        
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription plan not found"
            )
        
        # Verify amount matches plan price
        if amount != plan.price * 100:  # Convert to paise
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount does not match plan price"
            )
        
        # Create payment order
        payment_service = PaymentService()
        receipt = f"sub_{current_student.id}_{plan_id}_{datetime.now().timestamp()}"
        
        order_result = payment_service.create_order(
            amount=amount,
            currency="INR",
            receipt=receipt
        )
        
        if not order_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create payment order"
            )
        
        return {
            "success": True,
            "order_id": order_result["order"]["id"],
            "amount": order_result["order"]["amount"],
            "currency": order_result["order"]["currency"],
            "receipt": order_result["order"]["receipt"],
            "message": "Payment order created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating payment order: {str(e)}"
        )

@router.post("/verify")
async def verify_payment(
    verification_data: dict,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    """Verify payment and extend subscription"""
    try:
        # Extract verification data
        razorpay_order_id = verification_data.get("razorpay_order_id")
        razorpay_payment_id = verification_data.get("razorpay_payment_id")
        razorpay_signature = verification_data.get("razorpay_signature")
        plan_id = verification_data.get("plan_id")
        
        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, plan_id]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required verification data"
            )
        
        # Verify payment signature
        payment_service = PaymentService()
        verification_result = payment_service.verify_payment(
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature
        )
        
        if not verification_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment verification failed"
            )
        
        # Get subscription plan
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.library_id == current_student.admin_id,
            SubscriptionPlan.is_active == True
        ).first()
        
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription plan not found"
            )
        
        # Extend subscription
        if current_student.subscription_end and current_student.subscription_end > datetime.now():
            # Extend existing subscription
            new_end_date = current_student.subscription_end + timedelta(days=30)
        else:
            # Start new subscription
            new_end_date = datetime.now() + timedelta(days=30)
        
        # Update student subscription
        current_student.subscription_end = new_end_date
        current_student.subscription_status = "Active"
        
        db.commit()
        db.refresh(current_student)
        
        # Send confirmation notification
        notification_service = SubscriptionNotificationService(db)
        notification_service.notification_service.create_system_notification(
            student_id=current_student.id,
            admin_id=current_student.admin_id,
            title="✅ Subscription Renewed Successfully!",
            message=f"Your {plan.plan_name} subscription has been renewed. Thank you for continuing with us!",
            priority="medium"
        )
        
        # Send payment confirmation email
        try:
            email_service = EmailService()
            library_name = current_student.admin.admin_details.library_name if current_student.admin and current_student.admin.admin_details else "Library"
            student_name = current_student.name or f"{current_student.first_name or ''} {current_student.last_name or ''}".strip()
            
            # Format subscription end date
            subscription_end_formatted = new_end_date.strftime("%d %B %Y")
            
            email_result = email_service.send_payment_confirmation_email(
                email=current_student.email,
                student_name=student_name,
                library_name=library_name,
                plan_name=plan.plan_name,
                amount=plan.price,
                payment_id=razorpay_payment_id,
                subscription_end=subscription_end_formatted,
                base_url="http://localhost:3000/"  # Update with your frontend URL
            )
            
            if not email_result.get("success", False):
                logger.warning(f"Failed to send payment confirmation email: {email_result.get('error', 'Unknown error')}")
            
        except Exception as e:
            logger.error(f"Error sending payment confirmation email: {e}")
            # Don't fail the payment verification if email fails
        
        return {
            "success": True,
            "payment_id": razorpay_payment_id,
            "order_id": razorpay_order_id,
            "subscription_end": new_end_date.isoformat(),
            "plan_name": plan.plan_name,
            "message": "Payment verified and subscription renewed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying payment: {str(e)}"
        )

@router.get("/methods")
async def get_payment_methods():
    """Get available payment methods"""
    return {
        "success": True,
        "payment_methods": [
            {
                "id": "razorpay",
                "name": "Razorpay",
                "description": "Credit/Debit Cards, UPI, Net Banking, Wallets",
                "icon": "💳",
                "enabled": True
            }
        ]
    }

@router.get("/status/{payment_id}")
async def get_payment_status(
    payment_id: str,
    current_student: Student = Depends(get_current_student)
):
    """Get payment status"""
    try:
        payment_service = PaymentService()
        result = payment_service.get_payment_details(payment_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        return {
            "success": True,
            "payment": result["payment"],
            "message": "Payment details retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching payment details: {str(e)}"
        )
