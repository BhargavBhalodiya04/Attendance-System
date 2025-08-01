import os
from openpyxl import Workbook, load_workbook
from datetime import datetime
from core.upload_to_s3 import upload_file_to_s3

EXCEL_FILE = 'students.xlsx'

def update_student_excel(bucket_name, er_number, student_name):
    # Create or load workbook
    if os.path.exists(EXCEL_FILE):
        wb = load_workbook(EXCEL_FILE)
    else:
        wb = Workbook()
        default_sheet = wb.active
        wb.remove(default_sheet)

    # Sheet name = bucket name
    if bucket_name in wb.sheetnames:
        sheet = wb[bucket_name]
    else:
        sheet = wb.create_sheet(bucket_name)
        sheet.append(["ER Number", "Student Name", "Upload Date & Time"])

    # Add new row
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sheet.append([er_number, student_name, current_time])
    wb.save(EXCEL_FILE)

    upload_file_to_s3(bucket_name, EXCEL_FILE, 'students.xlsx')

def mark_attendance_local():
    """
    Dummy placeholder function for local attendance marking.
    Replace this with your actual attendance logic if needed.
    Returns a list of result strings to display to users.
    """
    return [
        "✅ Local: Student1 matched and marked present",
        "❌ Local: Student2 face not found"
    ]