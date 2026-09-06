"""
Email Service - handles sending verification emails.
Uses SMTP with MailHog for development.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from app.core.config import settings


def send_verification_email(to_email: str, token: str) -> bool:
    """
    Send a verification email to the user.
    
    Args:
        to_email: Recipient email address
        token: Verification token to include in the link
        
    Returns:
        True if email sent successfully, False otherwise
        
    Example:
        >>> send_verification_email("user@example.com", "abc123xyz")
        True
    """
    try:
        # Create verification link
        verification_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        
        # Create email content
        subject = "Verify your email for Trustworthy TA Agent"
        
        # HTML email body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #2563eb; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .button {{ display: inline-block; background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; }}
                .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Trustworthy TA Agent</h1>
                </div>
                <div class="content">
                    <h2>Welcome!</h2>
                    <p>Thank you for registering with Trustworthy TA Agent.</p>
                    <p>Please click the button below to verify your email address:</p>
                    <p style="text-align: center;">
                        <a href="{verification_link}" class="button">Verify Email</a>
                    </p>
                    <p>Or copy and paste this link in your browser:</p>
                    <p><code>{verification_link}</code></p>
                    <p>This link will expire in <strong>24 hours</strong>.</p>
                    <p>If you didn't create an account, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2026 Trustworthy TA Agent. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text fallback
        text_body = f"""
        Welcome to Trustworthy TA Agent!
        
        Please verify your email by clicking the link below:
        {verification_link}
        
        This link will expire in 24 hours.
        
        If you didn't create an account, please ignore this email.
        """
        
        # Create the email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"Trustworthy TA Agent <noreply@{settings.SMTP_HOST}>"
        msg['To'] = to_email
        
        # Attach both plain text and HTML versions
        part1 = MIMEText(text_body, 'plain')
        part2 = MIMEText(html_body, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        # Send the email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            # For MailHog, no authentication needed
            # For production SMTP, uncomment these lines:
            # server.starttls()
            # server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


def send_test_email(to_email: str) -> bool:
    """
    Send a test email to verify SMTP configuration.
    
    Args:
        to_email: Recipient email address
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        subject = "Test Email from Trustworthy TA Agent"
        
        html_body = f"""
        <html>
        <body>
            <h1>SMTP Test Successful!</h1>
            <p>Your email configuration is working correctly.</p>
            <p>Sent at: {__import__('datetime').datetime.now()}</p>
        </body>
        </html>
        """
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"Trustworthy TA Agent <noreply@{settings.SMTP_HOST}>"
        msg['To'] = to_email
        
        part1 = MIMEText("Test email from Trustworthy TA Agent", 'plain')
        part2 = MIMEText(html_body, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.send_message(msg)
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to send test email: {e}")
        return False