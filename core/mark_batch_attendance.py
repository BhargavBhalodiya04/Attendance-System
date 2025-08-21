import boto3
import os
from datetime import datetime
from openpyxl import Workbook

# Get individual student image bytes from S3
def get_photo_bytes_from_s3(bucket, key):
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket=bucket, Key=key)
    return response['Body'].read()

# List all student image keys in a batch
def list_student_images_from_s3(bucket, batch_prefix):
    s3 = boto3.client('s3')
    paginator = s3.get_paginator('list_objects_v2')
    page_iterator = paginator.paginate(Bucket=bucket, Prefix=batch_prefix)

    image_keys = []
    for page in page_iterator:
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.lower().endswith(('.jpg', '.jpeg', '.png')) and key != batch_prefix:
                image_keys.append(key)
    return image_keys

# Extract ER number and student name from file name
def extract_student_details_from_key(key):
    filename = os.path.basename(key)
    parts = os.path.splitext(filename)[0].split('_')
    if len(parts) >= 2:
        er_number = parts[0]
        name = ' '.join(parts[1:])
        return er_number, name
    return parts[0], parts[0]  # fallback

# Save attendance to Excel
def save_attendance_to_excel(attendance_data, batch_name, class_name, subject):
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H-%M-%S")
    
    # Save into a fixed folder so Flask can serve it
    save_dir = "attendance_reports"
    os.makedirs(save_dir, exist_ok=True)

    filename = f"Attendance_{batch_name}_{current_date}_{current_time}.xlsx"
    filepath = os.path.join(save_dir, filename)

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"

    # Header row
    ws.append(["ER Number", "Student Name", "Date", "Time", "Class", "Subject", "Batch"])

    # Data rows
    for student in attendance_data:
        ws.append([
            student["er_number"],
            student["name"],
            current_date,
            current_time,
            class_name,
            subject,
            batch_name
        ])

    wb.save(filepath)
    return filepath

# Main attendance marking function
def mark_batch_attendance_s3(
    batch_name,
    class_name,
    subject,
    group_image_files,
    s3_bucket='ict-attendance',
    region='ap-south-1'
):
    rekognition = boto3.client('rekognition', region_name=region)
    batch_prefix = f"{batch_name}/"

    student_image_keys = list_student_images_from_s3(s3_bucket, batch_prefix)

    present_students = {}

    for group_img_file in group_image_files:
        group_bytes = group_img_file.read()

        # Ensure group photo has faces
        detection = rekognition.detect_faces(
            Image={'Bytes': group_bytes},
            Attributes=['DEFAULT']
        )
        if not detection['FaceDetails']:
            raise ValueError("❌ No face detected in group image. Please upload a valid group photo.")

        # Compare each student image
        for key in student_image_keys:
            try:
                student_bytes = get_photo_bytes_from_s3(s3_bucket, key)
                response = rekognition.compare_faces(
                    SourceImage={'Bytes': student_bytes},
                    TargetImage={'Bytes': group_bytes},
                    SimilarityThreshold=80
                )
                if response['FaceMatches']:
                    er_number, student_name = extract_student_details_from_key(key)
                    image_url = f"https://{s3_bucket}.s3.amazonaws.com/{key}"
                    present_students[er_number] = {
                        "er_number": er_number,
                        "name": student_name,
                        "image_url": image_url
                    }
            except Exception as e:
                print(f"⚠️ Error comparing {key}: {e}")
                continue

        group_img_file.seek(0)

    # Prepare Excel file
    attendance_list = list(present_students.values())
    excel_file_path = save_attendance_to_excel(attendance_list, batch_name, class_name, subject)

    return attendance_list, excel_file_path