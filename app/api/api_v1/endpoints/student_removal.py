from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.auth.dependencies import get_current_admin
from app.models.admin import AdminUser
from app.services.student_removal_service import StudentRemovalService
from app.schemas.student_removal import (
    StudentRemovalRequestResponse,
    StudentRemovalRequestUpdate,
    StudentRemovalRequestList,
    StudentRemovalStats,
    RemovalRequestStatus
)

router = APIRouter()

@router.get("/requests", response_model=StudentRemovalRequestList)
async def get_removal_requests(
    status: Optional[RemovalRequestStatus] = Query(None, description="Filter by request status"),
    limit: int = Query(50, ge=1, le=100, description="Number of requests to return"),
    offset: int = Query(0, ge=0, description="Number of requests to skip"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get student removal requests for the current admin's library"""
    try:
        removal_service = StudentRemovalService(db)
        
        # Get requests for this admin's library
        requests = removal_service.get_removal_requests(
            admin_id=current_admin.id,
            status=status,
            limit=limit,
            offset=offset
        )
        
        # Get total counts
        stats = removal_service.get_removal_stats(admin_id=current_admin.id)
        
        return StudentRemovalRequestList(
            requests=requests,
            total=stats["total_requests"],
            pending_count=stats["pending_requests"],
            approved_count=stats["approved_requests"],
            rejected_count=stats["rejected_requests"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching removal requests: {str(e)}"
        )

@router.get("/requests/{request_id}", response_model=StudentRemovalRequestResponse)
async def get_removal_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get a specific removal request by ID"""
    try:
        removal_service = StudentRemovalService(db)
        
        request = removal_service.get_removal_request_by_id(request_id)
        
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Removal request not found"
            )
        
        # Verify the request belongs to this admin's library
        if request.admin_id != current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this removal request"
            )
        
        return request
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching removal request: {str(e)}"
        )

@router.put("/requests/{request_id}", response_model=StudentRemovalRequestResponse)
async def update_removal_request(
    request_id: UUID,
    update_data: StudentRemovalRequestUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Update a removal request status (approve/reject)"""
    try:
        removal_service = StudentRemovalService(db)
        
        # First, verify the request exists and belongs to this admin
        existing_request = removal_service.get_removal_request_by_id(request_id)
        
        if not existing_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Removal request not found"
            )
        
        if existing_request.admin_id != current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this removal request"
            )
        
        if existing_request.status != RemovalRequestStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pending requests can be updated"
            )
        
        # Update the request
        updated_request = removal_service.update_removal_request(
            request_id=request_id,
            update_data=update_data,
            processed_by=current_admin.id
        )
        
        if not updated_request:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update removal request"
            )
        
        return updated_request
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating removal request: {str(e)}"
        )

@router.get("/stats", response_model=StudentRemovalStats)
async def get_removal_stats(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get removal request statistics for the current admin's library"""
    try:
        removal_service = StudentRemovalService(db)
        
        stats = removal_service.get_removal_stats(admin_id=current_admin.id)
        
        return StudentRemovalStats(**stats)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching removal stats: {str(e)}"
        )

@router.post("/check-overdue")
async def check_overdue_students(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Manually trigger check for overdue students and create removal requests"""
    try:
        removal_service = StudentRemovalService(db)
        
        # Only check students for this admin's library
        created_count = removal_service.check_and_create_removal_requests()
        
        return {
            "success": True,
            "message": f"Created {created_count} new removal requests",
            "created_count": created_count
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking overdue students: {str(e)}"
        )

@router.get("/overdue-students")
async def get_overdue_students(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get list of students with expired subscriptions (potential removal candidates)"""
    try:
        from app.models.student import Student
        from datetime import datetime, timedelta
        
        # Find students with expired subscriptions (2+ days overdue)
        overdue_cutoff = datetime.now() - timedelta(days=2)
        
        overdue_students = db.query(Student).filter(
            Student.admin_id == current_admin.id,
            Student.subscription_end < overdue_cutoff,
            Student.subscription_status == "Expired",
            Student.is_active == True
        ).all()
        
        result = []
        for student in overdue_students:
            days_overdue = (datetime.now() - student.subscription_end).days
            
            # Check if removal request already exists
            from app.models.student_removal import StudentRemovalRequest, RemovalRequestStatus
            existing_request = db.query(StudentRemovalRequest).filter(
                StudentRemovalRequest.student_id == student.id,
                StudentRemovalRequest.status == RemovalRequestStatus.PENDING
            ).first()
            
            result.append({
                "student_id": student.id,
                "student_name": f"{student.first_name} {student.last_name}".strip(),
                "student_email": student.email,
                "subscription_end": student.subscription_end.isoformat(),
                "days_overdue": days_overdue,
                "removal_request_exists": existing_request is not None,
                "removal_request_id": existing_request.id if existing_request else None
            })
        
        return {
            "success": True,
            "overdue_students": result,
            "total_count": len(result)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching overdue students: {str(e)}"
        )

@router.post("/restore-student/{student_id}")
async def restore_student(
    student_id: UUID,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Restore a removed student back to the library"""
    try:
        removal_service = StudentRemovalService(db)
        
        # Check if student exists and belongs to this admin's library
        student = db.query(Student).filter(
            Student.id == student_id,
            Student.admin_id == current_admin.id
        ).first()
        
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found in your library"
            )
        
        if student.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student is already active"
            )
        
        # Restore the student
        success = removal_service.restore_student(student_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to restore student"
            )
        
        return {
            "success": True,
            "message": f"Student {student.name} has been restored to the library",
            "student_id": student_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error restoring student: {str(e)}"
        )
