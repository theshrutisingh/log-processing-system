import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import string
import email_config

def generate_otp(length=6):
    """Generate a random numeric OTP."""
    return ''.join(random.choices(string.digits, k=length))

def send_otp_email(receiver_email, otp):
    """
    Send OTP to the user's email address.
    Returns True if successful, False otherwise.
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = email_config.SENDER_EMAIL
        msg['To'] = receiver_email
        msg['Subject'] = "Password Reset OTP - Log Analytics Portal"

        body = f"""
        <html>
          <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;">
              <h2 style="color: #0D9488; margin-top: 0;">Password Reset Request</h2>
              <p>Hello,</p>
              <p>We received a request to reset your password for the Log Analytics Portal.</p>
              <p>Your One-Time Password (OTP) is:</p>
              <div style="background-color: #F8FAFC; padding: 15px; text-align: center; border-radius: 6px; margin: 20px 0;">
                <span style="font-size: 24px; font-weight: bold; letter-spacing: 4px; color: #1E293B;">{otp}</span>
              </div>
              <p>This code is valid for 10 minutes. If you did not request a password reset, please ignore this email.</p>
              <p style="font-size: 0.8rem; color: #64748B; margin-top: 30px;">
                Log Analytics Infrastructure Security Team
              </p>
            </div>
          </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))

        # Standard SMTP (Gmail uses STARTTLS on 587)
        server = smtplib.SMTP(email_config.SMTP_SERVER, email_config.SMTP_PORT)
        server.starttls()
        server.login(email_config.SENDER_EMAIL, email_config.SENDER_PASSWORD)
        text = msg.as_string()
        server.sendmail(email_config.SENDER_EMAIL, receiver_email.strip(), text)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send OTP email: {e}")
        return False
