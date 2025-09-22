import asyncio
import logging
from datetime import datetime
from typing import List
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.config import settings
from app.services.notification_service import NotificationService
from app.services.subscription_notification_service import SubscriptionNotificationService
from app.services.student_removal_service import StudentRemovalService
from app.models.student import StudentNotification

logger = logging.getLogger(__name__)

class NotificationScheduler:
    def __init__(self):
        self.running = False
        self.task = None
    
    async def start(self):
        """Start the notification scheduler"""
        if self.running:
            logger.warning("Notification scheduler is already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._run_scheduler())
        logger.info("Notification scheduler started")
    
    async def stop(self):
        """Stop the notification scheduler"""
        if not self.running:
            return
        
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        logger.info("Notification scheduler stopped")
    
    async def _run_scheduler(self):
        """Main scheduler loop"""
        # Optional initial delay to avoid immediate sends on server boot
        initial_delay = max(0, int(getattr(settings, 'SCHEDULER_INITIAL_DELAY_SECONDS', 0)))
        if initial_delay:
            logger.info(f"Scheduler initial delay: {initial_delay}s")
            await asyncio.sleep(initial_delay)

        # Track last dates we ran daily tasks
        last_subscription_check_date = None

        while self.running:
            try:
                await self._process_pending_notifications()

                # Run subscription checks at most once per day if enabled
                if getattr(settings, 'SUBSCRIPTION_CHECKS_DAILY_ENABLED', True):
                    from datetime import date
                    today = date.today()
                    if last_subscription_check_date != today:
                        await self._check_subscription_expiry()
                        last_subscription_check_date = today
                else:
                    await self._check_subscription_expiry()
                await self._check_overdue_students()
                # Sleep based on configured loop interval
                loop_interval = max(1, int(getattr(settings, 'SCHEDULER_LOOP_INTERVAL_SECONDS', 60)))
                await asyncio.sleep(loop_interval)
            except Exception as e:
                logger.error(f"Error in notification scheduler: {e}")
                loop_interval = max(1, int(getattr(settings, 'SCHEDULER_LOOP_INTERVAL_SECONDS', 60)))
                await asyncio.sleep(loop_interval)  # Wait before retrying
    
    async def _process_pending_notifications(self):
        """Process pending notifications that are ready to be sent"""
        try:
            # Get database session
            db = next(get_db())
            notification_service = NotificationService(db)
            
            # Get pending notifications
            pending_notifications = notification_service.get_pending_notifications(limit=100)
            
            if pending_notifications:
                logger.info(f"Processing {len(pending_notifications)} pending notifications")
                
                for notification in pending_notifications:
                    try:
                        await self._send_notification(notification, db)
                        notification_service.mark_notification_sent(notification.id)
                        logger.info(f"Sent notification {notification.id} to student {notification.student_id}")
                    except Exception as e:
                        logger.error(f"Failed to send notification {notification.id}: {e}")
            
            db.close()
            
        except Exception as e:
            logger.error(f"Error processing pending notifications: {e}")
    
    async def _send_notification(self, notification: StudentNotification, db: Session):
        """Send a notification (placeholder for actual sending logic)"""
        # This is where you would integrate with actual notification services
        # For now, we'll just log the notification
        
        logger.info(f"Sending notification: {notification.title} - {notification.message}")
        
        # Here you could integrate with:
        # - Email services (SendGrid, AWS SES, etc.)
        # - Push notification services (Firebase, OneSignal, etc.)
        # - SMS services (Twilio, etc.)
        # - In-app notifications
        # - WebSocket connections for real-time updates
        
        # Example integration points:
        # await self._send_email_notification(notification)
        # await self._send_push_notification(notification)
        # await self._send_websocket_notification(notification)
        
        # For now, we'll just mark it as sent in the database
        pass
    
    async def _send_email_notification(self, notification: StudentNotification):
        """Send email notification (placeholder)"""
        # Implement email sending logic here
        # You could use services like SendGrid, AWS SES, etc.
        pass
    
    async def _send_push_notification(self, notification: StudentNotification):
        """Send push notification (placeholder)"""
        # Implement push notification logic here
        # You could use Firebase, OneSignal, etc.
        pass
    
    async def _send_websocket_notification(self, notification: StudentNotification):
        """Send real-time notification via WebSocket (placeholder)"""
        # Implement WebSocket notification logic here
        # This would notify connected clients in real-time
        pass
    
    async def _check_subscription_expiry(self):
        """Check for expiring subscriptions and send warnings"""
        try:
            # Get database session
            db = next(get_db())
            subscription_service = SubscriptionNotificationService(db)
            
            # Check for expiring subscriptions (5 days or less)
            warning_results = subscription_service.check_and_send_subscription_warnings()
            
            # Check for expired subscriptions
            expired_results = subscription_service.check_and_send_expired_notifications()
            
            if warning_results or expired_results:
                logger.info(f"Subscription checks completed: {len(warning_results)} warnings, {len(expired_results)} expired")
            
            db.close()
            
        except Exception as e:
            logger.error(f"Error checking subscription expiry: {e}")
    
    async def _check_overdue_students(self):
        """Check for overdue students and create removal requests"""
        try:
            db = next(get_db())
            removal_service = StudentRemovalService(db)
            created_count = removal_service.check_and_create_removal_requests()
            
            if created_count > 0:
                logger.info(f"Created {created_count} new removal requests for overdue students")
            
            db.close()
        except Exception as e:
            logger.error(f"Error checking overdue students: {e}")

# Global scheduler instance
notification_scheduler = NotificationScheduler()

async def start_notification_scheduler():
    """Start the notification scheduler (call this when the app starts)"""
    await notification_scheduler.start()

async def stop_notification_scheduler():
    """Stop the notification scheduler (call this when the app shuts down)"""
    await notification_scheduler.stop()
