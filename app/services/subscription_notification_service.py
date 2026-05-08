from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, timezone, date
from typing import List, Optional
from uuid import UUID
import logging

from app.models.student import Student
from app.models.subscription import SubscriptionPlan
from app.models.admin import AdminDetails
from app.services.notification_service import NotificationService
from app.utils.subscription_plan_scope import admin_details_id_for_user, apply_plan_shift_filters
from app.services.email_queue_service import enqueue_email_job
from app.core.config import settings

logger = logging.getLogger(__name__)

class SubscriptionNotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService(db)

    def _subscription_plans_for_student(self, student: Student) -> List[SubscriptionPlan]:
        lib_id = admin_details_id_for_user(self.db, student.admin_id)
        if not lib_id:
            return []
        library = self.db.query(AdminDetails).filter(AdminDetails.id == lib_id).first()
        if not library:
            return []
        q = self.db.query(SubscriptionPlan).filter(
            SubscriptionPlan.library_id == lib_id,
            SubscriptionPlan.is_active == True,
        )
        q = apply_plan_shift_filters(
            q,
            library,
            is_shift_student=student.is_shift_student,
            shift_time=student.shift_time,
        )
        return q.all()

    def _renewal_url(self) -> str:
        base = (getattr(settings, "FRONTEND_BASE_URL", None) or "http://127.0.0.1:5173").rstrip("/")
        return f"{base}/student/subscription"

    def check_and_send_subscription_warnings(self) -> List[dict]:
        """Notify Active students only on milestone days: 5, 3, and 1 day(s) before expiry (once per calendar day)."""
        results = []
        today: date = datetime.now(timezone.utc).date()
        milestone_end_dates = [today + timedelta(days=d) for d in (5, 3, 1)]

        students_to_warn = (
            self.db.query(Student)
            .filter(
                Student.subscription_status == "Active",
                func.date(Student.subscription_end).in_(milestone_end_dates),
            )
            .all()
        )

        renew_url = self._renewal_url()

        for student in students_to_warn:
            end_d = (
                student.subscription_end.date()
                if student.subscription_end and hasattr(student.subscription_end, "date")
                else today
            )
            days_left = (end_d - today).days
            try:
                # Send in-app notification (includes renew / pay link)
                notification_result = self._send_subscription_warning_notification(
                    student, days_left, renew_url
                )
                
                email_sent = False
                if getattr(settings, 'SUBSCRIPTION_EMAIL_FROM_SCHEDULER_ENABLED', False):
                    # Send email only if explicitly enabled
                    email_sent = self._send_subscription_warning_email(student, days_left, renew_url)
                
                results.append({
                    'student_id': str(student.id),
                    'student_name': student.name,
                    'days_left': days_left,
                    'notification_sent': notification_result,
                    'email_sent': email_sent
                })
                
                logger.info(f"Subscription warning processed for student {student.name} ({days_left} days left) - email={'on' if email_sent else 'off'}")
                
            except Exception as e:
                logger.error(f"Failed to send subscription warning to student {student.id}: {e}")
                results.append({
                    'student_id': str(student.id),
                    'student_name': student.name,
                    'days_left': days_left,
                    'notification_sent': False,
                    'email_sent': False,
                    'error': str(e)
                })
        
        return results
    
    def check_and_send_expired_notifications(self) -> List[dict]:
        """Check for students with expired subscriptions and send notifications"""
        results = []
        now = datetime.now(timezone.utc)
        today = now.date()
        renew_url = self._renewal_url()

        expired_students = self.db.query(Student).filter(
            Student.subscription_end < now,
            Student.subscription_status == 'Active'
        ).all()
        
        for student in expired_students:
            days_expired = max(
                0,
                (today - student.subscription_end.date()).days
                if student.subscription_end
                else 0,
            )
            try:
                # Update subscription status
                student.subscription_status = 'Expired'
                self.db.commit()
                
                # Send in-app notification
                notification_result = self._send_subscription_expired_notification(
                    student, days_expired, renew_url
                )
                
                email_sent = False
                if getattr(settings, 'SUBSCRIPTION_EMAIL_FROM_SCHEDULER_ENABLED', False):
                    # Send email only if explicitly enabled
                    email_sent = self._send_subscription_expired_email(student, days_expired, renew_url)
                
                results.append({
                    'student_id': str(student.id),
                    'student_name': student.name,
                    'days_expired': days_expired,
                    'notification_sent': notification_result,
                    'email_sent': email_sent
                })
                
                logger.info(f"Subscription expired processed for student {student.name} - email={'on' if email_sent else 'off'}")
                
            except Exception as e:
                logger.error(f"Failed to send expired notification to student {student.id}: {e}")
                results.append({
                    'student_id': str(student.id),
                    'student_name': student.name,
                    'days_expired': days_expired,
                    'notification_sent': False,
                    'email_sent': False,
                    'error': str(e)
                })
        
        return results
    
    def _send_subscription_warning_notification(
        self, student: Student, days_left: int, renew_url: str
    ) -> bool:
        """Send subscription warning notification to student"""
        try:
            pay_line = f" Renew or pay online here: {renew_url}"
            if days_left == 1:
                title = "⚠️ Subscription — last day before expiry"
                message = (
                    "Your library subscription ends tomorrow. Choose a plan and pay to extend it."
                    + pay_line
                )
                priority = "urgent"
            elif days_left == 3:
                title = "⚠️ Subscription expires in 3 days"
                message = (
                    "Your library subscription expires in 3 days. Renew now to avoid interruption."
                    + pay_line
                )
                priority = "high"
            else:
                title = "📚 Subscription expires in 5 days"
                message = (
                    "Your library subscription expires in 5 days. You can renew anytime."
                    + pay_line
                )
                priority = "medium"
            
            notification = self.notification_service.create_system_notification(
                student_id=student.id,
                admin_id=student.admin_id,
                title=title,
                message=message,
                priority=priority
            )
            
            return notification is not None
            
        except Exception as e:
            logger.error(f"Failed to send subscription warning notification: {e}")
            return False
    
    def _send_subscription_expired_notification(
        self, student: Student, days_expired: int, renew_url: str
    ) -> bool:
        """Send subscription expired notification to student"""
        try:
            title = "❌ Subscription Expired"
            message = (
                "Your library subscription has expired. Renew with a plan to restore access. "
                f"If you do not renew, the library may request your removal. Pay here: {renew_url}"
            )
            priority = "urgent"
            
            notification = self.notification_service.create_system_notification(
                student_id=student.id,
                admin_id=student.admin_id,
                title=title,
                message=message,
                priority=priority
            )
            
            return notification is not None
            
        except Exception as e:
            logger.error(f"Failed to send subscription expired notification: {e}")
            return False
    
    def _send_subscription_warning_email(
        self, student: Student, days_left: int, renew_url: str
    ) -> bool:
        """Send subscription warning email to student"""
        try:
            subscription_plans = self._subscription_plans_for_student(student)

            if days_left == 1:
                subject = "⚠️ Your Library Subscription Expires Tomorrow!"
                urgency = "URGENT"
            elif days_left == 3:
                subject = f"⚠️ Your Library Subscription Expires in {days_left} Days"
                urgency = "HIGH PRIORITY"
            else:
                subject = f"📚 Your Library Subscription Expires in {days_left} Days"
                urgency = "REMINDER"
            
            # Create email content with available plans
            plans_html = self._generate_plans_html(subscription_plans)
            
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Subscription Reminder - {student.library_name if hasattr(student, 'library_name') else 'Library'}</title>
                <style>
                    * {{
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }}
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        background-color: #f8f9fa;
                    }}
                    .email-container {{
                        max-width: 600px;
                        margin: 0 auto;
                        background-color: #ffffff;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    }}
                    .header {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 40px 30px;
                        text-align: center;
                        border-radius: 8px 8px 0 0;
                        position: relative;
                        overflow: hidden;
                    }}
                    .header::before {{
                        content: '';
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        bottom: 0;
                        background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="white" opacity="0.1"/><circle cx="75" cy="75" r="1" fill="white" opacity="0.1"/><circle cx="50" cy="10" r="0.5" fill="white" opacity="0.1"/><circle cx="10" cy="60" r="0.5" fill="white" opacity="0.1"/><circle cx="90" cy="40" r="0.5" fill="white" opacity="0.1"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
                        opacity: 0.3;
                    }}
                    .header-content {{
                        position: relative;
                        z-index: 1;
                    }}
                    .logo {{
                        font-size: 32px;
                        font-weight: 700;
                        margin-bottom: 10px;
                        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                    }}
                    .header h1 {{
                        font-size: 28px;
                        margin-bottom: 10px;
                        font-weight: 600;
                    }}
                    .header p {{
                        font-size: 16px;
                        opacity: 0.9;
                    }}
                    .content {{
                        padding: 40px 30px;
                    }}
                    .greeting {{
                        font-size: 18px;
                        margin-bottom: 20px;
                        color: #2c3e50;
                    }}
                    .urgency-badge {{
                        background: linear-gradient(135deg, #ff6b6b, #ee5a52);
                        color: white;
                        padding: 20px 25px;
                        border-radius: 25px;
                        text-align: center;
                        margin: 25px 0;
                        font-size: 20px;
                        font-weight: 600;
                        box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3);
                    }}
                    .plans-section {{
                        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
                        border: 2px solid #dee2e6;
                        border-radius: 12px;
                        padding: 25px;
                        margin: 25px 0;
                    }}
                    .plans-section h2 {{
                        color: #495057;
                        margin-bottom: 20px;
                        font-size: 22px;
                        text-align: center;
                        border-bottom: 2px solid #dee2e6;
                        padding-bottom: 10px;
                    }}
                    .plan-card {{
                        background: white;
                        border: 2px solid #e0e0e0;
                        border-radius: 12px;
                        padding: 20px;
                        margin: 15px 0;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        transition: transform 0.2s;
                    }}
                    .plan-card:hover {{
                        transform: translateY(-2px);
                        border-color: #667eea;
                    }}
                    .plan-title {{
                        font-size: 20px;
                        font-weight: bold;
                        color: #667eea;
                        margin-bottom: 10px;
                        text-align: center;
                    }}
                    .plan-price {{
                        font-size: 28px;
                        font-weight: bold;
                        color: #28a745;
                        margin: 15px 0;
                        text-align: center;
                    }}
                    .plan-features {{
                        list-style: none;
                        padding: 0;
                        margin: 15px 0;
                    }}
                    .plan-features li {{
                        padding: 8px 0;
                        display: flex;
                        align-items: center;
                    }}
                    .plan-features li:before {{
                        content: "✓";
                        color: #28a745;
                        font-weight: bold;
                        margin-right: 10px;
                        background: #d4edda;
                        border-radius: 50%;
                        width: 20px;
                        height: 20px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 12px;
                    }}
                    .cta-button {{
                        display: inline-block;
                        background: linear-gradient(135deg, #667eea, #764ba2);
                        color: white;
                        padding: 15px 30px;
                        text-decoration: none;
                        border-radius: 25px;
                        font-weight: 600;
                        font-size: 16px;
                        margin: 20px 0;
                        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
                        transition: transform 0.2s;
                        text-align: center;
                    }}
                    .cta-button:hover {{
                        transform: translateY(-2px);
                    }}
                    .benefits-section {{
                        background-color: #e8f5e8;
                        border-radius: 12px;
                        padding: 25px;
                        margin: 25px 0;
                    }}
                    .benefits-section h3 {{
                        color: #2c3e50;
                        margin-bottom: 20px;
                        font-size: 20px;
                        text-align: center;
                    }}
                    .benefits-list {{
                        list-style: none;
                        padding: 0;
                    }}
                    .benefits-list li {{
                        padding: 10px 0;
                        border-bottom: 1px solid #d4edda;
                        display: flex;
                        align-items: center;
                    }}
                    .benefits-list li:last-child {{
                        border-bottom: none;
                    }}
                    .benefit-icon {{
                        background: linear-gradient(135deg, #28a745, #20c997);
                        color: white;
                        width: 30px;
                        height: 30px;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 14px;
                        font-weight: 600;
                        margin-right: 15px;
                        flex-shrink: 0;
                    }}
                    .help-section {{
                        background-color: #f8f9fa;
                        border: 1px solid #dee2e6;
                        border-radius: 8px;
                        padding: 20px;
                        margin: 25px 0;
                    }}
                    .help-section h3 {{
                        color: #495057;
                        margin-bottom: 15px;
                    }}
                    .help-item {{
                        display: flex;
                        align-items: center;
                        padding: 8px 0;
                        color: #6c757d;
                    }}
                    .help-icon {{
                        font-size: 16px;
                        margin-right: 10px;
                        width: 20px;
                    }}
                    .footer {{
                        background: linear-gradient(135deg, #2c3e50, #34495e);
                        color: white;
                        padding: 30px;
                        text-align: center;
                        border-radius: 0 0 8px 8px;
                    }}
                    .footer p {{
                        margin: 5px 0;
                    }}
                    .branding {{
                        margin: 20px 0;
                        padding: 15px;
                        background: rgba(255, 255, 255, 0.1);
                        border-radius: 8px;
                    }}
                    .branding h4 {{
                        font-size: 18px;
                        margin-bottom: 5px;
                    }}
                    .branding p {{
                        font-size: 14px;
                        opacity: 0.8;
                    }}
                    .social-links {{
                        margin: 20px 0;
                    }}
                    .social-links a {{
                        color: white;
                        text-decoration: none;
                        margin: 0 10px;
                        font-size: 18px;
                    }}
                    @media (max-width: 600px) {{
                        .header, .content, .footer {{
                            padding: 20px;
                        }}
                        .logo {{
                            font-size: 24px;
                        }}
                        .header h1 {{
                            font-size: 24px;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="email-container">
                    <div class="header">
                        <div class="header-content">
                            <div class="logo">📚 Library Connekto</div>
                            <h1>⚠️ Subscription Reminder</h1>
                            <p>Don't miss out on your learning journey</p>
                        </div>
                    </div>
                    
                    <div class="content">
                        <div class="greeting">
                            Hello {student.name}!
                        </div>
                        
                        <div class="urgency-badge">
                            {urgency}: Your subscription expires in {days_left} day{'s' if days_left != 1 else ''}!
                        </div>
                        
                        <p style="font-size: 16px; color: #495057; margin-bottom: 20px;">
                            We hope you're enjoying your studies at the library! Your current subscription will expire soon, and we don't want you to miss out on our services.
                        </p>
                        
                        <div class="plans-section">
                            <h2>📋 Available Subscription Plans</h2>
                            {plans_html}
                        </div>
                        
                        <div style="text-align: center;">
                            <a href="{renew_url}" class="cta-button">
                                🔄 Renew Your Subscription Now
                            </a>
                        </div>
                        
                        <div class="benefits-section">
                            <h3>🎯 Why Renew Your Subscription?</h3>
                            <ul class="benefits-list">
                                <li>
                                    <span class="benefit-icon">📚</span>
                                    <span>Continue accessing study materials and resources</span>
                                </li>
                                <li>
                                    <span class="benefit-icon">📈</span>
                                    <span>Maintain your study streak and progress</span>
                                </li>
                                <li>
                                    <span class="benefit-icon">🪑</span>
                                    <span>Keep your seat booking privileges</span>
                                </li>
                                <li>
                                    <span class="benefit-icon">👥</span>
                                    <span>Stay connected with your study community</span>
                                </li>
                            </ul>
                        </div>
                        
                        <div class="help-section">
                            <h3>Need Help?</h3>
                            <div class="help-item">
                                <span class="help-icon">📧</span>
                                <span>Contact us for subscription support</span>
                            </div>
                            <div class="help-item">
                                <span class="help-icon">💬</span>
                                <span>Chat with our support team</span>
                            </div>
                            <div class="help-item">
                                <span class="help-icon">📱</span>
                                <span>Visit our help center</span>
                            </div>
                        </div>
                        
                        <p style="margin-top: 30px; font-size: 16px; color: #495057; text-align: center;">
                            Thank you for choosing <strong>{student.library_name if hasattr(student, 'library_name') else 'our library'}</strong>! We're excited to continue being part of your learning journey.
                        </p>
                    </div>
                    
                    <div class="footer">
                        <div class="branding">
                            <h4>📚 {student.library_name if hasattr(student, 'library_name') else 'Library'}</h4>
                            <p>Your trusted learning partner</p>
                        </div>
                        <p>Powered by <strong>Library Connekto</strong></p>
                        <p>Connecting students with knowledge</p>
                        <div class="social-links">
                            <a href="#">📧</a>
                            <a href="#">📱</a>
                            <a href="#">🌐</a>
                        </div>
                        <p style="font-size: 12px; opacity: 0.8; margin-top: 20px;">
                            This is an automated message. Please do not reply to this email.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            enqueue_email_job(
                db=self.db,
                email_type="generic",
                to_email=student.email,
                payload={
                    "subject": subject,
                    "body": "Please view this email in HTML format for the best experience.",
                    "html_body": html_content,
                },
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to send subscription warning email: {e}")
            return False
    
    def _send_subscription_expired_email(
        self, student: Student, days_expired: int, renew_url: str
    ) -> bool:
        """Send subscription expired email to student"""
        try:
            subscription_plans = self._subscription_plans_for_student(student)

            subject = "❌ Your Library Subscription Has Expired"
            plans_html = self._generate_plans_html(subscription_plans)
            
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Subscription Expired - {student.library_name if hasattr(student, 'library_name') else 'Library'}</title>
                <style>
                    * {{
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }}
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        background-color: #f8f9fa;
                    }}
                    .email-container {{
                        max-width: 600px;
                        margin: 0 auto;
                        background-color: #ffffff;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    }}
                    .header {{
                        background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
                        color: white;
                        padding: 40px 30px;
                        text-align: center;
                        border-radius: 8px 8px 0 0;
                        position: relative;
                        overflow: hidden;
                    }}
                    .header::before {{
                        content: '';
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        bottom: 0;
                        background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="white" opacity="0.1"/><circle cx="75" cy="75" r="1" fill="white" opacity="0.1"/><circle cx="50" cy="10" r="0.5" fill="white" opacity="0.1"/><circle cx="10" cy="60" r="0.5" fill="white" opacity="0.1"/><circle cx="90" cy="40" r="0.5" fill="white" opacity="0.1"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
                        opacity: 0.3;
                    }}
                    .header-content {{
                        position: relative;
                        z-index: 1;
                    }}
                    .logo {{
                        font-size: 32px;
                        font-weight: 700;
                        margin-bottom: 10px;
                        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                    }}
                    .header h1 {{
                        font-size: 28px;
                        margin-bottom: 10px;
                        font-weight: 600;
                    }}
                    .header p {{
                        font-size: 16px;
                        opacity: 0.9;
                    }}
                    .content {{
                        padding: 40px 30px;
                    }}
                    .greeting {{
                        font-size: 18px;
                        margin-bottom: 20px;
                        color: #2c3e50;
                    }}
                    .expired-badge {{
                        background: linear-gradient(135deg, #e74c3c, #c0392b);
                        color: white;
                        padding: 20px 25px;
                        border-radius: 25px;
                        text-align: center;
                        margin: 25px 0;
                        font-size: 20px;
                        font-weight: 600;
                        box-shadow: 0 4px 15px rgba(231, 76, 60, 0.3);
                    }}
                    .plans-section {{
                        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
                        border: 2px solid #dee2e6;
                        border-radius: 12px;
                        padding: 25px;
                        margin: 25px 0;
                    }}
                    .plans-section h2 {{
                        color: #495057;
                        margin-bottom: 20px;
                        font-size: 22px;
                        text-align: center;
                        border-bottom: 2px solid #dee2e6;
                        padding-bottom: 10px;
                    }}
                    .plan-card {{
                        background: white;
                        border: 2px solid #e0e0e0;
                        border-radius: 12px;
                        padding: 20px;
                        margin: 15px 0;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        transition: transform 0.2s;
                    }}
                    .plan-card:hover {{
                        transform: translateY(-2px);
                        border-color: #e74c3c;
                    }}
                    .plan-title {{
                        font-size: 20px;
                        font-weight: bold;
                        color: #e74c3c;
                        margin-bottom: 10px;
                        text-align: center;
                    }}
                    .plan-price {{
                        font-size: 28px;
                        font-weight: bold;
                        color: #28a745;
                        margin: 15px 0;
                        text-align: center;
                    }}
                    .plan-features {{
                        list-style: none;
                        padding: 0;
                        margin: 15px 0;
                    }}
                    .plan-features li {{
                        padding: 8px 0;
                        display: flex;
                        align-items: center;
                    }}
                    .plan-features li:before {{
                        content: "✓";
                        color: #28a745;
                        font-weight: bold;
                        margin-right: 10px;
                        background: #d4edda;
                        border-radius: 50%;
                        width: 20px;
                        height: 20px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 12px;
                    }}
                    .cta-button {{
                        display: inline-block;
                        background: linear-gradient(135deg, #e74c3c, #c0392b);
                        color: white;
                        padding: 15px 30px;
                        text-decoration: none;
                        border-radius: 25px;
                        font-weight: 600;
                        font-size: 16px;
                        margin: 20px 0;
                        box-shadow: 0 4px 15px rgba(231, 76, 60, 0.3);
                        transition: transform 0.2s;
                        text-align: center;
                    }}
                    .cta-button:hover {{
                        transform: translateY(-2px);
                    }}
                    .restrictions-section {{
                        background-color: #f8d7da;
                        border: 1px solid #f5c6cb;
                        border-radius: 12px;
                        padding: 25px;
                        margin: 25px 0;
                    }}
                    .restrictions-section h3 {{
                        color: #721c24;
                        margin-bottom: 20px;
                        font-size: 20px;
                        text-align: center;
                    }}
                    .restrictions-list {{
                        list-style: none;
                        padding: 0;
                    }}
                    .restrictions-list li {{
                        padding: 10px 0;
                        border-bottom: 1px solid #f5c6cb;
                        display: flex;
                        align-items: center;
                    }}
                    .restrictions-list li:last-child {{
                        border-bottom: none;
                    }}
                    .restriction-icon {{
                        background: linear-gradient(135deg, #e74c3c, #c0392b);
                        color: white;
                        width: 30px;
                        height: 30px;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 14px;
                        font-weight: 600;
                        margin-right: 15px;
                        flex-shrink: 0;
                    }}
                    .help-section {{
                        background-color: #f8f9fa;
                        border: 1px solid #dee2e6;
                        border-radius: 8px;
                        padding: 20px;
                        margin: 25px 0;
                    }}
                    .help-section h3 {{
                        color: #495057;
                        margin-bottom: 15px;
                    }}
                    .help-item {{
                        display: flex;
                        align-items: center;
                        padding: 8px 0;
                        color: #6c757d;
                    }}
                    .help-icon {{
                        font-size: 16px;
                        margin-right: 10px;
                        width: 20px;
                    }}
                    .footer {{
                        background: linear-gradient(135deg, #2c3e50, #34495e);
                        color: white;
                        padding: 30px;
                        text-align: center;
                        border-radius: 0 0 8px 8px;
                    }}
                    .footer p {{
                        margin: 5px 0;
                    }}
                    .branding {{
                        margin: 20px 0;
                        padding: 15px;
                        background: rgba(255, 255, 255, 0.1);
                        border-radius: 8px;
                    }}
                    .branding h4 {{
                        font-size: 18px;
                        margin-bottom: 5px;
                    }}
                    .branding p {{
                        font-size: 14px;
                        opacity: 0.8;
                    }}
                    .social-links {{
                        margin: 20px 0;
                    }}
                    .social-links a {{
                        color: white;
                        text-decoration: none;
                        margin: 0 10px;
                        font-size: 18px;
                    }}
                    @media (max-width: 600px) {{
                        .header, .content, .footer {{
                            padding: 20px;
                        }}
                        .logo {{
                            font-size: 24px;
                        }}
                        .header h1 {{
                            font-size: 24px;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="email-container">
                    <div class="header">
                        <div class="header-content">
                            <div class="logo">📚 Library Connekto</div>
                            <h1>❌ Subscription Expired</h1>
                            <p>Restore your access immediately</p>
                        </div>
                    </div>
                    
                    <div class="content">
                        <div class="greeting">
                            Hello {student.name}!
                        </div>
                        
                        <div class="expired-badge">
                            ⚠️ Your library subscription has expired!
                        </div>
                        
                        <p style="font-size: 16px; color: #495057; margin-bottom: 20px;">
                            We're sorry to inform you that your library subscription has expired. To continue enjoying our services, please renew your subscription as soon as possible.
                        </p>
                        
                        <div class="plans-section">
                            <h2>📋 Available Subscription Plans</h2>
                            {plans_html}
                        </div>
                        
                        <div style="text-align: center;">
                            <a href="{renew_url}" class="cta-button">
                                🔄 Renew Your Subscription Now
                            </a>
                        </div>
                        
                        <div class="restrictions-section">
                            <h3>🚫 What happens when your subscription expires?</h3>
                            <ul class="restrictions-list">
                                <li>
                                    <span class="restriction-icon">📚</span>
                                    <span>Access to study materials is restricted</span>
                                </li>
                                <li>
                                    <span class="restriction-icon">🪑</span>
                                    <span>Seat booking privileges are suspended</span>
                                </li>
                                <li>
                                    <span class="restriction-icon">📈</span>
                                    <span>Study progress tracking is paused</span>
                                </li>
                                <li>
                                    <span class="restriction-icon">💬</span>
                                    <span>Communication with library staff is limited</span>
                                </li>
                            </ul>
                        </div>
                        
                        <div class="help-section">
                            <h3>Need Help?</h3>
                            <div class="help-item">
                                <span class="help-icon">📧</span>
                                <span>Contact us for subscription support</span>
                            </div>
                            <div class="help-item">
                                <span class="help-icon">💬</span>
                                <span>Chat with our support team</span>
                            </div>
                            <div class="help-item">
                                <span class="help-icon">📱</span>
                                <span>Visit our help center</span>
                            </div>
                        </div>
                        
                        <p style="margin-top: 30px; font-size: 16px; color: #495057; text-align: center;">
                            Don't let this interrupt your studies! Renew now to restore full access to all library services.
                        </p>
                        
                        <p style="margin-top: 20px; font-size: 16px; color: #495057; text-align: center;">
                            Thank you for choosing <strong>{student.library_name if hasattr(student, 'library_name') else 'our library'}</strong>! We're here to help you continue your learning journey.
                        </p>
                    </div>
                    
                    <div class="footer">
                        <div class="branding">
                            <h4>📚 {student.library_name if hasattr(student, 'library_name') else 'Library'}</h4>
                            <p>Your trusted learning partner</p>
                        </div>
                        <p>Powered by <strong>Library Connekto</strong></p>
                        <p>Connecting students with knowledge</p>
                        <div class="social-links">
                            <a href="#">📧</a>
                            <a href="#">📱</a>
                            <a href="#">🌐</a>
                        </div>
                        <p style="font-size: 12px; opacity: 0.8; margin-top: 20px;">
                            This is an automated message. Please do not reply to this email.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            enqueue_email_job(
                db=self.db,
                email_type="generic",
                to_email=student.email,
                payload={
                    "subject": subject,
                    "body": "Please view this email in HTML format for the best experience.",
                    "html_body": html_content,
                },
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to send subscription expired email: {e}")
            return False
    
    def _generate_plans_html(self, plans: List[SubscriptionPlan]) -> str:
        """Generate HTML for subscription plans"""
        if not plans:
            return "<p>No subscription plans available at the moment. Please contact the library for more information.</p>"
        
        plans_html = ""
        for plan in plans:
            features_html = ""
            if getattr(plan, "is_shift_plan", False) and getattr(plan, "shift_time", None):
                features_html += f"<li>Shift: {plan.shift_time}</li>"
            if getattr(plan, "discounted_amount", None):
                features_html += (
                    f"<li>Special price: ₹{plan.discounted_amount} (Regular: ₹{plan.amount})</li>"
                )
            
            plans_html += f"""
            <div class="plan-card">
                <div class="plan-title">{plan.months} Month{'s' if plan.months > 1 else ''}</div>
                <div class="plan-price">₹{plan.discounted_amount or plan.amount}</div>
                <ul class="plan-features">
                    {features_html}
                </ul>
            </div>
            """
        
        return plans_html
