from sqlalchemy.orm import Session
from sqlalchemy import func, select
from app.models.admin import AdminDetails
from app.models.student import Student

async def generate_student_id(admin_id: str, db: Session) -> str:
    """Generate a unique student ID for the given admin"""
    # Get admin details to get library name
    admin_details = db.query(AdminDetails).filter(AdminDetails.user_id == admin_id).first()
    if not admin_details:
        raise ValueError("Admin details not found")
    
    # Get current year (last 2 digits)
    current_year = db.execute(select(func.extract('year', func.now()))).scalar_one()
    year = str(current_year)[-2:]
    
    # Get first 4 letters of library name, sanitized
    raw_prefix = admin_details.library_name or ""
    library_prefix = "".join(filter(str.isalnum, raw_prefix)).upper()[:4]
    if len(library_prefix) < 4:
        library_prefix = library_prefix.ljust(4, 'L')

    # Get all students with this library prefix and year
    existing_students = db.query(Student).filter(
        Student.student_id.like(f"{library_prefix}{year}%"),
        Student.admin_id == admin_id
    ).all()
    
    max_sequence = 0
    if existing_students:
        # Extract sequence numbers from existing IDs and find the maximum
        for student in existing_students:
            try:
                sequence = int(student.student_id[-3:])
                max_sequence = max(max_sequence, sequence)
            except (ValueError, IndexError):
                continue
    
    # Increment sequence number
    next_sequence = max_sequence + 1
    
    # Format: LIBR25001 (where LIBR is first 4 letters of library name, 25 is year, 001 is sequence)
    return f"{library_prefix}{year}{next_sequence:03d}"
