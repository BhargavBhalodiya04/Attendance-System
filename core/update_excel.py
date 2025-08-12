import os
from openpyxl import Workbook, load_workbook
from datetime import datetime
from botocore.exceptions import ClientError
from core.upload_to_s3 import upload_file_to_s3, s3  # assuming s3 client is in core.upload_to_s3

EXCEL_FILE = 'students.xlsx'

def delete_excel_from_s3(bucket_name, s3_key='students.xlsx'):
    """Delete Excel file from S3 if it exists."""
    try:
        s3.delete_object(Bucket=bucket_name, Key=s3_key)
        print(f"✅ Deleted {s3_key} from S3 bucket '{bucket_name}'.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print("ℹ️ No previous Excel file found in S3.")
        else:
            raise

def reset_excel_file(bucket_name):
    """Delete old Excel from S3 and create a fresh one with only headers."""
    # Delete from S3
    delete_excel_from_s3(bucket_name)

    # Create fresh workbook
    wb = Workbook()
    default_sheet = wb.active
    default_sheet.title = bucket_name
    default_sheet.append(["ER Number", "Student Name", "Upload Date & Time"])
    wb.save(EXCEL_FILE)

    # Upload fresh file to S3
    upload_file_to_s3(bucket_name, EXCEL_FILE, 'students.xlsx')
    print("✅ New empty Excel file created and uploaded to S3.")

def update_student_excel(bucket_name, er_number, student_name):
    """Update Excel with new student entry and upload to S3."""
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
    """
    return [
        "✅ Local: Student1 matched and marked present",
        "❌ Local: Student2 face not found"
    ]
