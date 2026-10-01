"""
Email service for sending emails.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, html_content: str):
    """Send an email using SMTP."""
    try:
        msg = MIMEMultipart()
        msg['From'] = settings.SMTP_USERNAME or "noreply@trustworthy-ta.com"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_verification_email(to_email: str, token: str):
    """Send verification email to user."""
    verification_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    
    html_content = f"""
    <html>
        <body>
            <h1>Welcome to Trustworthy TA Agent!</h1>
            <p>Please click the link below to verify your email address:</p>
            <a href="{verification_link}">Verify Email</a>
            <p>This link will expire in 24 hours.</p>
        </body>
    </html>
    """
    
    return send_email(to_email, "Verify Your Email", html_content)


def send_password_reset_email(to_email: str, token: str):
    """Send password reset email to user."""
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    
    html_content = f"""
    <html>
        <body>
            <h1>Password Reset Request</h1>
            <p>You requested to reset your password. Click the link below:</p>
            <a href="{reset_link}">Reset Password</a>
            <p>This link will expire in 24 hours.</p>
            <p>If you didn't request this, ignore this email.</p>
        </body>
    </html>
    """
    
    return send_email(to_email, "Password Reset Request", html_content)