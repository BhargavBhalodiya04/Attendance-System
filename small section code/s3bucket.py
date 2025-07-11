from flask import Flask, request, render_template_string
import boto3
import os
from werkzeug.utils import secure_filename
from botocore.exceptions import ClientError

app = Flask(__name__)

# AWS Clients
s3 = boto3.client('s3')
s3_resource = boto3.resource('s3')

# HTML Page
UPLOAD_PAGE = """
<!DOCTYPE html>
<html>
<head><title>Upload Images to S3</title></head>
<body>
    <h2>Upload Images to AWS S3</h2>
    <form action="/" method="POST" enctype="multipart/form-data">
        <label>Enter Year (e.g., 2025):</label><br>
        <input type="text" name="year" required><br><br>

        <label>Enter Class Name (e.g., ClassA):</label><br>
        <input type="text" name="class_name" required><br><br>

        <label>Select Images:</label><br>
        <input type="file" name="files[]" multiple required><br><br>

        <input type="submit" value="Upload">
    </form>
</body>
</html>
"""

# Create bucket if it doesn't exist
def create_bucket(bucket_name):
    try:
        s3.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': boto3.session.Session().region_name}
            )

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        year = request.form.get('year')
        class_name = request.form.get('class_name')

        if not year or not class_name:
            return 'Year and Class Name are required.'

        bucket_name = year.strip()
        folder_prefix = f"{class_name.strip().replace(' ', '_')}/"

        try:
            create_bucket(bucket_name)
        except Exception as e:
            return f"Error creating bucket: {str(e)}"

        files = request.files.getlist('files[]')
        for file in files:
            if file.filename == '':
                continue

            filename = secure_filename(file.filename)
            file.save(filename)

            # Upload to folder inside the bucket
            s3_key = f"{folder_prefix}{filename}"
            try:
                s3.upload_file(Filename=filename, Bucket=bucket_name, Key=s3_key)
            except Exception as e:
                os.remove(filename)
                return f"Upload failed for {filename}: {str(e)}"

            os.remove(filename)

        return f"Files uploaded successfully to S3 bucket '{bucket_name}' in folder '{folder_prefix}'!"

    return render_template_string(UPLOAD_PAGE)

if __name__ == '__main__':
    app.run(debug=True)
