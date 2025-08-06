import boto3
import json

def get_student_db_from_s3(bucket_name, key='students.json'):
    s3 = boto3.client('s3')
    content = s3.get_object(Bucket=bucket_name, Key=key)['Body'].read().decode('utf-8')
    return json.loads(content)

def get_photo_bytes_from_s3(bucket, key):
    s3 = boto3.client('s3')
    return s3.get_object(Bucket=bucket, Key=key)['Body'].read()

def mark_batch_attendance_s3(batch_name, class_name, group_image_files, s3_bucket='ict-attendance', student_db_key='students.json', region='ap-south-1'):
    students = get_student_db_from_s3(s3_bucket, student_db_key)
    rekognition = boto3.client('rekognition', region_name=region)

    present_students = set()
    face_detection_done = False

    for group_img_file in group_image_files:
        group_bytes = group_img_file.read()
        detection = rekognition.detect_faces(
            Image={'Bytes': group_bytes},
            Attributes=['DEFAULT']
        )
        if not detection['FaceDetails']:
            raise ValueError("No face detected in uploaded photo! Please upload a group photo containing at least one person.")
        face_detection_done = True

        for student in students:
            student_name = student['name']
            face_key = student['photo_key']  # e.g., "photos/er123.jpg"
            try:
                student_bytes = get_photo_bytes_from_s3(s3_bucket, face_key)
                response = rekognition.compare_faces(
                    SourceImage={'Bytes': student_bytes},
                    TargetImage={'Bytes': group_bytes},
                    SimilarityThreshold=80
                )
                if response['FaceMatches']:
                    present_students.add(student_name)
            except Exception as e:
                continue
        group_img_file.seek(0)  # Reset stream

    present_list = sorted(list(present_students))
    absentees = [s['name'] for s in students if s['name'] not in present_students]
    return [f"✅ Present: {', '.join(present_list) if present_list else 'None'}",
            f"❌ Absentees: {', '.join(absentees) if absentees else 'None'}"]
