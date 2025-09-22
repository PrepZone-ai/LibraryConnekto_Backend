# Library Management System API Endpoints

## Base URL
`http://localhost:8000`

## Authentication Endpoints (`/api/v1/auth`)

### Admin Authentication
- `POST /api/v1/auth/admin/signup` - Register a new admin
- `POST /api/v1/auth/admin/signin` - Admin login

### Student Authentication  
- `POST /api/v1/auth/student/signup` - Register a new student
- `POST /api/v1/auth/student/signin` - Student login

## Admin Management Endpoints (`/api/v1/admin`)

### Admin Details
- `GET /api/v1/admin/details` - Get admin details
- `POST /api/v1/admin/details` - Create admin details
- `PUT /api/v1/admin/details` - Update admin details

### Statistics & Analytics
- `GET /api/v1/admin/stats` - Get basic library statistics
- `GET /api/v1/admin/analytics/dashboard` - Get comprehensive dashboard analytics
- `GET /api/v1/admin/analytics/attendance-trends` - Get attendance trends
- `GET /api/v1/admin/analytics/revenue-trends` - Get revenue trends

### Student Management
- `GET /api/v1/admin/students` - Get all students
- `POST /api/v1/admin/students` - Create a new student
- `GET /api/v1/admin/students/{student_id}` - Get specific student
- `PUT /api/v1/admin/students/{student_id}` - Update student
- `DELETE /api/v1/admin/students/{student_id}` - Delete student (soft delete)

### Attendance Management
- `GET /api/v1/admin/students/{student_id}/attendance` - Get student attendance
- `GET /api/v1/admin/attendance/today` - Get today's attendance for all students

### Task Management
- `GET /api/v1/admin/students/{student_id}/tasks` - Get student tasks
- `POST /api/v1/admin/students/{student_id}/tasks` - Create task for student

## Student Endpoints (`/api/v1/student`)

### Profile Management
- `GET /api/v1/student/profile` - Get student profile
- `PUT /api/v1/student/profile` - Update student profile

### Attendance
- `POST /api/v1/student/attendance/checkin` - Check in
- `POST /api/v1/student/attendance/checkout` - Check out
- `GET /api/v1/student/attendance` - Get attendance history

### Task Management
- `GET /api/v1/student/tasks` - Get tasks
- `POST /api/v1/student/tasks` - Create task
- `PUT /api/v1/student/tasks/{task_id}` - Update task
- `DELETE /api/v1/student/tasks/{task_id}` - Delete task

### Exam Management
- `GET /api/v1/student/exams` - Get exams
- `POST /api/v1/student/exams` - Create exam
- `PUT /api/v1/student/exams/{exam_id}` - Update exam
- `DELETE /api/v1/student/exams/{exam_id}` - Delete exam

## Booking System Endpoints (`/api/v1/booking`)

### Library Discovery
- `GET /api/v1/booking/libraries` - Get available libraries with location filtering

### Seat Booking
- `POST /api/v1/booking/seat-booking` - Create booking request
- `GET /api/v1/booking/seat-bookings` - Get bookings (admin view)
- `PUT /api/v1/booking/seat-bookings/{booking_id}` - Update booking (approve/reject)
- `GET /api/v1/booking/my-bookings` - Get bookings for current student

## Messaging Endpoints (`/api/v1/messaging`)

### Student Messaging
- `POST /api/v1/messaging/send-message` - Send message to admin
- `GET /api/v1/messaging/messages` - Get messages

### Admin Messaging
- `POST /api/v1/messaging/admin/send-message` - Send message to student
- `POST /api/v1/messaging/admin/broadcast` - Send broadcast message
- `PUT /api/v1/messaging/messages/{message_id}` - Update message (mark as read, respond)

## Referral System Endpoints (`/api/v1/referral`)

### Referral Codes
- `POST /api/v1/referral/codes` - Create referral code
- `GET /api/v1/referral/codes` - Get user's referral codes
- `POST /api/v1/referral/validate` - Validate referral code

### Referrals
- `POST /api/v1/referral/referrals` - Create referral
- `GET /api/v1/referral/referrals` - Get user's referrals
- `PUT /api/v1/referral/referrals/{referral_id}` - Update referral status

## Subscription Plan Endpoints (`/api/v1/subscription`)

### Plan Management
- `GET /api/v1/subscription/plans` - Get all subscription plans
- `POST /api/v1/subscription/plans` - Create subscription plan (admin only)
- `GET /api/v1/subscription/plans/{plan_id}` - Get specific plan
- `PUT /api/v1/subscription/plans/{plan_id}` - Update plan (admin only)
- `DELETE /api/v1/subscription/plans/{plan_id}` - Delete plan (admin only)

## Utility Endpoints

### Health Check
- `GET /health` - API health check
- `GET /api/v1/health` - API v1 health check

### File Upload
- `POST /upload` - Upload file (returns file URL)

### API Information
- `GET /` - API information and available endpoints

## Authentication

Most endpoints require authentication via JWT token in the Authorization header:
```
Authorization: Bearer <jwt_token>
```

## Response Format

All endpoints return JSON responses with appropriate HTTP status codes:
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `500` - Internal Server Error

## Interactive Documentation

Visit `http://localhost:8000/docs` for interactive API documentation with Swagger UI.
Visit `http://localhost:8000/redoc` for alternative documentation with ReDoc.
