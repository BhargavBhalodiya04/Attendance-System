import os
import io
import csv
import boto3
import pandas as pd
from datetime import timezone
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


def parse_metadata_from_filename(filename: str):
    """
    Extract batch and subject from filename.
    Example: 20250821_1234-1234_A_OS.xlsx
             -> batch = "1234-1234", subject = "OS"
    """
    try:
        name, _ = os.path.splitext(filename)
        parts = name.split("_")

        if len(parts) >= 4:
            batch = parts[1]     # "1234-1234"
            subject = parts[3]   # "OS"
            return batch, subject
    except Exception:
        pass
    return "-", "-"


def list_s3_reports():
    """
    List all attendance reports in the S3 bucket (reports/ prefix).
    Extracts metadata, record counts, and students list.
    """
    try:
        response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME, Prefix="reports/"
        )

        reports = []
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

            # Extract batch & subject from filename
            filename = os.path.basename(key)
            batch, subject = parse_metadata_from_filename(filename)

            reports.append(
                {
                    "id": key,
                    "fileName": filename,
                    "batch": batch,
                    "subject": subject,
                    "date": obj["LastModified"].astimezone(timezone.utc).isoformat(),
                    "size": f"{obj['Size']/1024:.1f} KB",
                    "records": records_count,
                    "status": "ready",
                    "students": students,
                    "url": f"https://{BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{key}",
                }
            )

        return reports

    except Exception as e:
        return {"error": str(e)}
