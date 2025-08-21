import os
import boto3
from openpyxl import Workbook
from dotenv import load_dotenv
from botocore.exceptions import ClientError

# Load environment variables
load_dotenv()

# Local Excel file
EXCEL_FILE = "students.xlsx"

# AWS config from .env
AWS_REGION = os.getenv("AWS_REGION")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
BUCKET_NAME = os.getenv("S3_BUCKET", "ict-attendance")
EXCEL_KEY = "students.xlsx"   # key inside bucket

# Init S3 client
s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)


def download_excel_from_s3():
    """Download Excel file from S3 if exists"""
    try:
        s3.download_file(BUCKET_NAME, EXCEL_KEY, EXCEL_FILE)
        print(f"⬇️ Downloaded {EXCEL_KEY} from S3")
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            print("⚠️ No Excel file found in S3, will create new one.")
        else:
            raise


def upload_excel_to_s3():
    """Upload local Excel file back to S3"""
    try:
        s3.upload_file(EXCEL_FILE, BUCKET_NAME, EXCEL_KEY)
        print(f"⬆️ Uploaded {EXCEL_FILE} to S3")
    except Exception as e:
        print(f"❌ Error uploading Excel: {e}")


def get_students_from_s3():
    """
    Fetch student details (ER number, Name, Batch) from S3 bucket.
    Assumes folder structure: batch/ER1234_Name.jpg
    """
    students = []

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET_NAME):
        for obj in page.get("Contents", []):
            key = obj["Key"]

            # Skip folders
            if key.endswith("/"):
                continue

            parts = key.split("/")
            if len(parts) >= 2:
                batch = parts[0]  # e.g., 2021-2024
                filename = parts[-1]  # e.g., ER1234_JohnDoe.jpg

                if "_" in filename:
                    er_number, name_with_ext = filename.split("_", 1)
                    student_name = os.path.splitext(name_with_ext)[0]
                    students.append((er_number, student_name, batch))

    return students


def sync_students_to_excel():
    """
    Sync students from S3 with Excel (local + S3 copy).
    Completely rebuilds Excel each time from S3 data.
    """
    # Download latest Excel (not really needed since we rebuild fresh, but keep for backup)
    download_excel_from_s3()

    students = get_students_from_s3()

    # Create a new workbook each time (fresh rebuild)
    wb = Workbook()
    ws = wb.active
    ws.title = "Students"
    ws.append(["ER Number", "Name", "Batch"])  # header

    for er, name, batch in students:
        ws.append([er, name, batch])

    wb.save(EXCEL_FILE)
    print(f"📘 Excel file '{EXCEL_FILE}' rebuilt with {len(students)} students.")

    # Upload updated Excel back to S3
    upload_excel_to_s3()
