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

            # Build name
            user_friendly = f"{subject} | Batch {batch} | Section {section} | {formatted_date}"

            return batch, section, subject, formatted_date, user_friendly

    except Exception:
        pass

    return "-", "-", "-", "-", filename


def load_master_students():
    """
    Reads master student list from students.xlsx in S3.
    Expected format: columns [Batch, Section, Name]
    Returns: dict {batch: {section: [students]}}
    """
    try:
        s3_obj = s3_client.get_object(Bucket=BUCKET_NAME, Key="reports/students.xlsx")
        body = s3_obj["Body"].read()
        df = pd.read_excel(io.BytesIO(body))

        master_students = {}
        if {"Batch", "Section", "Name"}.issubset(df.columns):
            for _, row in df.iterrows():
                batch = str(row["Batch"]).strip()
                section = str(row["Section"]).strip()
                name = str(row["Name"]).strip()
                if batch and section and name:
                    master_students.setdefault(batch, {}).setdefault(section, []).append(name)

        return master_students
    except Exception as e:
        print("⚠️ Could not load master student list:", e)
        return {}


def list_s3_reports():
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
                filename = os.path.basename(key)

                # 🚫 Skip master student file
                if filename.lower() == "students.xlsx":
                    continue

                # Only process CSV/XLSX reports
                if not key.lower().endswith((".csv", ".xlsx")):
                    continue

                # Download file content
                s3_obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
                body = s3_obj["Body"].read()

                records_count, students = 0, []

                if key.endswith(".csv"):
                    rows = list(csv.reader(io.StringIO(body.decode("utf-8"))))
                    if len(rows) > 1:
                        records_count = len(rows) - 1
                        students = [row[0] for row in rows[1:] if row]

                elif key.endswith(".xlsx"):
                    df = pd.read_excel(io.BytesIO(body))
                    records_count = len(df)
                    if "Name" in df.columns:
                        students = df["Name"].dropna().tolist()

                # Extract metadata
                batch, section, subject, formatted_date, user_friendly = parse_metadata_from_filename(filename)

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
                    # will be filled later
                    "attendanceMap": {}
                }

                # Insert into grouped structure
                grouped_reports.setdefault(batch, {}).setdefault(section, []).append(report)

            if response.get("IsTruncated"):
                continuation_token = response.get("NextContinuationToken")
            else:
                break

        return grouped_reports

    except Exception as e:
        return {"error": str(e)}


def calculate_attendance_percentages(grouped_reports, master_students):
    results = {}

    for batch, sections in grouped_reports.items():
        for section, reports in sections.items():
            students = master_students.get(batch, {}).get(section, [])
            total_classes = len(reports)

            # Initialize counts
            student_counts = {s: {"present": 0, "total": total_classes} for s in students}

            # Mark presence/absence in each report
            for report in reports:
                present_students = set(report["students"])
                attendance_map = {}
                for s in students:
                    if s in present_students:
                        student_counts[s]["present"] += 1
                        attendance_map[s] = "Present"
                    else:
                        attendance_map[s] = "Absent"
                report["attendanceMap"] = attendance_map  # attach per-class status

            # Compute %
            for s, data in student_counts.items():
                attended = data["present"]
                total = data["total"]
                pct = round((attended / total) * 100, 1) if total > 0 else 0
                student_counts[s]["percentage"] = pct

            results[(batch, section)] = student_counts

    return results


if __name__ == "__main__":
    # Load reports
    reports = list_s3_reports()

    # Load master student list
    master_students = load_master_students()

    # Calculate attendance summary + update reports with per-class map
    attendance_summary = calculate_attendance_percentages(reports, master_students)

    # Example print
    for (batch, section), students in attendance_summary.items():
        print(f"\n📘 Batch {batch} | Section {section}")
        for name, stats in students.items():
            print(f"{name}: {stats['present']}/{stats['total']} classes ({stats['percentage']}%)")

    # Example: see per-report attendance mapping
    for batch, sections in reports.items():
        for section, rep_list in sections.items():
            for rep in rep_list:
                print(f"\n📝 {rep['userFriendlyName']}")
                for s, status in rep["attendanceMap"].items():
                    print(f"  {s}: {status}")
