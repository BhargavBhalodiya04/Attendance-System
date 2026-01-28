from core.generate_attendance_charts import generate_overall_attendance
from core.email_service import send_low_attendance_email
import logging

logger = logging.getLogger(__name__)

def check_and_alert_low_attendance(threshold=75.0):
    """
    Checks attendance for all students and sends an email if below threshold.
    Returns the list of students who were alerted.
    """
    try:
        # Get latest attendance data
        data = generate_overall_attendance()
        students = data.get("students", [])
        
        alerted_students = []
        
        for student in students:
            try:
                percentage = float(student.get("attendance_percentage", 100))
                if percentage < threshold:
                    name = student.get("name", "Student")
                    # For now, we don't have emails in the Excel sheet (presumably).
                    # We will mock it or try to fetch from a mapping if it existed.
                    # TODO: Add email column to Excel or lookup.
                    # For this V1, let's assume we send to a debug email or skip if not found.
                    
                    # ALERT: Since we don't have real student emails, we will log this limitation.
                    # In a real app, we'd look up student['email'].
                    # For demo purposes, we will SKIP sending if we can't find an email,
                    # OR we can assume a pattern like 'firstname@example.com' or just log it.
                    
                    # For the USER to test, they should probably see this occurring.
                    logger.info(f"Student {name} has low attendance: {percentage}%")
                    
                    # We'll try to send to a placeholder or the configured ADMIN email for testing?
                    # Let's try to send to the sender itself (as a test) or just log it if no target.
                    
                    # Temporary: In a real deployment, we need a way to get student email.
                    # I will assume there might be a dictionary or database. 
                    # For now, I will NOT send actual emails to random addresses to avoid spam.
                    # I will return them in the list so the frontend knows who *would* be alerted.
                    
                    student_email = None # define how to get this
                    
                    # If the user wants to test, maybe we send ALL alerts to the ADMIN email?
                    # Let's do that if configured.
                    import os
                    admin_email = os.getenv("MAIL_USERNAME") # Send to self for testing
                    if admin_email:
                        send_low_attendance_email(admin_email, name, percentage)
                        alerted_students.append({
                            "name": name, 
                            "percentage": percentage, 
                            "status": "Email Sent to Admin"
                        })
                    else:
                        alerted_students.append({
                            "name": name, 
                            "percentage": percentage, 
                            "status": "Skipped (No Email Config)"
                        })
                        
            except Exception as inner_e:
                logger.error(f"Error processing student {student}: {inner_e}")
                continue

        return alerted_students

    except Exception as e:
        logger.error(f"Error checking low attendance: {e}")
        raise e
