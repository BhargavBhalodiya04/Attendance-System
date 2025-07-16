import os
from openpyxl import Workbook, load_workbook
from datetime import datetime
from core.upload_to_s3 import upload_file_to_s3  # ⬅️ DO NOT REMOVE

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

    # ✅ Upload Excel to ROOT of the S3 bucket
    upload_file_to_s3(bucket_name, EXCEL_FILE, 'students.xlsx')
