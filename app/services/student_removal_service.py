from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
import logging

from app.models.student_removal import StudentRemovalRequest, RemovalRequestStatus
from app.models.student import Student
from app.models.admin import AdminUser
from app.schemas.student_removal import (
    StudentRemovalRequestCreate, 
    StudentRemovalRequestResponse,
    StudentRemovalRequestUpdate
)

logger = logging.getLogger(__name__)

class StudentRemovalService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_removal_request(self, request_data: StudentRemovalRequestCreate) -> StudentRemovalRequest:
        """Create a new student removal request"""
        try:
            # Check if request already exists for this student
            existing_request = self.db.query(StudentRemovalRequest).filter(
                and_(
                    StudentRemovalRequest.student_id == request_data.student_id,
                    StudentRemovalRequest.status == RemovalRequestStatus.PENDING
                )
            ).first()
            
            if existing_request:
                logger.info(f"Removal request already exists for student {request_data.student_id}")
                return existing_request
            
            # Create new removal request
            removal_request = StudentRemovalRequest(
                student_id=request_data.student_id,
                admin_id=request_data.admin_id,
                reason=request_data.reason,
                subscription_end_date=request_data.subscription_end_date,
                days_overdue=request_data.days_overdue
            )
            
            self.db.add(removal_request)
            self.db.commit()
            self.db.refresh(removal_request)
            
            logger.info(f"Created removal request {removal_request.id} for student {request_data.student_id}")
            return removal_request
            
        except Exception as e:
            logger.error(f"Error creating removal request: {e}")
            self.db.rollback()
            raise
    
    def get_removal_requests(self, admin_id: Optional[UUID] = None, 
                           status: Optional[RemovalRequestStatus] = None,
                           limit: int = 50, offset: int = 0) -> List[StudentRemovalRequestResponse]:
        """Get removal requests with optional filtering"""
        try:
            query = self.db.query(StudentRemovalRequest)
            
            # Join with student and admin tables for additional data
            query = query.join(Student, StudentRemovalRequest.student_id == Student.id)
            query = query.join(AdminUser, StudentRemovalRequest.admin_id == AdminUser.id)
            
            # Apply filters
            if admin_id:
                query = query.filter(StudentRemovalRequest.admin_id == admin_id)
            
            if status:
                query = query.filter(StudentRemovalRequest.status == status)
            
            # Order by creation date (newest first)
            query = query.order_by(StudentRemovalRequest.created_at.desc())
            
            # Apply pagination
            requests = query.offset(offset).limit(limit).all()
            
            # Convert to response format
            result = []
            for request in requests:
                result.append(StudentRemovalRequestResponse(
                    id=request.id,
                    student_id=request.student_id,
                    admin_id=request.admin_id,
                    reason=request.reason,
                    status=request.status,
                    subscription_end_date=request.subscription_end_date,
                    days_overdue=request.days_overdue,
                    admin_notes=request.admin_notes,
                    processed_by=request.processed_by,
                    processed_at=request.processed_at,
                    created_at=request.created_at,
                    updated_at=request.updated_at,
                    student_name=request.student.name or f"{request.student.first_name or ''} {request.student.last_name or ''}".strip(),
                    student_email=request.student.email,
                    student_phone=request.student.mobile_no,
                    admin_name=request.admin.name or request.admin.admin_details.admin_name if request.admin.admin_details else "Admin",
                    library_name=request.admin.admin_details.library_name if request.admin.admin_details else "Library"
                ))
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting removal requests: {e}")
            raise
    
    def get_removal_request_by_id(self, request_id: UUID) -> Optional[StudentRemovalRequestResponse]:
        """Get a specific removal request by ID"""
        try:
            request = self.db.query(StudentRemovalRequest).filter(
                StudentRemovalRequest.id == request_id
            ).first()
            
            if not request:
                return None
            
            return StudentRemovalRequestResponse(
                id=request.id,
                student_id=request.student_id,
                admin_id=request.admin_id,
                reason=request.reason,
                status=request.status,
                subscription_end_date=request.subscription_end_date,
                days_overdue=request.days_overdue,
                admin_notes=request.admin_notes,
                processed_by=request.processed_by,
                processed_at=request.processed_at,
                created_at=request.created_at,
                updated_at=request.updated_at,
                student_name=request.student.name or f"{request.student.first_name or ''} {request.student.last_name or ''}".strip(),
                student_email=request.student.email,
                student_phone=request.student.mobile_no,
                admin_name=request.admin.name or request.admin.admin_details.admin_name if request.admin.admin_details else "Admin",
                library_name=request.admin.admin_details.library_name if request.admin.admin_details else "Library"
            )
            
        except Exception as e:
            logger.error(f"Error getting removal request {request_id}: {e}")
            raise
    
    def update_removal_request(self, request_id: UUID, update_data: StudentRemovalRequestUpdate, 
                              processed_by: UUID) -> Optional[StudentRemovalRequestResponse]:
        """Update a removal request status"""
        try:
            request = self.db.query(StudentRemovalRequest).filter(
                StudentRemovalRequest.id == request_id
            ).first()
            
            if not request:
                return None
            
            # Update request
            request.status = update_data.status
            request.admin_notes = update_data.admin_notes
            request.processed_by = processed_by
            request.processed_at = datetime.now()
            
            self.db.commit()
            self.db.refresh(request)
            
            # If approved, remove the student
            if update_data.status == RemovalRequestStatus.APPROVED:
                self._remove_student(request.student_id)
            
            logger.info(f"Updated removal request {request_id} to status {update_data.status}")
            
            return self.get_removal_request_by_id(request_id)
            
        except Exception as e:
            logger.error(f"Error updating removal request {request_id}: {e}")
            self.db.rollback()
            raise
    
    def _remove_student(self, student_id: UUID) -> bool:
        """Remove student from the library (soft delete)"""
        try:
            student = self.db.query(Student).filter(Student.id == student_id).first()
            
            if not student:
                logger.warning(f"Student {student_id} not found for removal")
                return False
            
            # Soft delete - mark as inactive
            student.is_active = False
            student.subscription_status = "Removed"
            student.removed_at = datetime.now()
            
            # Cancel any active bookings
            from app.models.booking import Booking
            active_bookings = self.db.query(Booking).filter(
                and_(
                    Booking.student_id == student_id,
                    Booking.status.in_(["confirmed", "pending"])
                )
            ).all()
            
            for booking in active_bookings:
                booking.status = "cancelled"
                booking.cancelled_at = datetime.now()
                booking.cancellation_reason = "Student removed from library"
            
            self.db.commit()
            
            logger.info(f"Successfully removed student {student_id} from library")
            return True
            
        except Exception as e:
            logger.error(f"Error removing student {student_id}: {e}")
            self.db.rollback()
            raise
    
    def restore_student(self, student_id: UUID) -> bool:
        """Restore a removed student back to the library"""
        try:
            student = self.db.query(Student).filter(Student.id == student_id).first()
            
            if not student:
                logger.warning(f"Student {student_id} not found for restoration")
                return False
            
            # Restore student access
            student.is_active = True
            student.subscription_status = "Active"  # or set to appropriate status
            student.removed_at = None
            
            self.db.commit()
            
            logger.info(f"Successfully restored student {student_id} to library")
            return True
            
        except Exception as e:
            logger.error(f"Error restoring student {student_id}: {e}")
            self.db.rollback()
            raise
    
    def get_removal_stats(self, admin_id: Optional[UUID] = None) -> Dict[str, int]:
        """Get removal request statistics"""
        try:
            query = self.db.query(StudentRemovalRequest)
            
            if admin_id:
                query = query.filter(StudentRemovalRequest.admin_id == admin_id)
            
            total_requests = query.count()
            pending_requests = query.filter(StudentRemovalRequest.status == RemovalRequestStatus.PENDING).count()
            approved_requests = query.filter(StudentRemovalRequest.status == RemovalRequestStatus.APPROVED).count()
            rejected_requests = query.filter(StudentRemovalRequest.status == RemovalRequestStatus.REJECTED).count()
            
            # Count overdue students (expired subscription, no payment in 2+ days)
            overdue_cutoff = datetime.now() - timedelta(days=2)
            overdue_students = self.db.query(Student).filter(
                and_(
                    Student.admin_id == admin_id if admin_id else True,
                    Student.subscription_end < overdue_cutoff,
                    Student.subscription_status == "Expired",
                    Student.is_active == True
                )
            ).count()
            
            return {
                "total_requests": total_requests,
                "pending_requests": pending_requests,
                "approved_requests": approved_requests,
                "rejected_requests": rejected_requests,
                "overdue_students": overdue_students
            }
            
        except Exception as e:
            logger.error(f"Error getting removal stats: {e}")
            raise
    
    def check_and_create_removal_requests(self) -> int:
        """Check for expired subscriptions and create removal requests"""
        try:
            # Find students with expired subscriptions (2+ days overdue)
            overdue_cutoff = datetime.now() - timedelta(days=2)
            
            overdue_students = self.db.query(Student).filter(
                and_(
                    Student.subscription_end < overdue_cutoff,
                    Student.subscription_status == "Expired",
                    Student.is_active == True
                )
            ).all()
            
            created_count = 0
            
            for student in overdue_students:
                # Check if removal request already exists
                existing_request = self.db.query(StudentRemovalRequest).filter(
                    and_(
                        StudentRemovalRequest.student_id == student.id,
                        StudentRemovalRequest.status == RemovalRequestStatus.PENDING
                    )
                ).first()
                
                if not existing_request:
                    # Calculate days overdue
                    days_overdue = (datetime.now() - student.subscription_end).days
                    
                    # Create removal request
                    request_data = StudentRemovalRequestCreate(
                        student_id=student.id,
                        admin_id=student.admin_id,
                        reason="Subscription expired and payment not received within 2 days",
                        subscription_end_date=student.subscription_end,
                        days_overdue=f"{days_overdue} days overdue"
                    )
                    
                    self.create_removal_request(request_data)
                    created_count += 1
                    
                    logger.info(f"Created removal request for overdue student {student.id}")
            
            return created_count
            
        except Exception as e:
            logger.error(f"Error checking and creating removal requests: {e}")
            raise
