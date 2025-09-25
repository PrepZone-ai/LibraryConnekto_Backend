import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
import logging
from typing import Optional, Dict, Any
import asyncio
from datetime import datetime
import time
import random

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.is_configured = bool(self.smtp_host and self.smtp_username and self.smtp_password)
    
    def send_email(self, to_email: str, subject: str, body: str, html_body: Optional[str] = None, max_retries: int = 3) -> Dict[str, Any]:
        """
        Send email with retry mechanism and comprehensive error handling
        Returns: {"success": bool, "message": str, "error": Optional[str], "attempts": int}
        """
        # Enforce a hard cap of 3 attempts regardless of caller input
        try:
            max_retries = int(max_retries)
        except Exception:
            max_retries = 3
        if max_retries < 1:
            max_retries = 1
        if max_retries > 3:
            max_retries = 3
        if not self.is_configured:
            return {
                "success": False,
                "message": "Email service not configured",
                "error": "SMTP settings not configured",
                "attempts": 0
            }
        
        # Create message once (outside retry loop for efficiency)
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.smtp_username
        msg['To'] = to_email
        
        # Add text and HTML parts
        text_part = MIMEText(body, 'plain')
        msg.attach(text_part)
        
        if html_body:
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
        
        last_error = None
        attempts = 0
        
        for attempt in range(1, max_retries + 1):
            attempts = attempt
            try:
                logger.info(f"Attempting to send email to {to_email} (attempt {attempt}/{max_retries})")
                
                # Send email
                if self.smtp_port == 465:
                    # Use SSL for port 465
                    with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30) as server:
                        server.login(self.smtp_username, self.smtp_password)
                        server.sendmail(self.smtp_username, [to_email], msg.as_string())
                else:
                    # Use TLS for other ports (like 587)
                    with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                        server.starttls()
                        server.login(self.smtp_username, self.smtp_password)
                        server.sendmail(self.smtp_username, [to_email], msg.as_string())
                
                logger.info(f"Email sent successfully to {to_email} on attempt {attempt}")
                return {
                    "success": True,
                    "message": f"Email sent successfully to {to_email}",
                    "error": None,
                    "attempts": attempt
                }
                
            except smtplib.SMTPAuthenticationError as e:
                error_msg = f"SMTP authentication failed: {str(e)}"
                last_error = error_msg
                logger.error(f"Attempt {attempt} failed - {error_msg}")
                # Authentication errors are usually not retryable
                break
                
            except smtplib.SMTPRecipientsRefused as e:
                error_msg = f"Recipient email refused: {str(e)}"
                last_error = error_msg
                logger.error(f"Attempt {attempt} failed - {error_msg}")
                # Recipient refused errors are usually not retryable
                break
                
            except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, smtplib.SMTPException) as e:
                # Detect non-retryable SMTP errors (e.g., Gmail daily sending limit exceeded 5.4.5 / 550)
                non_retryable = False
                smtp_code = None
                smtp_text = None
                if isinstance(e, smtplib.SMTPResponseException):
                    smtp_code = getattr(e, "smtp_code", None)
                    smtp_text = getattr(e, "smtp_error", None)
                    if isinstance(smtp_text, (bytes, bytearray)):
                        try:
                            smtp_text = smtp_text.decode("utf-8", errors="ignore")
                        except Exception:
                            smtp_text = str(smtp_text)
                else:
                    smtp_text = str(e)

                # Gmail daily limit pattern: 550 5.4.5 Daily user sending limit exceeded
                if (smtp_code == 550) or (smtp_text and ("5.4.5" in smtp_text and "Daily user sending limit exceeded" in smtp_text)):
                    non_retryable = True

                error_msg = f"SMTP error: code={smtp_code} msg={smtp_text}" if smtp_code or smtp_text else f"SMTP error: {str(e)}"
                last_error = error_msg
                logger.error(f"Attempt {attempt} failed - {error_msg}")
                if non_retryable:
                    logger.info("Non-retryable SMTP error detected; will not retry further.")
                    break
                
                # If this is not the last attempt, wait before retrying
                if attempt < max_retries:
                    # Exponential backoff with jitter
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"Waiting {wait_time:.2f} seconds before retry...")
                    time.sleep(wait_time)
                    
            except Exception as e:
                error_msg = f"Unexpected email error: {str(e)}"
                last_error = error_msg
                logger.error(f"Attempt {attempt} failed - {error_msg}")
                
                # If this is not the last attempt, wait before retrying
                if attempt < max_retries:
                    # Exponential backoff with jitter
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"Waiting {wait_time:.2f} seconds before retry...")
                    time.sleep(wait_time)
        
        # All attempts failed
        logger.error(f"Failed to send email to {to_email} after {attempts} attempts. Last error: {last_error}")
        return {
            "success": False,
            "message": f"Email sending failed after {attempts} attempts",
            "error": last_error,
            "attempts": attempts
        }
    
    def send_email_with_retry(self, to_email: str, subject: str, body: str, html_body: Optional[str] = None, max_retries: int = 3, email_type: str = "general") -> Dict[str, Any]:
        """
        Send email with custom retry count and detailed logging
        """
        logger.info(f"Starting {email_type} email send to {to_email} with {max_retries} max retries")
        result = self.send_email(to_email, subject, body, html_body, max_retries)
        
        if result["success"]:
            logger.info(f"{email_type} email sent successfully to {to_email} after {result['attempts']} attempt(s)")
        else:
            logger.error(f"{email_type} email failed to {to_email} after {result['attempts']} attempts: {result['error']}")
        
        return result
    
    def send_student_password_setup_email(self, email: str, student_id: str, mobile_no: str, token: str, library_name: str, base_url: str) -> Dict[str, Any]:
        """Send password setup email to student with mobile number as initial password"""
        subject = f" Welcome to {library_name} - Set Your Password"
        
        # Create setup URL
        setup_url = f"{base_url}api/v1/student/set-password?token={token}"
        
        # Text version
        text_body = f"""
 WELCOME TO {library_name.upper()}!

Hello!

You have been successfully registered in {library_name}. We're excited to have you join our learning community!

Your Login Details:
- Username (Student ID): {student_id}
- Initial Password: {mobile_no}

IMPORTANT: Please set your own secure password by clicking the link below:
{setup_url}

If the link doesn't work, copy and paste it into your browser.

 This link will expire in 24 hours for security reasons.

What's Next?
1. Set your password using the link above
2. Log in to your account
3. Complete your profile
4. Start your learning journey!

Need Help?
- Contact: [Library Contact Info]
- Support: [Support Email]
- Website: [Library Website]

Best regards,
{library_name} Team
Powered by Library Connekto
        """
        
        # HTML version with beautiful Library Connekto branding
        html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to {library_name} - Set Your Password</title>
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
        .welcome-badge {{
            background: linear-gradient(135deg, #28a745, #20c997);
            color: white;
            padding: 20px 25px;
            border-radius: 25px;
            text-align: center;
            margin: 25px 0;
            font-size: 20px;
            font-weight: 600;
            box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);
        }}
        .login-details {{
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border: 2px solid #dee2e6;
            border-radius: 12px;
            padding: 25px;
            margin: 25px 0;
            position: relative;
        }}
        .login-details::before {{
            content: '';
            position: absolute;
            top: -15px;
            left: 20px;
            background: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .login-details h3 {{
            color: #495057;
            margin-bottom: 20px;
            font-size: 20px;
            border-bottom: 2px solid #dee2e6;
            padding-bottom: 10px;
        }}
        .detail-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }}
        .detail-item {{
            background-color: white;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }}
        .detail-label {{
            font-weight: 600;
            color: #6c757d;
            font-size: 14px;
            margin-bottom: 5px;
        }}
        .detail-value {{
            font-size: 16px;
            color: #2c3e50;
            font-weight: 500;
            font-family: 'Courier New', monospace;
            background-color: #f8f9fa;
            padding: 8px 12px;
            border-radius: 5px;
            border: 1px solid #e9ecef;
        }}
        .password-section {{
            background: linear-gradient(135deg, #fff3cd, #ffeaa7);
            border: 1px solid #ffeaa7;
            border-radius: 12px;
            padding: 25px;
            margin: 25px 0;
            text-align: center;
        }}
        .password-section h3 {{
            color: #856404;
            margin-bottom: 15px;
            font-size: 22px;
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
        }}
        .cta-button:hover {{
            transform: translateY(-2px);
        }}
        .security-notice {{
            background-color: #d1ecf1;
            border: 1px solid #bee5eb;
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
            color: #0c5460;
        }}
        .next-steps {{
            background-color: #e8f5e8;
            border-radius: 12px;
            padding: 25px;
            margin: 25px 0;
        }}
        .next-steps h3 {{
            color: #2c3e50;
            margin-bottom: 20px;
            font-size: 20px;
        }}
        .steps-list {{
            list-style: none;
            padding: 0;
        }}
        .steps-list li {{
            padding: 10px 0;
            border-bottom: 1px solid #d4edda;
            display: flex;
            align-items: center;
        }}
        .steps-list li:last-child {{
            border-bottom: none;
        }}
        .step-number {{
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
            .detail-grid {{
                grid-template-columns: 1fr;
            }}
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
                <div class="logo"> Library Connekto</div>
                <h1> Welcome to {library_name}!</h1>
                <p>Your learning journey starts here</p>
            </div>
        </div>
        
        <div class="content">
            <div class="greeting">
                Hello!
            </div>
            
            <div class="welcome-badge">
                 You have been successfully registered in {library_name}!
            </div>
            
            <p style="font-size: 16px; color: #495057; margin-bottom: 20px;">
                We're excited to have you join our learning community! Your account has been created and you're ready to start your educational journey.
            </p>
            
            <div class="login-details">
                <h3> Your Login Credentials</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Username (Student ID)</div>
                        <div class="detail-value">{student_id}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Initial Password</div>
                        <div class="detail-value">{mobile_no}</div>
                    </div>
                </div>
            </div>
            
            <div class="password-section">
                <h3> Set Your Secure Password</h3>
                <p style="color: #856404; margin-bottom: 20px;">
                    <strong>Important:</strong> Please set your own secure password to protect your account.
                </p>
                
                <a href="{setup_url}" class="cta-button"> Set My Password</a>
                
                <p style="font-size: 14px; color: #856404; margin-top: 15px;">
                    If the button doesn't work, copy and paste this link into your browser:
                </p>
                <p style="word-break: break-all; color: #667eea; font-size: 12px; background: white; padding: 10px; border-radius: 5px; margin: 10px 0;">
                    {setup_url}
                </p>
            </div>
            
            <div class="security-notice">
                <strong> Security Notice:</strong> This password setup link will expire in 24 hours for your security. Please set your password as soon as possible.
            </div>
            
            <div class="next-steps">
                <h3> What's Next?</h3>
                <ul class="steps-list">
                    <li>
                        <span class="step-number">1</span>
                        Set your secure password using the link above
                    </li>
                    <li>
                        <span class="step-number">2</span>
                        Log in to your account with your credentials
                    </li>
                    <li>
                        <span class="step-number">3</span>
                        Complete your profile information
                    </li>
                    <li>
                        <span class="step-number">4</span>
                        Start your learning journey!
                    </li>
                </ul>
            </div>
            
            <div class="help-section">
                <h3> Need Help?</h3>
                <div class="help-item">
                    <span class="help-icon"></span>
                    <span>Contact: [Library Contact Info]</span>
                </div>
                <div class="help-item">
                    <span class="help-icon"></span>
                    <span>Support: [Support Email]</span>
                </div>
                <div class="help-item">
                    <span class="help-icon"></span>
                    <span>Website: [Library Website]</span>
                </div>
            </div>
            
            <p style="margin-top: 30px; font-size: 16px; color: #495057; text-align: center;">
                Thank you for choosing <strong>{library_name}</strong>! We're excited to be part of your learning journey.
            </p>
        </div>
        
        <div class="footer">
            <div class="branding">
                <h4> {library_name}</h4>
                <p>Your trusted learning partner</p>
            </div>
            <p>Powered by <strong>Library Connekto</strong></p>
            <p>Connecting students with knowledge</p>
            <div class="social-links">
                <a href="#"></a>
                <a href="#"></a>
                <a href="#"></a>
            </div>
            <p style="font-size: 12px; opacity: 0.8; margin-top: 20px;">
                This is an automated message. Please do not reply to this email.
            </p>
        </div>
    </div>
</body>
</html>
        """
        
        return self.send_email_with_retry(email, subject, text_body, html_body, max_retries=3, email_type="student_password_setup")

    def send_referral_invitation_email(self, email: str, referrer_name: str, referral_code: str, library_name: str = "", invite_url: str = "") -> Dict[str, Any]:
        """Send a branded referral invitation email with Library Connekto styling"""
        subject = f"{referrer_name} invited you to join {library_name or 'Library Connekto'}"

        # Build CTA link text
        cta_text = invite_url or "Download the app or contact the library to join"

        # Text version (fallback)
        text_body = f"""
You're invited!

{referrer_name} thinks you'll love {library_name or 'our study community'}. Use referral code: {referral_code}.

How to join:
1) Use the referral code during sign-up
2) {cta_text}

Happy learning!
{(library_name + '  ') if library_name else ''}Powered by Library Connekto
        """

        # HTML version with branding
        cta_html = f'<p><a href="{invite_url}" class="cta">Join now</a></p>' if invite_url else ''
        brand_text = f"{library_name} • " if library_name else ""
        
        html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>You're invited to {library_name or 'Library Connekto'}</title>
  <style>
    body {{ background: #0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; margin:0; padding:24px; }}
    .card {{ max-width: 640px; margin: 0 auto; background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(236,72,153,0.12)); border: 1px solid rgba(255,255,255,0.15); border-radius: 16px; padding: 24px; }}
    h1 {{ color: #ffffff; font-size: 22px; margin: 0 0 8px; }}
    p {{ color: rgba(255,255,255,0.8); line-height: 1.6; margin: 0 0 12px; }}
    .code {{ display:inline-block; padding: 10px 14px; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.2); border-radius: 10px; color:#fff; letter-spacing: 2px; font-weight: 700; font-size: 18px; }}
    .cta {{ display:inline-block; margin-top: 16px; padding: 12px 18px; background: linear-gradient(90deg,#10b981,#059669); color:#fff; text-decoration:none; border-radius: 12px; font-weight: 600; }}
    .brand {{ margin-top: 20px; color: rgba(255,255,255,0.6); font-size: 12px; }}
  </style>
  </head>
  <body>
    <div class="card">
      <h1>You're invited to {library_name or 'Library Connekto'}</h1>
      <p><strong style="color:#fff">{referrer_name}</strong> thinks you'll love our study community.</p>
      <p>Use this referral code during sign-up:</p>
      <p class="code">{referral_code}</p>
      {cta_html}
      <p class="brand">{brand_text}Powered by Library Connekto</p>
    </div>
  </body>
</html>
        """

        return self.send_email_with_retry(email, subject, text_body, html_body, max_retries=3, email_type="referral_invitation")
    
    def send_admin_verification_email(self, email: str, token: str, base_url: str) -> Dict[str, Any]:
        """Send verification email to admin"""
        subject = "Verify Your Admin Account"
        
        verify_url = f"{base_url}api/v1/auth/admin/verify-email?token={token}"
        
        text_body = f"""
Hello!

Welcome to the Library Management System!

To verify your email address, please click the following link:
{verify_url}

If the link doesn't work, copy and paste it into your browser.

Best regards,
Library Management Team
        """
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Verify Your Email</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #f8f9fa; padding: 20px; text-align: center; border-radius: 5px; }}
        .content {{ padding: 20px; }}
        .button {{ display: inline-block; padding: 12px 24px; background-color: #28a745; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Welcome to Library Management System!</h2>
        </div>
        <div class="content">
            <p>Hello!</p>
            <p>Welcome to the Library Management System!</p>
            
            <p>To verify your email address, please click the button below:</p>
            
            <a href="{verify_url}" class="button">Verify Email</a>
            
            <p>If the button doesn't work, copy and paste this link into your browser:</p>
            <p style="word-break: break-all; color: #007bff;">{verify_url}</p>
        </div>
        <div class="footer">
            <p>Best regards,<br>Library Management Team</p>
        </div>
    </div>
</body>
</html>
        """
        
        return self.send_email_with_retry(email, subject, text_body, html_body, max_retries=3, email_type="admin_verification")
    
    def send_payment_confirmation_email(self, email: str, student_name: str, library_name: str, 
                                      plan_name: str, amount: float, payment_id: str, 
                                      subscription_end: str, base_url: str = "") -> Dict[str, Any]:
        """Send payment confirmation email with subscription extension details"""
        subject = f" Payment Successful - {plan_name} Subscription Renewed!"
        
        text_body = f"""
Hello {student_name}!

 Great news! Your payment has been processed successfully and your subscription has been renewed.

Payment Details:
- Plan: {plan_name}
- Amount: {amount}
- Payment ID: {payment_id}
- Subscription Valid Until: {subscription_end}

Your library access has been restored and you can continue your studies without interruption.

Thank you for choosing {library_name}!

Best regards,
The {library_name} Team

Powered by Library Connekto
        """
        
        # HTML version with beautiful Library Connekto branding
        html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Confirmation - {library_name}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .email-container {{
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }}
        .header-content {{
            max-width: 500px;
            margin: 0 auto;
        }}
        .logo {{
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 20px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }}
        .header h1 {{
            font-size: 32px;
            margin: 0 0 10px 0;
            font-weight: 700;
        }}
        .header p {{
            font-size: 18px;
            margin: 0;
            opacity: 0.9;
        }}
        .content {{
            padding: 40px 30px;
            background: white;
        }}
        .greeting {{
            font-size: 20px;
            color: #333;
            margin-bottom: 30px;
            font-weight: 600;
        }}
        .success-badge {{
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            margin-bottom: 30px;
            font-size: 18px;
            font-weight: 600;
            box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);
        }}
        .payment-details {{
            background: #f8f9fa;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
            border-left: 5px solid #28a745;
        }}
        .payment-details h3 {{
            color: #333;
            margin: 0 0 20px 0;
            font-size: 20px;
            display: flex;
            align-items: center;
        }}
        .detail-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }}
        .detail-item {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #e9ecef;
        }}
        .detail-label {{
            font-size: 12px;
            color: #6c757d;
            text-transform: uppercase;
            font-weight: 600;
            margin-bottom: 5px;
        }}
        .detail-value {{
            font-size: 16px;
            color: #333;
            font-weight: 600;
        }}
        .subscription-info {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            margin-bottom: 30px;
        }}
        .subscription-info h3 {{
            margin: 0 0 15px 0;
            font-size: 20px;
        }}
        .subscription-end {{
            font-size: 24px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .cta-section {{
            text-align: center;
            margin: 30px 0;
        }}
        .cta-button {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 30px;
            text-decoration: none;
            border-radius: 25px;
            font-weight: 600;
            font-size: 16px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            transition: transform 0.2s ease;
        }}
        .cta-button:hover {{
            transform: translateY(-2px);
        }}
        .features-section {{
            background: #f8f9fa;
            border-radius: 12px;
            padding: 25px;
            margin: 30px 0;
        }}
        .features-section h3 {{
            color: #333;
            margin: 0 0 20px 0;
            font-size: 18px;
            text-align: center;
        }}
        .features-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        .feature-item {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #e9ecef;
        }}
        .feature-icon {{
            font-size: 24px;
            margin-bottom: 10px;
        }}
        .feature-text {{
            font-size: 14px;
            color: #333;
            font-weight: 500;
        }}
        .help-section {{
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 12px;
            padding: 20px;
            margin: 30px 0;
        }}
        .help-section h3 {{
            color: #856404;
            margin: 0 0 15px 0;
            font-size: 18px;
        }}
        .help-item {{
            display: flex;
            align-items: center;
            margin-bottom: 10px;
            color: #856404;
        }}
        .help-icon {{
            margin-right: 10px;
            font-size: 16px;
        }}
        .footer {{
            background: #343a40;
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .branding {{
            margin-bottom: 20px;
        }}
        .branding h4 {{
            margin: 0 0 10px 0;
            font-size: 20px;
        }}
        .branding p {{
            margin: 0;
            opacity: 0.8;
        }}
        .social-links {{
            margin: 20px 0;
        }}
        .social-links a {{
            color: white;
            text-decoration: none;
            margin: 0 10px;
            font-size: 20px;
        }}
        @media (max-width: 600px) {{
            .email-container {{
                margin: 10px;
                border-radius: 10px;
            }}
            .header, .content, .footer {{
                padding: 20px;
            }}
            .logo {{
                font-size: 24px;
            }}
            .header h1 {{
                font-size: 24px;
            }}
            .detail-grid {{
                grid-template-columns: 1fr;
            }}
            .features-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <div class="header-content">
                <div class="logo"> Library Connekto</div>
                <h1> Payment Successful!</h1>
                <p>Your subscription has been renewed</p>
            </div>
        </div>
        
        <div class="content">
            <div class="greeting">
                Hello {student_name}!
            </div>
            
            <div class="success-badge">
                 Payment Processed Successfully!
            </div>
            
            <p style="font-size: 16px; color: #495057; margin-bottom: 20px;">
                Great news! Your payment has been processed successfully and your subscription has been renewed. 
                Your library access has been restored and you can continue your studies without interruption.
            </p>
            
            <div class="payment-details">
                <h3> Payment Details</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Plan Name</div>
                        <div class="detail-value">{plan_name}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Amount Paid</div>
                        <div class="detail-value">{amount}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Payment ID</div>
                        <div class="detail-value">{payment_id}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Payment Date</div>
                        <div class="detail-value">{datetime.now().strftime('%d %B %Y')}</div>
                    </div>
                </div>
            </div>
            
            <div class="subscription-info">
                <h3> Subscription Extension Details</h3>
                <p style="margin: 0 0 10px 0; font-size: 16px;">Your subscription is now valid until:</p>
                <div class="subscription-end">{subscription_end}</div>
                <p style="margin: 10px 0 0 0; font-size: 14px; opacity: 0.9;">
                    You can continue accessing all library services until this date
                </p>
            </div>
            
            <div class="cta-section">
                <a href="{base_url}student/dashboard" class="cta-button"> Access Your Dashboard</a>
            </div>
            
            <div class="features-section">
                <h3> What You Can Access Now</h3>
                <div class="features-grid">
                    <div class="feature-item">
                        <div class="feature-icon"></div>
                        <div class="feature-text">Library Resources</div>
                    </div>
                    <div class="feature-item">
                        <div class="feature-icon"></div>
                        <div class="feature-text">Study Materials</div>
                    </div>
                    <div class="feature-item">
                        <div class="feature-icon"></div>
                        <div class="feature-text">Digital Access</div>
                    </div>
                    <div class="feature-item">
                        <div class="feature-icon"></div>
                        <div class="feature-text">Community Support</div>
                    </div>
                </div>
            </div>
            
            <div class="help-section">
                <h3> Need Help?</h3>
                <div class="help-item">
                    <span class="help-icon"></span>
                    <span>Contact: [Library Contact Info]</span>
                </div>
                <div class="help-item">
                    <span class="help-icon"></span>
                    <span>Support: [Support Email]</span>
                </div>
                <div class="help-item">
                    <span class="help-icon"></span>
                    <span>Website: [Library Website]</span>
                </div>
            </div>
            
            <p style="margin-top: 30px; font-size: 16px; color: #495057; text-align: center;">
                Thank you for choosing <strong>{library_name}</strong>! We're excited to continue supporting your learning journey.
            </p>
        </div>
        
        <div class="footer">
            <div class="branding">
                <h4> {library_name}</h4>
                <p>Your trusted learning partner</p>
            </div>
            <p>Powered by <strong>Library Connekto</strong></p>
            <p>Connecting students with knowledge</p>
            <div class="social-links">
                <a href="#"></a>
                <a href="#"></a>
                <a href="#"></a>
            </div>
            <p style="font-size: 12px; opacity: 0.8; margin-top: 20px;">
                This is an automated message. Please do not reply to this email.
            </p>
        </div>
    </div>
</body>
</html>
        """
        
        return self.send_email_with_retry(email, subject, text_body, html_body, max_retries=3, email_type="payment_confirmation")
    
    def send_booking_approval_email(self, email: str, student_name: str, library_name: str, booking_details: Dict[str, Any], payment_url: str = None) -> Dict[str, Any]:
        """Send booking approval email with payment instructions"""
        subject = f" Your Seat Booking Request Has Been Approved - {library_name}"
        
        # Extract booking details
        amount = booking_details.get('amount', 0)
        subscription_months = booking_details.get('subscription_months', 1)
        booking_date = booking_details.get('created_at', '')
        seat_number = booking_details.get('seat_number', 'TBD')
        
        # Format dates
        if booking_date:
            try:
                from datetime import datetime
                if isinstance(booking_date, str):
                    booking_date = datetime.fromisoformat(booking_date.replace('Z', '+00:00'))
                formatted_date = booking_date.strftime('%B %d, %Y')
            except:
                formatted_date = str(booking_date)
        else:
            formatted_date = 'N/A'
        
        # Text version
        text_body = f"""
Dear {student_name},

 GREAT NEWS! Your seat booking request has been APPROVED!

Your booking details:
- Library: {library_name}
- Subscription: {subscription_months} month{'s' if subscription_months > 1 else ''}
- Amount: {amount}
- Booking Date: {formatted_date}
- Seat Number: {seat_number}

 PAYMENT REQUIRED:
To complete your booking, please make the payment of {amount} as soon as possible.

Payment Method:
 Online Payment (Secure & Instant)

Complete your payment online to activate your subscription immediately.

Your seat will be reserved for 48 hours pending payment confirmation.

Thank you for choosing {library_name}!

Best regards,
{library_name} Team
Powered by Library Connekto
        """
        
        # HTML version with beautiful design
        html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Booking Approved - {library_name}</title>
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
        .approval-badge {{
            background: linear-gradient(135deg, #28a745, #20c997);
            color: white;
            padding: 15px 25px;
            border-radius: 25px;
            text-align: center;
            margin: 25px 0;
            font-size: 18px;
            font-weight: 600;
            box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);
        }}
        .booking-details {{
            background-color: #f8f9fa;
            border: 2px solid #e9ecef;
            border-radius: 12px;
            padding: 25px;
            margin: 25px 0;
        }}
        .booking-details h3 {{
            color: #495057;
            margin-bottom: 20px;
            font-size: 20px;
            border-bottom: 2px solid #dee2e6;
            padding-bottom: 10px;
        }}
        .detail-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }}
        .detail-item {{
            background-color: white;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        .detail-label {{
            font-weight: 600;
            color: #6c757d;
            font-size: 14px;
            margin-bottom: 5px;
        }}
        .detail-value {{
            font-size: 16px;
            color: #2c3e50;
            font-weight: 500;
        }}
        .amount-highlight {{
            background: linear-gradient(135deg, #ff6b6b, #ee5a24);
            color: white;
            border-left-color: #ff6b6b;
        }}
        .payment-section {{
            background: linear-gradient(135deg, #ffd700, #ffed4e);
            border-radius: 12px;
            padding: 25px;
            margin: 25px 0;
            text-align: center;
        }}
        .payment-section h3 {{
            color: #2c3e50;
            margin-bottom: 15px;
            font-size: 22px;
        }}
        .payment-amount {{
            font-size: 32px;
            font-weight: 700;
            color: #2c3e50;
            margin: 15px 0;
        }}
        .payment-methods {{
            background-color: white;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }}
        .payment-method {{
            display: flex;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #e9ecef;
        }}
        .payment-method:last-child {{
            border-bottom: none;
        }}
        .method-icon {{
            font-size: 20px;
            margin-right: 15px;
            width: 30px;
        }}
        .method-text {{
            font-weight: 500;
            color: #495057;
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
        }}
        .cta-button:hover {{
            transform: translateY(-2px);
        }}
        .urgency-notice {{
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
            color: #856404;
        }}
        .footer {{
            background-color: #2c3e50;
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 0 0 8px 8px;
        }}
        .footer p {{
            margin: 5px 0;
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
            .detail-grid {{
                grid-template-columns: 1fr;
            }}
            .header, .content, .footer {{
                padding: 20px;
            }}
            .payment-amount {{
                font-size: 28px;
            }}
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1> Booking Approved!</h1>
            <p>Your seat booking request has been accepted</p>
        </div>
        
        <div class="content">
            <div class="greeting">
                Dear <strong>{student_name}</strong>,
            </div>
            
            <div class="approval-badge">
                 Your seat booking request has been APPROVED!
            </div>
            
            <div class="booking-details">
                <h3> Your Booking Details</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Library</div>
                        <div class="detail-value">{library_name}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Subscription Duration</div>
                        <div class="detail-value">{subscription_months} month{'s' if subscription_months > 1 else ''}</div>
                    </div>
                    <div class="detail-item amount-highlight">
                        <div class="detail-label">Amount to Pay</div>
                        <div class="detail-value">{amount}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Booking Date</div>
                        <div class="detail-value">{formatted_date}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Seat Number</div>
                        <div class="detail-value">{seat_number}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Status</div>
                        <div class="detail-value" style="color: #28a745; font-weight: 600;"> Approved</div>
                    </div>
                </div>
            </div>
            
            <div class="payment-section">
                <h3> Payment Required</h3>
                <div class="payment-amount">{amount}</div>
                <p>To complete your booking, please make the payment as soon as possible.</p>
                
                <div class="payment-methods">
                    <div class="payment-method">
                        <span class="method-icon"></span>
                        <span class="method-text">Online Payment (Secure & Instant)</span>
                    </div>
                </div>
                <p style="margin-top: 15px; font-size: 14px; color: #495057;">
                    Complete your payment online to activate your subscription immediately.
                </p>
                
                {f'<a href="{payment_url}" class="cta-button"> Make Payment Now</a>' if payment_url else ''}
            </div>
            
            <div class="urgency-notice">
                <strong> Important:</strong> Your seat will be reserved for 48 hours pending payment confirmation. Please complete the payment soon to secure your booking.
            </div>
            
            <p style="margin-top: 30px; font-size: 16px; color: #495057;">
                Thank you for choosing <strong>{library_name}</strong>! We look forward to serving you.
            </p>
        </div>
        
        <div class="footer">
            <p><strong>{library_name}</strong></p>
            <p>Powered by <strong>Library Connekto</strong></p>
            <p>Your trusted learning partner</p>
            <div class="social-links">
                <a href="#"></a>
                <a href="#"></a>
                <a href="#"></a>
            </div>
            <p style="font-size: 12px; opacity: 0.8; margin-top: 20px;">
                This is an automated message. Please do not reply to this email.
            </p>
        </div>
    </div>
</body>
</html>
        """
        
        return self.send_email_with_retry(email, subject, text_body, html_body, max_retries=3, email_type="booking_approval")
    
    def send_booking_payment_confirmation_email(self, email: str, student_name: str, library_name: str, booking_details: Dict[str, Any]) -> Dict[str, Any]:
        """Send booking payment confirmation email with welcome message"""
        subject = f" Payment Confirmed - Welcome to {library_name}!"
        
        # Extract booking details
        amount = booking_details.get('amount', 0)
        subscription_months = booking_details.get('subscription_months', 1)
        payment_method = booking_details.get('payment_method', 'Unknown')
        payment_reference = booking_details.get('payment_reference', '')
        subscription_start = booking_details.get('subscription_start', '')
        subscription_end = booking_details.get('subscription_end', '')
        
        # Format dates
        def format_date(date_obj):
            if date_obj:
                try:
                    if isinstance(date_obj, str):
                        date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
                    return date_obj.strftime('%B %d, %Y')
                except:
                    return str(date_obj)
            return 'N/A'
        
        formatted_start = format_date(subscription_start)
        formatted_end = format_date(subscription_end)
        
        # Text version
        text_body = f"""
Dear {student_name},

 WELCOME TO {library_name.upper()}!

Your payment has been successfully confirmed and your subscription is now ACTIVE!

Payment Details:
- Amount Paid: {amount}
- Payment Method: Online Payment (Secure & Instant)
- Transaction Reference: {payment_reference}
- Subscription Duration: {subscription_months} month{'s' if subscription_months > 1 else ''}

Your Subscription:
- Start Date: {formatted_start}
- End Date: {formatted_end}
- Status:  ACTIVE

You can now:
 Access the library facilities
 Use your assigned seat
 Attend library sessions
 Access online resources

Next Steps:
1. Visit the library with a valid ID
2. Complete your registration process
3. Get your student ID card
4. Start your learning journey!

Library Contact:
- Address: [Library Address]
- Phone: [Library Phone]
- Email: [Library Email]

Thank you for choosing {library_name}! We're excited to be part of your learning journey.

Best regards,
{library_name} Team
Powered by Library Connekto
        """
        
        # HTML version with beautiful design
        html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Confirmed - Welcome to {library_name}</title>
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
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
            border-radius: 8px 8px 0 0;
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
        .welcome-badge {{
            background: linear-gradient(135deg, #28a745, #20c997);
            color: white;
            padding: 20px 25px;
            border-radius: 25px;
            text-align: center;
            margin: 25px 0;
            font-size: 20px;
            font-weight: 600;
            box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);
        }}
        .payment-details {{
            background-color: #f8f9fa;
            border: 2px solid #e9ecef;
            border-radius: 12px;
            padding: 25px;
            margin: 25px 0;
        }}
        .payment-details h3 {{
            color: #495057;
            margin-bottom: 20px;
            font-size: 20px;
            border-bottom: 2px solid #dee2e6;
            padding-bottom: 10px;
        }}
        .detail-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }}
        .detail-item {{
            background-color: white;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #28a745;
        }}
        .detail-label {{
            font-weight: 600;
            color: #6c757d;
            font-size: 14px;
            margin-bottom: 5px;
        }}
        .detail-value {{
            font-size: 16px;
            color: #2c3e50;
            font-weight: 500;
        }}
        .subscription-section {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border-radius: 12px;
            padding: 25px;
            margin: 25px 0;
            text-align: center;
        }}
        .subscription-section h3 {{
            margin-bottom: 15px;
            font-size: 22px;
        }}
        .subscription-dates {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 20px 0;
        }}
        .date-item {{
            background-color: rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 8px;
        }}
        .date-label {{
            font-size: 14px;
            opacity: 0.8;
            margin-bottom: 5px;
        }}
        .date-value {{
            font-size: 18px;
            font-weight: 600;
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
            font-size: 20px;
            margin-right: 15px;
            width: 30px;
        }}
        .next-steps {{
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 8px;
            padding: 20px;
            margin: 25px 0;
        }}
        .next-steps h3 {{
            color: #856404;
            margin-bottom: 15px;
        }}
        .steps-list {{
            list-style: none;
            padding: 0;
        }}
        .steps-list li {{
            padding: 8px 0;
            color: #856404;
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
        }}
        .footer {{
            background-color: #2c3e50;
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 0 0 8px 8px;
        }}
        .footer p {{
            margin: 5px 0;
        }}
        @media (max-width: 600px) {{
            .detail-grid, .subscription-dates {{
                grid-template-columns: 1fr;
            }}
            .header, .content, .footer {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1> Payment Confirmed!</h1>
            <p>Welcome to {library_name}</p>
        </div>
        
        <div class="content">
            <div class="greeting">
                Dear <strong>{student_name}</strong>,
            </div>
            
            <div class="welcome-badge">
                 WELCOME TO {library_name.upper()}!
            </div>
            
            <div class="payment-details">
                <h3> Payment Details</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Amount Paid</div>
                        <div class="detail-value">{amount}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Payment Method</div>
                        <div class="detail-value">Online Payment (Secure & Instant)</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Transaction Reference</div>
                        <div class="detail-value">{payment_reference or 'N/A'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Subscription Duration</div>
                        <div class="detail-value">{subscription_months} month{'s' if subscription_months > 1 else ''}</div>
                    </div>
                </div>
            </div>
            
            <div class="subscription-section">
                <h3> Your Active Subscription</h3>
                <div class="subscription-dates">
                    <div class="date-item">
                        <div class="date-label">Start Date</div>
                        <div class="date-value">{formatted_start}</div>
                    </div>
                    <div class="date-item">
                        <div class="date-label">End Date</div>
                        <div class="date-value">{formatted_end}</div>
                    </div>
                </div>
                <p style="font-size: 18px; font-weight: 600; margin-top: 15px;"> Status: ACTIVE</p>
            </div>
            
            <div class="benefits-section">
                <h3> What You Can Do Now</h3>
                <ul class="benefits-list">
                    <li><span class="benefit-icon"></span>Access the library facilities</li>
                    <li><span class="benefit-icon"></span>Use your assigned seat</li>
                    <li><span class="benefit-icon"></span>Attend library sessions</li>
                    <li><span class="benefit-icon"></span>Access online resources</li>
                    <li><span class="benefit-icon"></span>Borrow books and materials</li>
                    <li><span class="benefit-icon"></span>Join study groups</li>
                </ul>
            </div>
            
            <div class="next-steps">
                <h3> Next Steps</h3>
                <ol class="steps-list">
                    <li>1. Visit the library with a valid ID</li>
                    <li>2. Complete your registration process</li>
                    <li>3. Get your student ID card</li>
                    <li>4. Start your learning journey!</li>
                </ol>
            </div>
            
            <p style="margin-top: 30px; font-size: 16px; color: #495057; text-align: center;">
                Thank you for choosing <strong>{library_name}</strong>! We're excited to be part of your learning journey.
            </p>
        </div>
        
        <div class="footer">
            <p><strong>{library_name}</strong></p>
            <p>Powered by <strong>Library Connekto</strong></p>
            <p>Your trusted learning partner</p>
            <p style="font-size: 12px; opacity: 0.8; margin-top: 20px;">
                This is an automated message. Please do not reply to this email.
            </p>
        </div>
    </div>
</body>
</html>
        """
        
        return self.send_email_with_retry(email, subject, text_body, html_body, max_retries=3, email_type="payment_confirmation")
    
    def send_booking_submission_email(self, email: str, student_name: str, library_name: str, booking_details: Dict[str, Any]) -> Dict[str, Any]:
        """Send booking submission confirmation email to student"""
        subject = f" Seat Booking Request Submitted - {library_name}"
        
        # Extract booking details
        amount = booking_details.get('amount', 0)
        subscription_months = booking_details.get('subscription_months', 1)
        booking_date = booking_details.get('created_at', '')
        
        # Format dates
        if booking_date:
            try:
                if isinstance(booking_date, str):
                    booking_date = datetime.fromisoformat(booking_date.replace('Z', '+00:00'))
                formatted_date = booking_date.strftime('%B %d, %Y at %I:%M %p')
            except:
                formatted_date = str(booking_date)
        else:
            formatted_date = 'N/A'
        
        # Text version
        text_body = f"""
Dear {student_name},

 Your seat booking request has been successfully submitted!

Booking Details:
- Library: {library_name}
- Subscription Duration: {subscription_months} month{'s' if subscription_months > 1 else ''}
- Amount: {amount}
- Submission Date: {formatted_date}
- Status:  Pending Review

What happens next:
1. Our admin team will review your request
2. You'll receive an email notification once reviewed
3. If approved, you'll get payment instructions
4. Complete payment to activate your subscription

Your request is now in our system and will be processed within 24 hours.

Thank you for choosing {library_name}!

Best regards,
{library_name} Team
Powered by Library Connekto
        """
        
        # HTML version with beautiful design
        html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Booking Request Submitted - {library_name}</title>
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
        .submission-badge {{
            background: linear-gradient(135deg, #17a2b8, #138496);
            color: white;
            padding: 20px 25px;
            border-radius: 25px;
            text-align: center;
            margin: 25px 0;
            font-size: 20px;
            font-weight: 600;
            box-shadow: 0 4px 15px rgba(23, 162, 184, 0.3);
        }}
        .booking-details {{
            background-color: #f8f9fa;
            border: 2px solid #e9ecef;
            border-radius: 12px;
            padding: 25px;
            margin: 25px 0;
        }}
        .booking-details h3 {{
            color: #495057;
            margin-bottom: 20px;
            font-size: 20px;
            border-bottom: 2px solid #dee2e6;
            padding-bottom: 10px;
        }}
        .detail-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }}
        .detail-item {{
            background-color: white;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #17a2b8;
        }}
        .detail-label {{
            font-weight: 600;
            color: #6c757d;
            font-size: 14px;
            margin-bottom: 5px;
        }}
        .detail-value {{
            font-size: 16px;
            color: #2c3e50;
            font-weight: 500;
        }}
        .status-badge {{
            background: linear-gradient(135deg, #ffc107, #e0a800);
            color: #212529;
            padding: 10px 20px;
            border-radius: 20px;
            text-align: center;
            margin: 20px 0;
            font-weight: 600;
        }}
        .next-steps {{
            background-color: #e7f3ff;
            border: 1px solid #b3d9ff;
            border-radius: 8px;
            padding: 20px;
            margin: 25px 0;
        }}
        .next-steps h3 {{
            color: #0056b3;
            margin-bottom: 15px;
        }}
        .steps-list {{
            list-style: none;
            padding: 0;
        }}
        .steps-list li {{
            padding: 8px 0;
            color: #0056b3;
            display: flex;
            align-items: center;
        }}
        .step-number {{
            background-color: #0056b3;
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 600;
            margin-right: 15px;
            flex-shrink: 0;
        }}
        .footer {{
            background-color: #2c3e50;
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 0 0 8px 8px;
        }}
        .footer p {{
            margin: 5px 0;
        }}
        @media (max-width: 600px) {{
            .detail-grid {{
                grid-template-columns: 1fr;
            }}
            .header, .content, .footer {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1> Request Submitted!</h1>
            <p>Your seat booking request is under review</p>
        </div>
        
        <div class="content">
            <div class="greeting">
                Dear <strong>{student_name}</strong>,
            </div>
            
            <div class="submission-badge">
                 Your seat booking request has been successfully submitted!
            </div>
            
            <div class="booking-details">
                <h3> Booking Details</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Library</div>
                        <div class="detail-value">{library_name}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Subscription Duration</div>
                        <div class="detail-value">{subscription_months} month{'s' if subscription_months > 1 else ''}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Amount</div>
                        <div class="detail-value">{amount}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Submission Date</div>
                        <div class="detail-value">{formatted_date}</div>
                    </div>
                </div>
            </div>
            
            <div class="status-badge">
                 Status: Pending Review
            </div>
            
            <div class="next-steps">
                <h3> What happens next?</h3>
                <ul class="steps-list">
                    <li>
                        <span class="step-number">1</span>
                        Our admin team will review your request
                    </li>
                    <li>
                        <span class="step-number">2</span>
                        You'll receive an email notification once reviewed
                    </li>
                    <li>
                        <span class="step-number">3</span>
                        If approved, you'll get payment instructions
                    </li>
                    <li>
                        <span class="step-number">4</span>
                        Complete payment to activate your subscription
                    </li>
                </ul>
            </div>
            
            <p style="margin-top: 30px; font-size: 16px; color: #495057; text-align: center;">
                Your request is now in our system and will be processed within <strong>24 hours</strong>.
            </p>
            
            <p style="margin-top: 20px; font-size: 16px; color: #495057; text-align: center;">
                Thank you for choosing <strong>{library_name}</strong>!
            </p>
        </div>
        
        <div class="footer">
            <p><strong>{library_name}</strong></p>
            <p>Powered by <strong>Library Connekto</strong></p>
            <p>Your trusted learning partner</p>
            <p style="font-size: 12px; opacity: 0.8; margin-top: 20px;">
                This is an automated message. Please do not reply to this email.
            </p>
        </div>
    </div>
</body>
</html>
        """
        
        return self.send_email_with_retry(email, subject, text_body, html_body, max_retries=3, email_type="booking_submission")
    
    def send_booking_rejection_email(self, email: str, student_name: str, library_name: str, booking_details: Dict[str, Any], rejection_reason: str = None) -> Dict[str, Any]:
        """Send booking rejection email to student"""
        subject = f" Seat Booking Request Update - {library_name}"
        
        # Extract booking details
        amount = booking_details.get('amount', 0)
        subscription_months = booking_details.get('subscription_months', 1)
        booking_date = booking_details.get('created_at', '')
        
        # Format dates
        if booking_date:
            try:
                if isinstance(booking_date, str):
                    booking_date = datetime.fromisoformat(booking_date.replace('Z', '+00:00'))
                formatted_date = booking_date.strftime('%B %d, %Y')
            except:
                formatted_date = str(booking_date)
        else:
            formatted_date = 'N/A'
        
        # Default rejection reason if not provided
        if not rejection_reason:
            rejection_reason = "Unfortunately, we are unable to accommodate your request at this time due to capacity constraints."
        
        # Text version
        text_body = f"""
Dear {student_name},

 Your seat booking request has been reviewed and we regret to inform you that it cannot be approved at this time.

Booking Details:
- Library: {library_name}
- Subscription Duration: {subscription_months} month{'s' if subscription_months > 1 else ''}
- Amount: {amount}
- Booking Date: {formatted_date}
- Status:  Rejected

Reason: {rejection_reason}

What you can do:
1. Try booking for a different time period
2. Contact us for alternative arrangements
3. Check back later for availability updates

We apologize for any inconvenience and hope to serve you in the future.

Thank you for your interest in {library_name}.

Best regards,
{library_name} Team
Powered by Library Connekto
        """
        
        # HTML version with beautiful design
        html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Booking Request Update - {library_name}</title>
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
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
            border-radius: 8px 8px 0 0;
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
        .rejection-badge {{
            background: linear-gradient(135deg, #dc3545, #c82333);
            color: white;
            padding: 20px 25px;
            border-radius: 25px;
            text-align: center;
            margin: 25px 0;
            font-size: 20px;
            font-weight: 600;
            box-shadow: 0 4px 15px rgba(220, 53, 69, 0.3);
        }}
        .booking-details {{
            background-color: #f8f9fa;
            border: 2px solid #e9ecef;
            border-radius: 12px;
            padding: 25px;
            margin: 25px 0;
        }}
        .booking-details h3 {{
            color: #495057;
            margin-bottom: 20px;
            font-size: 20px;
            border-bottom: 2px solid #dee2e6;
            padding-bottom: 10px;
        }}
        .detail-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }}
        .detail-item {{
            background-color: white;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #dc3545;
        }}
        .detail-label {{
            font-weight: 600;
            color: #6c757d;
            font-size: 14px;
            margin-bottom: 5px;
        }}
        .detail-value {{
            font-size: 16px;
            color: #2c3e50;
            font-weight: 500;
        }}
        .status-badge {{
            background: linear-gradient(135deg, #dc3545, #c82333);
            color: white;
            padding: 10px 20px;
            border-radius: 20px;
            text-align: center;
            margin: 20px 0;
            font-weight: 600;
        }}
        .reason-section {{
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 8px;
            padding: 20px;
            margin: 25px 0;
        }}
        .reason-section h3 {{
            color: #721c24;
            margin-bottom: 15px;
        }}
        .reason-text {{
            color: #721c24;
            font-style: italic;
        }}
        .alternatives {{
            background-color: #d1ecf1;
            border: 1px solid #bee5eb;
            border-radius: 8px;
            padding: 20px;
            margin: 25px 0;
        }}
        .alternatives h3 {{
            color: #0c5460;
            margin-bottom: 15px;
        }}
        .alternatives-list {{
            list-style: none;
            padding: 0;
        }}
        .alternatives-list li {{
            padding: 8px 0;
            color: #0c5460;
            display: flex;
            align-items: center;
        }}
        .alternative-icon {{
            font-size: 16px;
            margin-right: 15px;
            width: 20px;
        }}
        .footer {{
            background-color: #2c3e50;
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 0 0 8px 8px;
        }}
        .footer p {{
            margin: 5px 0;
        }}
        @media (max-width: 600px) {{
            .detail-grid {{
                grid-template-columns: 1fr;
            }}
            .header, .content, .footer {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1> Request Update</h1>
            <p>Your seat booking request has been reviewed</p>
        </div>
        
        <div class="content">
            <div class="greeting">
                Dear <strong>{student_name}</strong>,
            </div>
            
            <div class="rejection-badge">
                 Your seat booking request cannot be approved at this time
            </div>
            
            <div class="booking-details">
                <h3> Booking Details</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Library</div>
                        <div class="detail-value">{library_name}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Subscription Duration</div>
                        <div class="detail-value">{subscription_months} month{'s' if subscription_months > 1 else ''}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Amount</div>
                        <div class="detail-value">{amount}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Booking Date</div>
                        <div class="detail-value">{formatted_date}</div>
                    </div>
                </div>
            </div>
            
            <div class="status-badge">
                 Status: Rejected
            </div>
            
            <div class="reason-section">
                <h3> Reason</h3>
                <p class="reason-text">{rejection_reason}</p>
            </div>
            
            <div class="alternatives">
                <h3> What you can do</h3>
                <ul class="alternatives-list">
                    <li><span class="alternative-icon"></span>Try booking for a different time period</li>
                    <li><span class="alternative-icon"></span>Contact us for alternative arrangements</li>
                    <li><span class="alternative-icon"></span>Check back later for availability updates</li>
                </ul>
            </div>
            
            <p style="margin-top: 30px; font-size: 16px; color: #495057; text-align: center;">
                We apologize for any inconvenience and hope to serve you in the future.
            </p>
            
            <p style="margin-top: 20px; font-size: 16px; color: #495057; text-align: center;">
                Thank you for your interest in <strong>{library_name}</strong>.
            </p>
        </div>
        
        <div class="footer">
            <p><strong>{library_name}</strong></p>
            <p>Powered by <strong>Library Connekto</strong></p>
            <p>Your trusted learning partner</p>
            <p style="font-size: 12px; opacity: 0.8; margin-top: 20px;">
                This is an automated message. Please do not reply to this email.
            </p>
        </div>
    </div>
</body>
</html>
        """
        
        return self.send_email_with_retry(email, subject, text_body, html_body, max_retries=3, email_type="booking_rejection")

# Global email service instance
email_service = EmailService() 