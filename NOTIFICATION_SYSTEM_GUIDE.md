# Notification System Guide

## Overview

The Library Management System now includes a comprehensive notification system that automatically sends time-based reminders to students for their tasks and exams. The system is designed to be extensible and supports multiple notification types and delivery methods.

## Features

### 🎯 Automatic Reminders
- **Task Reminders**: Automatically created when students add tasks with due dates
- **Exam Reminders**: Automatically created when students add exams
- **Customizable Timing**: Support for multiple reminder intervals (1 hour, 6 hours, 1 day, 3 days, 1 week, 2 weeks)

### 📱 Notification Types
- **Task Reminders**: Notifications for upcoming task deadlines
- **Exam Reminders**: Notifications for upcoming exams
- **General Notifications**: Admin-sent notifications to students
- **System Notifications**: System-generated notifications

### 🔔 Priority Levels
- **Low**: 2+ weeks before due date
- **Medium**: 3 days to 1 week before due date
- **High**: 1 day before due date
- **Urgent**: 1-6 hours before due date

## Database Schema

### StudentNotification Table
```sql
CREATE TABLE student_notifications (
    id UUID PRIMARY KEY,
    student_id UUID REFERENCES students(id),
    admin_id UUID REFERENCES admin_users(user_id),
    title VARCHAR NOT NULL,
    message TEXT NOT NULL,
    notification_type VARCHAR NOT NULL, -- task_reminder, exam_reminder, general, system
    priority VARCHAR DEFAULT 'medium', -- low, medium, high, urgent
    related_task_id UUID REFERENCES student_tasks(id),
    related_exam_id UUID REFERENCES student_exams(id),
    scheduled_for TIMESTAMP WITH TIME ZONE NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE,
    read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## API Endpoints

### Student Endpoints

#### Get Notifications
```http
GET /api/v1/notifications/
```
**Query Parameters:**
- `skip` (int): Number of notifications to skip (default: 0)
- `limit` (int): Maximum number of notifications to return (default: 50)
- `notification_type` (str): Filter by notification type (optional)
- `unread_only` (bool): Show only unread notifications (default: false)

#### Get Unread Count
```http
GET /api/v1/notifications/unread-count
```

#### Mark Notification as Read
```http
PUT /api/v1/notifications/{notification_id}/read
```

#### Mark All Notifications as Read
```http
PUT /api/v1/notifications/mark-all-read
```

#### Create Task Reminders
```http
POST /api/v1/notifications/task-reminders
```
**Request Body:**
```json
{
    "task_id": "uuid",
    "reminder_times": ["1_hour", "1_day"]
}
```

#### Create Exam Reminders
```http
POST /api/v1/notifications/exam-reminders
```
**Request Body:**
```json
{
    "exam_id": "uuid",
    "reminder_times": ["1_day", "1_week"]
}
```

### Admin Endpoints

#### Send Notification to Student
```http
POST /api/v1/notifications/admin/send
```
**Request Body:**
```json
{
    "student_id": "uuid",
    "title": "Notification Title",
    "message": "Notification message",
    "notification_type": "general",
    "priority": "medium",
    "scheduled_for": "2024-01-01T10:00:00Z"
}
```

#### Send Broadcast Notification
```http
POST /api/v1/notifications/admin/broadcast
```
**Request Body:**
```json
{
    "title": "Broadcast Title",
    "message": "Broadcast message to all students",
    "notification_type": "general",
    "priority": "medium",
    "scheduled_for": "2024-01-01T10:00:00Z"
}
```

#### Get Pending Notifications
```http
GET /api/v1/notifications/admin/pending
```

#### Mark Notification as Sent
```http
PUT /api/v1/notifications/admin/{notification_id}/sent
```

## Automatic Notification Creation

### Task Creation
When a student creates a task with a due date, the system automatically creates reminders:
- **Default Reminders**: 1 hour and 1 day before due date
- **Automatic Priority**: Based on time until due date

### Exam Creation
When a student creates an exam, the system automatically creates reminders:
- **Default Reminders**: 1 day and 1 week before exam date
- **Automatic Priority**: Based on time until exam date

## Background Scheduler

The notification system includes a background scheduler that:
- Runs every 60 seconds
- Processes pending notifications that are ready to be sent
- Marks notifications as sent after processing
- Logs all notification activities

### Scheduler Integration
The scheduler is automatically started when the FastAPI application starts and stopped when it shuts down.

## Notification Service

The `NotificationService` class provides methods for:
- Creating task and exam reminders
- Managing notification lifecycle
- Querying notifications
- Marking notifications as read/sent

### Key Methods
```python
# Create task reminders
notification_service.create_task_reminders(task, reminder_times)

