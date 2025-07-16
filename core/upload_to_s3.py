import os
import boto3
from werkzeug.utils import secure_filename
from botocore.exceptions import ClientError
from openpyxl import Workbook, load_workbook
from datetime import datetime
from aws_config import AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION

# Constants
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
MAX_FILE_SIZE_MB = 5  # Max 5 MB per image
EXCEL_FILE = 'students.xlsx'

# S3 client
s3 = boto3.client(
    's3',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

def allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

def file_size_okay(file_obj):
    file_obj.seek(0, os.SEEK_END)
    size_mb = file_obj.tell() / (1024 * 1024)
    file_obj.seek(0)
    return size_mb <= MAX_FILE_SIZE_MB

def create_bucket(bucket_name):
    try:
        s3.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code in ('404', 'NoSuchBucket'):
            try:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': AWS_REGION}
                )
            except ClientError as ce:
                raise Exception(f"❌ Could not create bucket: {ce}")
        else:
            raise Exception(f"❌ Bucket access error: {e}")

def upload_file_to_s3(bucket_name, file_path, s3_key):
    try:
        print(f"Uploading to S3 → Bucket: {bucket_name}, Key: {s3_key}")
        s3.upload_file(file_path, bucket_name, s3_key)
    except Exception as e:
        raise Exception(f"❌ Upload failed: {e}")

def update_student_excel_and_upload(bucket_name, er_number, name):
    # Create or load Excel
    if os.path.exists(EXCEL_FILE):
        wb = load_workbook(EXCEL_FILE)
    else:
        wb = Workbook()
        default_sheet = wb.active
        wb.remove(default_sheet)

    # Use bucket name as sheet name
    if bucket_name in wb.sheetnames:
        sheet = wb[bucket_name]
    else:
        sheet = wb.create_sheet(bucket_name)
        sheet.append(["ER Number", "Student Name", "Upload Date & Time"])

    # Add entry
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sheet.append([er_number, name, now])
    wb.save(EXCEL_FILE)

    # ✅ Upload Excel to S3 at ROOT level
    try:
        upload_file_to_s3(bucket_name, EXCEL_FILE, 'students.xlsx')
    except Exception as e:
        raise Exception(f"❌ Failed to upload Excel to S3: {e}")

def upload_multiple_images(bucket_name, er_number, name, image_files):
    create_bucket(bucket_name)

    student_folder = name.strip().replace(" ", "_")
    er_number = er_number.strip()

    os.makedirs("uploads", exist_ok=True)
    upload_results = []

    for i, image_file in enumerate(image_files):
        filename = secure_filename(image_file.filename)
        extension = os.path.splitext(filename)[1].lower()

        if not allowed_file(filename):
            upload_results.append(f"❌ Rejected {filename}: Invalid file type")
            continue
        if not file_size_okay(image_file):
            upload_results.append(f"❌ Rejected {filename}: File too large (> {MAX_FILE_SIZE_MB} MB)")
            continue

        new_filename = f"{er_number}_{student_folder}_{i + 1}{extension}"
        s3_key = f"{student_folder}/{new_filename}"
        local_path = os.path.join("uploads", new_filename)

        try:
            image_file.save(local_path)
            s3.upload_file(Filename=local_path, Bucket=bucket_name, Key=s3_key)
            upload_results.append(f"✅ Uploaded: {s3_key}")
        except Exception as e:
            upload_results.append(f"❌ Failed: {s3_key} -> {str(e)}")
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)

    # Excel update and upload to root
    try:
        update_student_excel_and_upload(bucket_name, er_number, name)
        upload_results.append("📄 Excel updated and uploaded to S3 root.")
    except Exception as e:
        upload_results.append(f"⚠️ Excel update failed: {e}")

    return upload_results
