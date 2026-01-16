import matplotlib.pyplot as plt
import io
import base64
import pandas as pd
import boto3
import os
from dotenv import load_dotenv

load_dotenv()
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
EXCEL_FOLDER_KEY = os.getenv("EXCEL_FOLDER_KEY", "reports/")

def generate_overall_attendance():
    # S3 client
    s3 = boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
    )

    # list all .xlsx under prefix (handle pagination)
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=BUCKET_NAME, Prefix=EXCEL_FOLDER_KEY)

    files = []
    for page in pages:
        for obj in page.get("Contents", []) if page.get("Contents") else []:
            key = obj.get("Key")
            if key and key.lower().endswith(".xlsx"):
                files.append(key)

    if not files:
        raise ValueError(f"No Excel files found in S3 folder: {EXCEL_FOLDER_KEY}")

    # read and combine
    combined_df = pd.DataFrame()
    for file_key in files:
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=file_key)
        content = obj["Body"].read()
        # read Excel (first sheet). If multiple sheets are needed adjust here.
        df = pd.read_excel(io.BytesIO(content))
        # normalize column names
        df.columns = [str(col).strip().lower() for col in df.columns]
        combined_df = pd.concat([combined_df, df], ignore_index=True)

    # required columns
    required_cols = ["date", "subject", "student name", "er number", "status"]
    missing_cols = [c for c in required_cols if c not in combined_df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in Excel files: {missing_cols}")

    # clean date and drop invalid
    combined_df["date"] = pd.to_datetime(combined_df["date"], errors="coerce")
    combined_df = combined_df.dropna(subset=["date"])

    # normalize text fields
    combined_df["student name"] = combined_df["student name"].astype(str).str.strip()
    combined_df["er number"] = combined_df["er number"].astype(str).str.strip()
    combined_df["subject"] = combined_df["subject"].astype(str).str.strip()

    # robust status normalization: treat anything containing 'present' as present
    combined_df["status"] = combined_df["status"].astype(str).str.strip().str.lower().fillna("")
    is_present = combined_df["status"].str.contains("present", na=False)

    present_df = combined_df[is_present].copy()

    # total unique class sessions (date + subject)
    total_classes = combined_df[["date", "subject"]].drop_duplicates().shape[0]

    # present count per student (unique (date, subject) per student)
    present_count = (
        present_df[["date", "subject", "student name", "er number"]]
        .drop_duplicates()
        .groupby(["student name", "er number"])
        .size()
        .reset_index(name="present_count")
    )

    # include all students (even those never present)
    all_students = combined_df[["student name", "er number"]].drop_duplicates()
    student_attendance_count = all_students.merge(
        present_count, on=["student name", "er number"], how="left"
    )
    student_attendance_count["present_count"] = student_attendance_count[
        "present_count"
    ].fillna(0).astype(int)

    # add totals and percentage (avoid div-by-zero)
    student_attendance_count["total_classes"] = int(total_classes)
    if total_classes > 0:
        student_attendance_count["attendance_percentage"] = (
            student_attendance_count["present_count"] / total_classes * 100
        ).round(1)
    else:
        student_attendance_count["attendance_percentage"] = 0.0

    # prepare students list sorted by percentage desc
    students = []
    sorted_df = student_attendance_count.sort_values(
        ["attendance_percentage", "present_count"], ascending=[False, False]
    )
    for _, row in sorted_df.iterrows():
        students.append(
            {
                "name": row["student name"],
                "er_number": row["er number"],
                "present_count": int(row["present_count"]),
                "total_classes": int(row["total_classes"]),
                "attendance_percentage": float(row["attendance_percentage"]),
            }
        )

    # daily trend: number of unique present students per date
    daily_trend_df = (
        present_df[["date", "er number"]]
        .drop_duplicates()
        .groupby("date")
        .agg({"er number": pd.Series.nunique})
        .reset_index()
        .rename(columns={"er number": "attendance"})
        .sort_values("date")
    )
    daily_trend_data = [
        {"date": r["date"].strftime("%Y-%m-%d"), "attendance": int(r["attendance"])}
        for _, r in daily_trend_df.iterrows()
    ]

    # overall realtime average attendance %
    total_students = combined_df["er number"].nunique()
    total_days = combined_df["date"].nunique()
    total_attendance_records = present_df[["date", "er number"]].drop_duplicates().shape[0]
    if total_students * total_days > 0:
        avg_attendance_pct = round((total_attendance_records / (total_students * total_days)) * 100, 1)
    else:
        avg_attendance_pct = 0.0

    # subject-wise summary (unique present student counts)
    subject_summary = (
        present_df.groupby("subject")
        .agg({"er number": pd.Series.nunique})
        .reset_index()
        .rename(columns={"er number": "present_students"})
        .sort_values("present_students", ascending=False)
    )

    # Pie chart (guard when there are no subjects / zero values)
    subject_pie_chart = None
    if not subject_summary.empty and subject_summary["present_students"].sum() > 0:
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.pie(
            subject_summary["present_students"],
            labels=subject_summary["subject"].tolist(),
            autopct="%1.1f%%",
            startangle=140,
        )
        ax.set_title("Subject-wise Attendance Distribution")
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        subject_pie_chart = base64.b64encode(buf.getvalue()).decode()

    return {
        "students": students,
        "daily_trend_data": daily_trend_data,
        "subject_pie_chart": subject_pie_chart,  # base64 PNG or None
        "avg_attendance_pct": f"{avg_attendance_pct}%",
        "total_students": int(total_students),
        "total_days": int(total_days),
        "total_classes": int(total_classes),
    }
