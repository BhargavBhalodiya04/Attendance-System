from flask import Flask, request, render_template_string
import boto3
import os
from werkzeug.utils import secure_filename
# from botocore.exceptions import ClientError

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
        <label>Enter S3 Bucket Name:</label><br>
        <input type="text" name="bucket_name" required><br><br>

        <label>Select Images:</label><br>
        <input type="file" name="files[]" multiple required><br><br>

        <input type="submit" value="Upload">
    </form>
</body>
</html>
"""

# Bucket creation
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
        bucket_name = request.form.get('bucket_name')
        if not bucket_name:
            return 'Bucket name is required.'

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

            try:
                s3.upload_file(Filename=filename, Bucket=bucket_name, Key=filename)
            except Exception as e:
                os.remove(filename)
                return f"Upload failed for {filename}: {str(e)}"

            os.remove(filename)

        return f"Files uploaded successfully to S3 bucket '{bucket_name}'!"

    # For GET request, show the form
    return render_template_string(UPLOAD_PAGE)

if __name__ == '__main__':
    app.run(debug=True)
