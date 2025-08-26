import os
import io
import csv
import boto3
import pandas as pd
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment values
load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
BUCKET_NAME = os.getenv("BUCKET_NAME", "ict-attendance")

# Initialize S3 client
s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
)

# 🔹 Subject mapping dictionary
SUBJECT_MAP = {
    "OS": "Operating System",
    "CN": "Computer Networks",
    "DBMS": "Database Management Systems",
    "AI": "Artificial Intelligence",
    # add more as needed
}


def parse_metadata_from_filename(filename: str):
    """
    Example filename: 20250825_2020-2024_A_OS.xlsx
    -> date = 20250825, batch = 2020-2024, section = A, subject = OS
    """
    try:
        name, _ = os.path.splitext(filename)
        parts = name.split("_")

        if len(parts) >= 4:
            date_str = parts[0]          # 20250825
            batch = parts[1]             # 2020-2024
            section = parts[2]           # A
            subject_code = parts[3]      # OS

            # Format date
            date_obj = datetime.strptime(date_str, "%Y%m%d")
            formatted_date = date_obj.strftime("%d %b %Y")

            # Map subject
            subject = SUBJECT_MAP.get(subject_code, subject_code)

            # Build user-friendly name
            user_friendly = f"{subject} | Batch {batch} | Section {section} | {formatted_date}"

            return batch, section, subject, formatted_date, user_friendly

    except Exception:
        pass

    return "-", "-", "-", "-", filename  # fallback


def list_s3_reports():
    """
    List all attendance reports in the S3 bucket (reports/ prefix).
    Group by batch -> section.
    Extracts metadata, record counts, and student list.
    """
    try:
        grouped_reports = {}  # {batch: {section: [reports]}}

        continuation_token = None

        while True:
            if continuation_token:
                response = s3_client.list_objects_v2(
                    Bucket=BUCKET_NAME, Prefix="reports/", ContinuationToken=continuation_token
                )
            else:
                response = s3_client.list_objects_v2(
                    Bucket=BUCKET_NAME, Prefix="reports/"
                )

            for obj in response.get("Contents", []):
                key = obj["Key"]

                # Only process CSV/XLSX files
                if not key.lower().endswith((".csv", ".xlsx")):
                    continue

                # Download file content
                s3_obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
                body = s3_obj["Body"].read()

                records_count, students = 0, []

                if key.endswith(".csv"):
                    rows = list(csv.reader(io.StringIO(body.decode("utf-8"))))
                    if len(rows) > 1:
                        records_count = len(rows) - 1  # exclude header
                        students = [row[0] for row in rows[1:] if row]  # first column

                elif key.endswith(".xlsx"):
                    df = pd.read_excel(io.BytesIO(body))
                    records_count = len(df)
                    if "Name" in df.columns:
                        students = df["Name"].dropna().tolist()

                # Extract metadata
                filename = os.path.basename(key)
                batch, section, subject, formatted_date, user_friendly = parse_metadata_from_filename(filename)

                # Report entry
                report = {
                    "id": key,
                    "fileName": filename,              
                    "userFriendlyName": user_friendly, 
                    "batch": batch,
                    "section": section,
                    "subject": subject,
                    "generatedDate": formatted_date,
                    "uploadedAt": obj["LastModified"].astimezone(timezone.utc).isoformat(),
                    "size": f"{obj['Size']/1024:.1f} KB",
                    "records": records_count,
                    "status": "ready",
                    "students": students,
                    "url": f"https://{BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{key}",
                }

                # Insert into grouped structure
                if batch not in grouped_reports:
                    grouped_reports[batch] = {}
                if section not in grouped_reports[batch]:
                    grouped_reports[batch][section] = []
                grouped_reports[batch][section].append(report)

            # Handle pagination
            if response.get("IsTruncated"):
                continuation_token = response.get("NextContinuationToken")
            else:
                break

        return grouped_reports

    except Exception as e:
        return {"error": str(e)}
