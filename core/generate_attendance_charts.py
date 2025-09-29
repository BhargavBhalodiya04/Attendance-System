import matplotlib
matplotlib.use('Agg')

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
    s3 = boto3.client(
        's3',
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY
    )

    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=EXCEL_FOLDER_KEY)
    files = [file['Key'] for file in response.get('Contents', []) if file['Key'].endswith('.xlsx')]

    if not files:
        raise ValueError(f"No Excel files found in S3 folder: {EXCEL_FOLDER_KEY}")

    combined_df = pd.DataFrame()
    for file_key in files:
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=file_key)
        df = pd.read_excel(io.BytesIO(obj['Body'].read()))
        df.columns = [col.strip().lower() for col in df.columns]
        combined_df = pd.concat([combined_df, df], ignore_index=True)

    required_cols = ['date', 'subject', 'student name', 'er number', 'status']
    missing_cols = [col for col in required_cols if col not in combined_df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in Excel files: {missing_cols}")

    combined_df['date'] = pd.to_datetime(combined_df['date'], errors='coerce')
    combined_df = combined_df.dropna(subset=['date'])

    # Total unique class sessions (date + subject)
    total_classes = combined_df[['date', 'subject']].drop_duplicates().shape[0]

    # Count Present only
    present_df = combined_df[combined_df['status'].str.lower() == 'present']

    present_count = (
        present_df[['date', 'subject', 'student name', 'er number']]
        .drop_duplicates()
        .groupby(['student name', 'er number'])
        .size()
        .reset_index(name='present_count')
    )

    # Ensure all students (including absent ones) are included
    all_students = combined_df[['student name', 'er number']].drop_duplicates()

    student_attendance_count = all_students.merge(
        present_count,
        on=['student name', 'er number'],
        how='left'
    ).fillna({'present_count': 0})

    # Add total_classes and percentage
    student_attendance_count['total_classes'] = total_classes
    student_attendance_count['attendance_percentage'] = (
        student_attendance_count['present_count'] / student_attendance_count['total_classes'] * 100
    )

    students = []
    for _, row in student_attendance_count.iterrows():
        students.append({
            "name": row['student name'],
            "er_number": row['er number'],
            "present_count": int(row['present_count']),
            "total_classes": int(row['total_classes']),
            "attendance_percentage": round(float(row['attendance_percentage']), 1)
        })

    # Build Structured Daily Trend Data (how many PRESENT each day)
    daily_trend_df = (
        present_df.groupby('date')
        .agg({'er number': pd.Series.nunique})
        .reset_index()
    )
    daily_trend_data = []
    for _, row in daily_trend_df.iterrows():
        daily_trend_data.append({
            "date": row['date'].strftime('%Y-%m-%d'),
            "attendance": int(row['er number'])
        })

    # Calculate Real-time Average Attendance %
    total_students = combined_df['er number'].nunique()
    total_days = combined_df['date'].nunique()
    total_attendance_records = present_df[['date', 'er number']].drop_duplicates().shape[0]

    if total_students * total_days > 0:
        avg_attendance_pct = round(
            (total_attendance_records / (total_students * total_days)) * 100, 1
        )
    else:
        avg_attendance_pct = 0.0

    # Generate Subject Pie Chart (based on PRESENT counts)
    subject_summary = (
        present_df.groupby('subject')
        .agg({'er number': pd.Series.nunique})
        .reset_index()
    )

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(
        subject_summary['er number'],
        labels=subject_summary['subject'],
        autopct='%1.1f%%',
        startangle=140
    )
    ax.set_title('Subject-wise Attendance Distribution')
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    subject_pie_chart = base64.b64encode(buf.getvalue()).decode()

    return {
        "students": students,
        "daily_trend_data": daily_trend_data,
        "subject_pie_chart": subject_pie_chart,
        "avg_attendance_pct": f"{avg_attendance_pct}%"
    }
