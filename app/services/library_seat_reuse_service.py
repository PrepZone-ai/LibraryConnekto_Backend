"""When a student is removed, queue their seat numbers; assign FIFO to new students."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.admin import AdminDetails
from app.models.booking import SeatBooking
from app.models.library_freed_seat import LibraryFreedSeat
from app.models.student import Student

logger = logging.getLogger(__name__)


def _library_for_student(db: Session, student: Student) -> Optional[AdminDetails]:
    return db.query(AdminDetails).filter(AdminDetails.user_id == student.admin_id).first()


def record_freed_seats_for_removed_student(db: Session, student: Student) -> None:
    """Enqueue distinct seat numbers from this student's active seat bookings (before they are cancelled)."""
    library = _library_for_student(db, student)
    if not library:
        return
    bookings = (
        db.query(SeatBooking)
        .filter(
            SeatBooking.student_id == student.auth_user_id,
            SeatBooking.library_id == library.id,
            SeatBooking.status.in_(["pending", "approved", "active"]),
            SeatBooking.seat_number.isnot(None),
        )
        .all()
    )
    seen: set[str] = set()
    for b in bookings:
        sn = (b.seat_number or "").strip()
        if not sn or sn in seen:
            continue
        seen.add(sn)
        db.add(LibraryFreedSeat(library_id=library.id, seat_number=sn))
        logger.info("Queued freed seat %s for library %s", sn, library.id)


def student_has_assigned_seat_booking(db: Session, student: Student) -> bool:
    row = (
        db.query(SeatBooking)
        .filter(
            SeatBooking.student_id == student.auth_user_id,
            SeatBooking.status.in_(["pending", "approved", "active"]),
            SeatBooking.seat_number.isnot(None),
        )
        .first()
    )
    if not row:
        return False
    return bool((row.seat_number or "").strip())


def assign_next_freed_seat_to_student(db: Session, student: Student) -> Optional[str]:
    """
    If the library has a queued freed seat and the student has no seat booking yet,
    create an active SeatBooking (no payment) holding that seat.
    """
    if not student.is_active or student.subscription_status == "Removed":
        return None
    if student_has_assigned_seat_booking(db, student):
        return None
    library = _library_for_student(db, student)
    if not library:
        return None
    freed = (
        db.query(LibraryFreedSeat)
        .filter(LibraryFreedSeat.library_id == library.id)
        .order_by(LibraryFreedSeat.created_at.asc())
        .first()
    )
    if not freed:
        return None
    seat_number = (freed.seat_number or "").strip()
    if not seat_number:
        db.delete(freed)
        return None
    db.delete(freed)

    booking = SeatBooking(
        student_id=student.auth_user_id,
        library_id=library.id,
        admin_id=student.admin_id,
        name=student.name,
        email=student.email,
        mobile=student.mobile_no,
        address=student.address or "",
        seat_number=seat_number,
        status="active",
        payment_status="pending",
        amount=0,
        subscription_months=1,
        purpose="Seat auto-assigned from freed inventory",
    )
    db.add(booking)
    logger.info("Assigned freed seat %s to student %s", seat_number, student.id)
    return seat_number


def invalidate_seat_caches(db: Session, student: Student) -> None:
    from app.core.cache import invalidate_library_capacity, invalidate_admin_caches

    lib = _library_for_student(db, student)
    if lib:
        invalidate_library_capacity(str(lib.id))
    invalidate_admin_caches(str(student.admin_id))
