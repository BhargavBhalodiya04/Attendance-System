import os
import boto3
from werkzeug.utils import secure_filename
from botocore.exceptions import ClientError

# Setup S3 client
s3 = boto3.client('s3')
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
MAX_FILE_SIZE_MB = 5  # Max 5 MB per image

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
        if e.response['Error']['Code'] == '404':
            region = boto3.session.Session().region_name
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )

def upload_multiple_images(bucket_name, er_number, name, image_files):
    create_bucket(bucket_name)
    student_folder = name.strip().replace(" ", "_")
    er_number = er_number.strip()

    os.makedirs("uploads", exist_ok=True)
    upload_results = []

    for i, image_file in enumerate(image_files):
        filename = secure_filename(image_file.filename)
        extension = os.path.splitext(filename)[1].lower()

        # Validate file
        if not allowed_file(filename):
            upload_results.append(f"❌ Rejected {filename}: Invalid file type")
            continue
        if not file_size_okay(image_file):
            upload_results.append(f"❌ Rejected {filename}: File too large (> {MAX_FILE_SIZE_MB} MB)")
            continue

        s3_key = f"{student_folder}/{er_number}_{student_folder}_{i + 1}{extension}"
        local_path = os.path.join("uploads", f"{er_number}_{student_folder}_{i + 1}{extension}")
        
        # Save temporarily
        image_file.save(local_path)

        try:
            s3.upload_file(Filename=local_path, Bucket=bucket_name, Key=s3_key)
            upload_results.append(f"✅ Uploaded: {s3_key}")
        except Exception as e:
            upload_results.append(f"❌ Failed: {s3_key} -> {str(e)}")
        finally:
            os.remove(local_path)

    return upload_results
