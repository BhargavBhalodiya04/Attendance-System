import io
import os
import pandas as pd
from flask import Blueprint, jsonify
from dotenv import load_dotenv
import boto3

# Load environment
load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
BUCKET_NAME = os.getenv("BUCKET_NAME", "ict-attendance")

# S3 client
s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

dashboard_bp = Blueprint("dashboard_api", __name__)

@dashboard_bp.route("/overview", methods=["GET"])
def class_overview():
    try:
        # Load students Excel from S3
        s3_obj = s3_client.get_object(Bucket=BUCKET_NAME, Key="students.xlsx")
        body = s3_obj["Body"].read()
        df_students = pd.read_excel(io.BytesIO(body))
        total_students = len(df_students)

        # Find subject reports in S3
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix="reports/")
        subjects_data = []
        trend_data = {}

        for obj in response.get("Contents", []):
            key = obj["Key"]
            if not key.endswith((".xlsx", ".csv")):
                continue

            s3_file = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
            file_body = s3_file["Body"].read()

            # Load attendance file
            if key.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(file_body))
            else:
                df = pd.read_excel(io.BytesIO(file_body))

            # Skip empty files
            if df.empty:
                continue

            # Safe subject extraction
            subject_name = df["Subject"].iloc[0] if "Subject" in df.columns and len(df) > 0 else "Unknown"

            # Safe batch/division extraction
            if "Division" in df.columns:
                batch_name = df["Division"].iloc[0] if len(df) > 0 else "Unknown"
            elif "Class" in df.columns:
                batch_name = df["Class"].iloc[0] if len(df) > 0 else "Unknown"
            else:
                batch_name = "Unknown"

            # Attendance calculation
            present_count = df["ER Number"].nunique() if "ER Number" in df.columns else 0
            total_count = total_students if total_students > 0 else 1
            attendance_percent = round((present_count / total_count) * 100, 2)

            subjects_data.append({
                "subject": subject_name,
                "batch": batch_name,
                "attendance": attendance_percent
            })

            # Trend: group by month if Date column exists
            if "Date" in df.columns:
                df["Month"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%b")
                month_avg = df.groupby("Month").size().mean() if not df.empty else 0
                trend_data[f"{subject_name} ({batch_name})"] = {
                    "month": list(df["Month"].unique()),
                    "attendance": month_avg
                }

        # Overall stats
        avg_attendance = round(
            sum(s["attendance"] for s in subjects_data) / len(subjects_data), 2
        ) if subjects_data else 0

        active_subjects = len(subjects_data)
        best_subject_data = max(subjects_data, key=lambda x: x["attendance"]) if subjects_data else None
        best_subject = best_subject_data["subject"] if best_subject_data else None
        best_batch = best_subject_data["batch"] if best_subject_data else None

        # Format trend for chart
        overall_trend = []
        for subject_batch, data in trend_data.items():
            for m in data["month"]:
                overall_trend.append({
                    "month": m,
                    "attendance": data["attendance"],
                    "subject_batch": subject_batch
                })

        return jsonify({
            "avgAttendance": avg_attendance,
            "totalStudents": total_students,
            "activeSubjects": active_subjects,
            "bestSubject": best_subject,
            "bestBatch": best_batch,
            "subjects": subjects_data,
            "trend": overall_trend
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
