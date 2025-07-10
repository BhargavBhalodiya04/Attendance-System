from flask import render_template_string, request
import boto3
import os
from werkzeug.utils import secure_filename
from botocore.exceptions import ClientError

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

# ✅ This is the function you will import
def upload_images_to_s3(bucket_name, files):
    create_bucket(bucket_name)

    for file in files:
        if file.filename == '':
            continue

        filename = secure_filename(file.filename)
        file.save(filename)

        try:
            s3.upload_file(Filename=filename, Bucket=bucket_name, Key=filename)
        except Exception as e:
            os.remove(filename)
            raise Exception(f"Upload failed for {filename}: {str(e)}")

        os.remove(filename)

    return f"Files uploaded successfully to S3 bucket '{bucket_name}'!"
