from flask import Flask, request, render_template_string
import boto3
import os
from werkzeug.utils import secure_filename
from botocore.exceptions import ClientError

app = Flask(__name__)

# AWS Clients
s3 = boto3.client('s3')
s3_resource = boto3.resource('s3')

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

# Upload images to S3 under batch folder inside year bucket
def upload_images_to_s3(bucket_name, batch_name, files):
    create_bucket(bucket_name)

    for file in files:
        if file.filename == '':
            continue

        filename = secure_filename(file.filename)
        file.save(filename)

        s3_key = f"{batch_name}/{filename}"

        try:
            s3.upload_file(Filename=filename, Bucket=bucket_name, Key=s3_key)
        except Exception as e:
            os.remove(filename)
            raise Exception(f"Upload failed for {filename}: {str(e)}")

        os.remove(filename)

    return f"✅ Files uploaded to batch '{batch_name}' in S3 bucket '{bucket_name}'!"

# Upload form route
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        year = request.form['year']
        batch = request.form['batch']
        files = request.files.getlist('files')
        result = upload_images_to_s3(year, batch, files)
        return result

    return render_template_string('''
        <!doctype html>
        <title>Upload to S3</title>
        <h2>Upload Files to S3</h2>
        <form method=post enctype=multipart/form-data>
          Year (bucket): <input type=text name=year required><br><br>
          Batch (folder): <input type=text name=batch required><br><br>
          Files: <input type=file name=files multiple required><br><br>
          <input type=submit value=Upload>
        </form>
    ''')

if __name__ == '__main__':
    app.run(debug=True)