# Create exam reminders
notification_service.create_exam_reminders(exam, reminder_times)

# Get pending notifications
notification_service.get_pending_notifications()

# Mark notification as sent
notification_service.mark_notification_sent(notification_id)
```

## Integration Points

### Email Notifications
The system is designed to integrate with email services:
- SendGrid
- AWS SES
- SMTP servers

### Push Notifications
Ready for integration with:
- Firebase Cloud Messaging
- OneSignal
- Apple Push Notification Service

### WebSocket Notifications
Supports real-time notifications via WebSocket connections.

## Configuration

### Reminder Times
Available reminder time options:
- `1_hour`: 1 hour before due date
- `6_hours`: 6 hours before due date
- `1_day`: 1 day before due date
- `3_days`: 3 days before due date
- `1_week`: 1 week before due date
- `2_weeks`: 2 weeks before due date

### Priority Mapping
- **Urgent**: 1_hour, 6_hours
- **High**: 1_day
- **Medium**: 3_days, 1_week
- **Low**: 2_weeks

## Usage Examples

### Creating a Task with Automatic Reminders
```python
# When a student creates a task
task_data = {
    "title": "Complete Math Assignment",
    "description": "Solve problems 1-20",
    "due_date": "2024-01-15T23:59:00Z",
    "priority": "high"
}

# The system automatically creates reminders for:
# - 1 hour before due date (urgent priority)
# - 1 day before due date (high priority)
```

### Creating an Exam with Automatic Reminders
```python
# When a student creates an exam
exam_data = {
    "exam_name": "Final Mathematics Exam",
    "exam_date": "2024-01-20T09:00:00Z",
    "notes": "Bring calculator and ID"
}

# The system automatically creates reminders for:
# - 1 day before exam (high priority)
# - 1 week before exam (medium priority)
```

### Admin Sending Custom Notifications
```python
# Admin can send custom notifications
notification_data = {
    "student_id": "student-uuid",
    "title": "Library Closure Notice",
    "message": "The library will be closed tomorrow for maintenance.",
    "notification_type": "general",
    "priority": "high",
    "scheduled_for": "2024-01-10T08:00:00Z"
}
```

## Testing

### Manual Testing
1. Create a task with a due date in the future
2. Check that notifications are created in the database
3. Verify the scheduler processes pending notifications
4. Test marking notifications as read

### API Testing
Use the FastAPI documentation at `/docs` to test all notification endpoints.

## Future Enhancements

### Planned Features
1. **Email Integration**: Send notifications via email
2. **Push Notifications**: Mobile app push notifications
3. **SMS Notifications**: Text message reminders
4. **Notification Preferences**: Student-customizable notification settings
5. **Notification Templates**: Predefined notification templates
6. **Analytics**: Notification delivery and engagement analytics

### Extensibility
The system is designed to be easily extensible:
- Add new notification types
- Integrate with external services
- Customize reminder timing
- Add new delivery methods

## Troubleshooting

### Common Issues
1. **Notifications not being sent**: Check if the scheduler is running
2. **Database errors**: Ensure the migration was applied correctly
3. **Permission errors**: Verify student/admin authentication

### Logs
The system logs all notification activities. Check the application logs for:
- Scheduler status
- Notification processing
- Error messages

## Security Considerations

1. **Authentication**: All endpoints require proper authentication
2. **Authorization**: Students can only access their own notifications
3. **Admin Access**: Admins can only manage notifications for their students
4. **Data Privacy**: Notification data is properly isolated by admin/student relationships
