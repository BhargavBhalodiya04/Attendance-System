import boto3
import pandas as pd
from datetime import datetime
import os

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
BUCKET_NAME = "ict-attendance"
EXCEL_FILE = "students.xlsx"

s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
)


def sync_students_to_excel():
    # 🔹 Get student objects from S3
    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)

    if "Contents" not in response:
        print("⚠️ No students found in S3.")
        return

    data = []
    for obj in response["Contents"]:
        key = obj["Key"]

        # Ignore the Excel file itself
        if key.endswith(".xlsx"):
            continue

        try:
            filename = os.path.basename(key)
            er_number, student_name = filename.split("_", 1)
            student_name = os.path.splitext(student_name)[0]

            # 🔹 Get last modified from S3
            last_modified = obj["LastModified"]
            upload_date = last_modified.strftime("%Y-%m-%d")
            upload_time = last_modified.strftime("%H:%M:%S")

            data.append({
                "ER Number": er_number,
                "Student Name": student_name,
                "Upload Date": upload_date,
                "Upload Time": upload_time,
            })

        except Exception as e:
            print(f"❌ Error parsing key {key}: {e}")

    # Convert to DataFrame
    df = pd.DataFrame(data)

    # Save Excel
    df.to_excel(EXCEL_FILE, index=False)

    # Upload back to S3
    s3_client.upload_file(EXCEL_FILE, BUCKET_NAME, EXCEL_FILE)
    print(f"✅ Excel synced successfully with {len(df)} students.")


if __name__ == "__main__":
    sync_students_to_excel()