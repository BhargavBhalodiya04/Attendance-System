import os
import sys
import io
import csv
from datetime import datetime
import boto3
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, send_file, jsonify
)
from flask_cors import CORS
from flask import send_from_directory

sys.dont_write_bytecode = True

# Load .env variables
load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
FLASK_SECRET_KEY = os.getenv("SECRET_KEY", "your_default_secret")

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

# Enable CORS for React frontend
CORS(app, supports_credentials=True, resources={r"/*": {"origins": "*"}})

# Initialize AWS clients
rekognition_client = boto3.client(
    "rekognition",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)
s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

# Import core functions
from core.upload_to_s3 import upload_multiple_images
from core.update_excel import sync_students_to_excel
from core.mark_batch_attendance import mark_batch_attendance_s3

USER = {'username': 'admin', 'password': 'admin'}

# ---------------- ROUTES ---------------- #

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == USER['username'] and password == USER['password']:
            session['logged_in'] = True
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/home', methods=['GET', 'POST'])
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    selected_action = request.form.get('action')
    if selected_action:
        return redirect(url_for('action_page', action=selected_action))
    return render_template('home.html')


@app.route('/action/<action>', methods=['GET', 'POST'])
def action_page(action):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if action == 'take_attendance':
        return redirect(url_for('take_attendance'))
    elif action == 'upload':
        return render_template('upload.html')
    elif action == 'batch_attendance_upload':
        return redirect(url_for('batch_attendance_upload'))
    return "Invalid action selected.", 400


@app.route('/upload-image', methods=['POST'])
def upload_image():
    bucket_name = request.form.get('bucket_name', '').strip() or 'ict-attendance'
    batch_name = request.form.get('batch_name', '').strip()
    er_number = request.form.get('er_number', '').strip()
    student_name = request.form.get('student_name', '').strip() or request.form.get('name', '').strip()

    image_files = request.files.getlist('images')
    single_file = request.files.get('file')
    if single_file and (not image_files or len(image_files) == 0):
        image_files = [single_file]

    if not all([bucket_name, batch_name, er_number, student_name]) or not image_files or not any(getattr(f, 'filename', '') for f in image_files):
        return jsonify({"error": "❌ All fields are required and images must be selected."}), 400

    try:
        # ✅ Upload images to S3
        upload_results = upload_multiple_images(batch_name, er_number, student_name, image_files)

        # ✅ Update Excel file after upload
        sync_students_to_excel()

        return jsonify({
            "success": True,
            "student": {
                "er_number": er_number,
                "name": student_name,
                "batch_name": batch_name,
                "bucket_name": bucket_name
            },
            "results": upload_results,
            "message": "✅ Upload successful and Excel updated."
        }), 200

    except Exception as e:
        return jsonify({"error": f"❌ Upload failed: {str(e)}"}), 500


# ---------------- JSON Attendance API ---------------- #
@app.route('/take_attendance', methods=['POST'])
def take_attendance():
    try:
        batch_name = request.form.get('batch_name')
        subject_name = request.form.get('subject_name')
        lab_name = request.form.get('lab_name', '')

        group_images = request.files.getlist('class_images')
        if not batch_name or not subject_name or not group_images:
            return jsonify({"success": False, "error": "Batch, Subject, and class_images are required"}), 400

        # Run batch attendance
        attendance_list, excel_file_path = mark_batch_attendance_s3(
            batch_name=batch_name,
            class_name=lab_name,
            subject=subject_name,
            group_image_files=group_images
        )

        # Prepare response
        present_names = [s["name"] for s in attendance_list]
        present_er = [s["er_number"] for s in attendance_list]

        # TODO: get full list of students for absent calc (for now empty)
        absent_students = []

        report_url = f"/{excel_file_path}"

        return jsonify({
            "success": True,
            "present": present_names,
            "absent": absent_students,
            "report_url": report_url
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Serve saved attendance reports
@app.route('/attendance_reports/<path:filename>')
def download_report(filename):
    return send_from_directory("attendance_reports", filename, as_attachment=True)


# ---------------- Batch Upload Placeholder ---------------- #
@app.route('/batch_attendance_upload', methods=['GET', 'POST'])
def batch_attendance_upload():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        return render_template('batch_attendance_upload.html', message="Feature under development.")
    
    return render_template('batch_attendance_upload.html')


# ---------------- CSV Download ---------------- #
@app.route('/download_attendance')
def download_attendance():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    students = session.get('recognized_students', [])
    batch_name = session.get('batch_name', 'attendance')
    class_name = session.get('class_name', '')
    subject_name = session.get('subject_name', '')

    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H-%M-%S")

    # ✅ Generate CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ER Number', 'Name', 'Subject Name', 'Batch', 'Class', 'Date', 'Time'])

    for student in students:
        parts = student.split('_', 1)
        if len(parts) == 2:
            er_number, name = parts
        else:
            er_number, name = student, ''
        writer.writerow([er_number, name, subject_name, batch_name, class_name, current_date, current_time])

    output.seek(0)
    csv_bytes = io.BytesIO(output.getvalue().encode())

    filename = f"{batch_name}_{subject_name}_{current_date}_{current_time}.csv"
    s3_key = f"reports/{filename}"

    try:
        # ✅ Upload CSV to S3 with public-read ACL
        s3_client.upload_fileobj(
            csv_bytes,
            "ict-attendance",
            s3_key,
            ExtraArgs={'ACL': 'public-read'}   # 👈 makes file public
        )

        # ✅ Permanent Public URL
        public_url = f"https://ict-attendance.s3.ap-south-1.amazonaws.com/{s3_key}"

        if request.headers.get("Accept") == "application/json":
            return jsonify({
                "success": True,
                "report_url": public_url,
                "file_name": filename,
                "present_students": students
            })
        else:
            return send_file(
                io.BytesIO(output.getvalue().encode()),
                mimetype='text/csv',
                as_attachment=True,
                download_name=filename
            )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



if __name__ == '__main__':
    print("✅ Starting Flask server on http://localhost:5000 ...")
    app.run(debug=True)

    
# if __name__ == '__main__':
#     print("✅ Starting Flask server on http://0.0.0.0:5000 ...")
#     app.run(host="0.0.0.0", port=5000, debug=True)