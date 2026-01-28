import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_low_attendance_email(student_email, student_name, percentage, course_name="Course"):
    """
    Sends a low attendance warning email to the student.
    """
    sender_email = os.getenv("MAIL_USERNAME")
    sender_password = os.getenv("MAIL_PASSWORD")
    smtp_server = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("MAIL_PORT", 587))

    if not sender_email or not sender_password:
        logger.warning("❌ Email credentials not set in .env. Skipping email dispatch.")
        return False

    subject = f"⚠️ Low Attendance Warning: {int(percentage)}%"
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
            <h2 style="color: #d9534f;">Low Attendance Alert</h2>
            <p>Dear <strong>{student_name}</strong>,</p>
            <p>This is an automated alert to inform you that your attendance in <strong>{course_name}</strong> has dropped below the required threshold.</p>
            
            <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center;">
                <p style="margin: 0; font-size: 16px;">Current Attendance:</p>
                <h1 style="color: #d9534f; margin: 5px 0;">{percentage}%</h1>
                <p style="margin: 0; font-size: 14px; color: #777;">Threshold: 75%</p>
            </div>

            <p>Please ensure you attend upcoming classes to avoid any academic penalties.</p>
            <p>If you believe this is an error, please contact your faculty immediately.</p>
            
            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; color: #999;">Attendance System Automated Message</p>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = student_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_content, "html"))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, student_email, msg.as_string())
        server.quit()
        logger.info(f"✅ Email sent successfully to {student_email}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send email to {student_email}: {e}")
        return False
