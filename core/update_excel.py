import os
import boto3
from openpyxl import Workbook, load_workbook
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
    students = set()

    # List all objects in bucket
    response = s3.list_objects_v2(Bucket=BUCKET_NAME)

    if "Contents" not in response:
        return students

    for obj in response["Contents"]:
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
                students.add((er_number, student_name, batch))

    return students


def sync_students_to_excel():
    """
    Sync students from S3 with Excel (local + S3 copy).
    Adds new students, removes missing students.
    """
    # Download latest Excel from S3 first
    download_excel_from_s3()

    students = get_students_from_s3()

    # Load or create Excel file
    if os.path.exists(EXCEL_FILE):
        wb = load_workbook(EXCEL_FILE)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Students"
        ws.append(["ER Number", "Name", "Batch"])  # header

    # Current Excel data
    excel_students = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0]:
            excel_students[row[0]] = row

    # Add new students
    for er, name, batch in students:
        if er not in excel_students:
            ws.append([er, name, batch])
            print(f"✅ Added student {er} - {name}")

    # Remove students not in S3
    er_in_s3 = {er for er, _, _ in students}
    rows_to_delete = []
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        er = row[0]
        if er not in er_in_s3:
            rows_to_delete.append(row_idx)

    for idx in sorted(rows_to_delete, reverse=True):
        ws.delete_rows(idx)
        print(f"❌ Removed student at row {idx}")

    wb.save(EXCEL_FILE)
    print(f"📘 Excel file '{EXCEL_FILE}' updated successfully.")

    # Upload updated Excel back to S3
    upload_excel_to_s3()