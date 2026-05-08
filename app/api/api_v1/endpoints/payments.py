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
from app.utils.subscription_plan_scope import admin_details_id_for_user
from app.utils.razorpay_route import order_transfers_to_library
from app.models.admin import AdminDetails
from app.services.payment_service import PaymentService
from app.services.subscription_notification_service import SubscriptionNotificationService
from app.services.email_queue_service import enqueue_email_job
from app.services.qr_transfer_service import (
    get_transfer_by_reference,
    complete_transfer_payment,
    mark_transfer_payment_verified,
)
from app.services.razorpay_service import razorpay_service

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

        lib_id = admin_details_id_for_user(db, current_student.admin_id)
        if not lib_id:
            raise HTTPException(status_code=404, detail="Library not found for this account")

        # Verify plan exists and is active
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.library_id == lib_id,
            SubscriptionPlan.is_active == True
        ).first()
        
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription plan not found"
            )
        
        # Verify amount matches plan price
        if amount != float(plan.amount) * 100:  # Convert to paise
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount does not match plan price"
            )
        
        # Create payment order (settlement → library linked account when Route is enabled)
        payment_service = PaymentService()
        library_row = db.query(AdminDetails).filter(AdminDetails.id == lib_id).first()
        receipt = f"sub{str(current_student.id).replace('-', '')[:8]}_{int(datetime.now().timestamp())}"
        if len(receipt) > 40:
            receipt = receipt[:40]
        order_notes = {"plan_id": str(plan_id), "library_id": str(lib_id), "student_id": str(current_student.id)}
        transfers = order_transfers_to_library(
            library_row,
            amount_paise=int(amount),
            currency="INR",
            notes=order_notes,
        )
        order_result = payment_service.create_order(
            amount=int(amount),
            currency="INR",
            receipt=receipt,
            transfers=transfers,
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
        
        lib_id = admin_details_id_for_user(db, current_student.admin_id)
        if not lib_id:
            raise HTTPException(status_code=404, detail="Library not found for this account")

        # Get subscription plan
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.library_id == lib_id,
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
            message=f"Your {plan.months}-month subscription has been renewed. Thank you for continuing with us!",
            priority="medium"
        )
        
        # Queue payment confirmation email
        library_name = current_student.admin.admin_details.library_name if current_student.admin and current_student.admin.admin_details else "Library"
        student_name = current_student.name or f"{current_student.first_name or ''} {current_student.last_name or ''}".strip()
        subscription_end_formatted = new_end_date.strftime("%d %B %Y")
        enqueue_email_job(
            db=db,
            email_type="payment_confirmation",
            to_email=current_student.email,
            payload={
                "student_name": student_name,
                "library_name": library_name,
                "plan_name": f"{plan.months} month(s)",
                "amount": float(plan.amount),
                "payment_id": razorpay_payment_id,
                "subscription_end": subscription_end_formatted,
                "base_url": "http://localhost:3000/",
            },
        )
        
        return {
            "success": True,
            "payment_id": razorpay_payment_id,
            "order_id": razorpay_order_id,
            "subscription_end": new_end_date.isoformat(),
            "plan_name": f"{plan.months} month(s)",
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


@router.get("/transfer/{payment_reference}")
async def get_transfer_payment_details(
    payment_reference: str,
    db: Session = Depends(get_db),
):
    transfer = get_transfer_by_reference(db, payment_reference)
    student = transfer.student
    return {
        "transfer_id": str(transfer.id),
        "payment_reference": transfer.payment_reference,
        "amount": float(transfer.amount),
        "status": transfer.status,
        "student_name": student.name if student else None,
        "student_email": student.email if student else None,
        "razorpay_order_id": transfer.razorpay_order_id,
    }


@router.post("/transfer/create-order")
async def create_transfer_payment_order(
    body: dict,
    db: Session = Depends(get_db),
):
    payment_reference = body.get("payment_reference")
    if not payment_reference:
        raise HTTPException(status_code=400, detail="payment_reference is required")
    transfer = get_transfer_by_reference(db, payment_reference)
    if transfer.status == "completed":
        raise HTTPException(status_code=400, detail="Transfer already completed")
    if transfer.status not in {"payment_pending", "initiated", "paid"}:
        raise HTTPException(status_code=400, detail="Transfer cannot accept payment")

    if transfer.razorpay_order_id:
        return {
            "id": transfer.razorpay_order_id,
            "amount": int(float(transfer.amount) * 100),
            "currency": "INR",
            "receipt": f"transfer_{str(transfer.id)[:8]}",
            "notes": {"payment_reference": payment_reference},
        }

    amount_paise = int(float(transfer.amount) * 100)
    receipt = f"transfer_{str(transfer.id)[:8]}"
    if len(receipt) > 40:
        receipt = receipt[:40]
    target_library = db.query(AdminDetails).filter(
        AdminDetails.user_id == transfer.target_admin_id
    ).first()
    transfer_notes = {
        "payment_reference": payment_reference,
        "transfer_id": str(transfer.id),
    }
    route_transfers = order_transfers_to_library(
        target_library,
        amount_paise=amount_paise,
        currency="INR",
        notes=transfer_notes,
    )
    result = razorpay_service.create_order(
        amount=amount_paise,
        currency="INR",
        receipt=receipt,
        notes=transfer_notes,
        transfers=route_transfers,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=f"Failed to create Razorpay order: {result.get('error')}")

    order = result["order"]
    transfer.razorpay_order_id = order.get("id")
    db.commit()
    return order


@router.post("/transfer/verify")
async def verify_transfer_payment(
    body: dict,
    db: Session = Depends(get_db),
):
    payment_reference = body.get("payment_reference")
    razorpay_order_id = body.get("razorpay_order_id")
    razorpay_payment_id = body.get("razorpay_payment_id")
    razorpay_signature = body.get("razorpay_signature")
    if not all([payment_reference, razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        raise HTTPException(status_code=400, detail="Missing verification fields")

    verification = razorpay_service.verify_payment(
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        razorpay_signature=razorpay_signature,
    )
    if not verification.get("success") or not verification.get("verified"):
        raise HTTPException(status_code=400, detail="Payment verification failed")

    mark_transfer_payment_verified(
        db,
        payment_reference=payment_reference,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
    )
    transfer = complete_transfer_payment(db, payment_reference)
    return {
        "success": True,
        "transfer_id": str(transfer.id),
        "status": transfer.status,
    }


@router.post("/transfer/confirm")
async def confirm_transfer_payment(
    body: dict,
    db: Session = Depends(get_db),
):
    payment_reference = body.get("payment_reference")
    if not payment_reference:
        raise HTTPException(status_code=400, detail="payment_reference is required")
    transfer = complete_transfer_payment(db, payment_reference)
    return {
        "success": True,
        "transfer_id": str(transfer.id),
        "status": transfer.status,
    }
