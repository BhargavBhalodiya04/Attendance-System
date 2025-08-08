import boto3
import os

# Get individual student image bytes from S3
def get_photo_bytes_from_s3(bucket, key):
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket=bucket, Key=key)
    return response['Body'].read()

# List all student image keys in a batch (e.g., '2021-2024/')
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

# Extract readable student name from key like '2021-2024/ER1234_Rahul_Patel.jpg'
def extract_student_name_from_key(key):
    filename = os.path.basename(key)
    parts = os.path.splitext(filename)[0].split('_')
    if len(parts) >= 2:
        return ' '.join(parts[1:])  # e.g., 'Rahul Patel'
    return parts[0]  # fallback

# Main attendance marking function
def mark_batch_attendance_s3(
    batch_name,            # e.g., '2021-2024'
    class_name,            # optional, currently unused
    group_image_files,     # list of file streams (from Flask)
    s3_bucket='ict-attendance',
    region='ap-south-1'
):
    rekognition = boto3.client('rekognition', region_name=region)
    batch_prefix = f"{batch_name}/"  # Ensure folder structure like '2021-2024/'

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
                    student_name = extract_student_name_from_key(key)
                    image_url = f"https://{s3_bucket}.s3.amazonaws.com/{key}"
                    present_students[student_name] = image_url
            except Exception as e:
                print(f"⚠️ Error comparing {key}: {e}")
                continue

        group_img_file.seek(0)  # Reset for next file if multiple images uploaded

    # Build final lists
    all_student_names = [extract_student_name_from_key(k) for k in student_image_keys]
    absentees = [name for name in all_student_names if name not in present_students]

    present_list = [
        {"name": name, "image_url": present_students[name]}
        for name in sorted(present_students)
    ]

    return present_list, absentees
