# import boto3
# import os
# from werkzeug.utils import secure_filename
# from botocore.exceptions import ClientError
# from flask import Flask, request, render_template_string

# app = Flask(__name__)
# s3 = boto3.client('s3')
# s3_resource = boto3.resource('s3')

# def create_bucket(bucket_name):
#     """Create the S3 bucket if it does not exist."""
#     try:
#         s3.head_bucket(Bucket=bucket_name)
#     except ClientError as e:
#         error_code = int(e.response['Error']['Code'])
#         if error_code == 404:
#             region = boto3.session.Session().region_name
#             s3.create_bucket(
#                 Bucket=bucket_name,
#                 CreateBucketConfiguration={'LocationConstraint': region}
#             )

# def upload_student_image(bucket_name, er_number, student_name, image_file):
#     """Upload a student image into a folder (prefix) inside S3 bucket."""
#     create_bucket(bucket_name)

#     # Sanitize inputs
#     student_name_clean = secure_filename(student_name.strip().replace(" ", "_"))
#     er_clean = secure_filename(er_number.strip())
#     folder_prefix = f"{er_clean}_{student_name_clean}"

#     # Save file temporarily
#     filename = secure_filename(image_file.filename)
#     extension = os.path.splitext(filename)[1]
#     s3_filename = f"{folder_prefix}/{filename}"

#     temp_path = f"temp_{filename}"
#     image_file.save(temp_path)

#     try:
#         s3.upload_file(temp_path, bucket_name, s3_filename)
#         os.remove(temp_path)
#         return f"✅ Uploaded {filename} to folder <strong>{folder_prefix}</strong> in S3!"
#     except Exception as e:
#         os.remove(temp_path)
#         return f"❌ Upload failed: {str(e)}"

# # Optional test form to run independently
# if __name__ == '__main__':
#     @app.route('/', methods=['GET', 'POST'])
#     def upload_form():
#         if request.method == 'POST':
#             bucket_name = 'your-s3-bucket-name'  # Change this
#             er_number = request.form.get('er_number', '').strip()
#             student_name = request.form.get('name', '').strip()
#             image = request.files.get('image')

#             if bucket_name and er_number and student_name and image and image.filename:
#                 return upload_student_image(bucket_name, er_number, student_name, image)

#             return "❌ Missing fields. Please fill all fields."

#         return render_template_string('''
#             <h2>Upload Student Image to S3</h2>
#             <form method="post" enctype="multipart/form-data">
#                 <label>ER Number:</label><br>
#                 <input type="text" name="er_number" required><br><br>
#                 <label>Student Name:</label><br>
#                 <input type="text" name="name" required><br><br>
#                 <label>Select Image:</label><br>
#                 <input type="file" name="image" accept="image/*" required><br><br>
#                 <input type="submit" value="Upload">
#             </form>
#         ''')

#     app.run(debug=True)

# import boto3
# import os
# from werkzeug.utils import secure_filename
# from botocore.exceptions import ClientError

# s3 = boto3.client('s3')
# s3_resource = boto3.resource('s3')

# def create_bucket(bucket_name):
#     """Creates the S3 bucket if it does not exist."""
#     try:
#         s3.head_bucket(Bucket=bucket_name)
#     except ClientError as e:
#         error_code = int(e.response['Error']['Code'])
#         if error_code == 404:
#             s3.create_bucket(
#                 Bucket=bucket_name,
#                 CreateBucketConfiguration={'LocationConstraint': boto3.session.Session().region_name}
#             )

# def upload_images_to_s3(bucket_name, file_path, s3_filename):
#     """Generic uploader used for multiple files."""
#     create_bucket(bucket_name)
#     try:
#         s3.upload_file(Filename=file_path, Bucket=bucket_name, Key=s3_filename)
#     except Exception as e:
#         raise Exception(f"Upload failed for {s3_filename}: {str(e)}")
#     return f"✅ Uploaded {s3_filename} to S3 bucket '{bucket_name}'"

# def upload_student_image(bucket_name, er_number, name, image_file):
#     """Uploads a student's image to a folder named after the student in S3."""
#     create_bucket(bucket_name)

#     name_clean = name.strip().replace(" ", "_")
#     er_number = er_number.strip()
#     extension = os.path.splitext(secure_filename(image_file.filename))[1]
    
#     # Create S3 "folder" by including it in the key
#     s3_filename = f"{name_clean}/{er_number}_{name_clean}{extension}"

#     # Save temporarily
#     local_path = os.path.join("uploads", er_number + "_" + name_clean + extension)
#     os.makedirs("uploads", exist_ok=True)
#     image_file.save(local_path)

#     try:
#         s3.upload_file(Filename=local_path, Bucket=bucket_name, Key=s3_filename)
#     finally:
#         os.remove(local_path)

#     return f"✅ Uploaded to folder <strong>{name_clean}/</strong> as <strong>{s3_filename}</strong>"

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

