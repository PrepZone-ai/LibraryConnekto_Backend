from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.cache import invalidate_admin_caches, invalidate_student_dashboard
from app.models.student import Student, StudentAttendance


def auto_checkout_stale_attendance_sessions(db: Session) -> int:
    """Auto-checkout active attendance sessions that stopped sending location pings."""
    stale_before = datetime.now(timezone.utc) - timedelta(
        minutes=settings.ATTENDANCE_AUTO_CHECKOUT_STALE_MINUTES
    )

    stale_sessions = (
        db.query(StudentAttendance)
        .join(Student, Student.auth_user_id == StudentAttendance.student_id)
        .filter(
            StudentAttendance.exit_time.is_(None),
            StudentAttendance.last_ping_at.isnot(None),
            StudentAttendance.last_ping_at <= stale_before,
        )
        .all()
    )

    if not stale_sessions:
        return 0

    affected_admins = set()
    affected_students = set()
    now_utc = datetime.now(timezone.utc)

    for attendance in stale_sessions:
        attendance.exit_time = now_utc

        if attendance.entry_time.tzinfo is None:
            entry_time_aware = attendance.entry_time.replace(tzinfo=timezone.utc)
        else:
            entry_time_aware = attendance.entry_time

        attendance.total_duration = attendance.exit_time - entry_time_aware

        student = (
            db.query(Student)
            .filter(Student.auth_user_id == attendance.student_id)
            .first()
        )
        if student:
            student.status = "Absent"
            affected_admins.add(str(student.admin_id))
            affected_students.add(str(student.auth_user_id))

    db.commit()

    for student_id in affected_students:
        invalidate_student_dashboard(student_id)
    for admin_id in affected_admins:
        invalidate_admin_caches(admin_id)

    return len(stale_sessions)
