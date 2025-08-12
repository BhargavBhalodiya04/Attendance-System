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

sys.dont_write_bytecode = True

# Load .env variables
load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
FLASK_SECRET_KEY = os.getenv("SECRET_KEY", "your_default_secret")

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

# Enable CORS for React frontend on localhost:8081
CORS(app, supports_credentials=True, resources={r"/*": {"origins": "http://localhost:8081"}})

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

# Import core functions (make sure these exist and import correctly)
from core.upload_to_s3 import upload_multiple_images, mark_attendance_s3
from core.update_excel import mark_attendance_local
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
    # No login check now!

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
        upload_results = upload_multiple_images(batch_name, er_number, student_name, image_files)
        return jsonify({
            "success": True,
            "student": {
                "er_number": er_number,
                "name": student_name,
                "batch_name": batch_name,
                "bucket_name": bucket_name
            },
            "results": upload_results
        }), 200
    except Exception as e:
        return jsonify({"error": f"❌ Upload failed: {str(e)}"}), 500



@app.route('/take_attendance', methods=['GET', 'POST'])
def take_attendance():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    recognized_students = []

    if request.method == 'POST':
        batch_name = request.form.get('batch_name')
        subject_name = request.form.get('subject_name')
        lab_name = request.form.get('lab_name', '')
        uploaded_file = request.files.get('class_image')

        if not uploaded_file or not batch_name or not subject_name:
            return render_template("take_attendance.html", error="❌ Batch, Subject, and Image are required.")

        img_bytes = uploaded_file.read()

        try:
            result = s3_client.list_objects_v2(Bucket="ict-attendance", Prefix=f"{batch_name}/")
        except Exception as e:
            return render_template("take_attendance.html", error=f"❌ Error listing S3 objects: {e}")

        if 'Contents' not in result:
            session['recognized_students'] = []
            session['batch_name'] = batch_name
            session['subject_name'] = subject_name
            session['class_name'] = lab_name
            return redirect(url_for('attendance_summary'))

        for obj in result['Contents']:
            if obj['Key'].lower().endswith(('.jpg', '.jpeg', '.png')):
                source_key = obj['Key']
                try:
                    response = rekognition_client.compare_faces(
                        SourceImage={'S3Object': {'Bucket': "ict-attendance", 'Name': source_key}},
                        TargetImage={'Bytes': img_bytes},
                        SimilarityThreshold=85
                    )
                    for match in response.get('FaceMatches', []):
                        student_nm = source_key.split("/")[-1].rsplit(".", 1)[0]
                        if student_nm not in recognized_students:
                            recognized_students.append(student_nm)
                except Exception as e:
                    print(f"Error comparing {source_key}: {str(e)}")

        session['recognized_students'] = recognized_students
        session['batch_name'] = batch_name
        session['subject_name'] = subject_name
        session['class_name'] = lab_name

        return redirect(url_for('attendance_summary'))

    return render_template("take_attendance.html")


@app.route('/attendance_summary')
def attendance_summary():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    students = session.get('recognized_students', [])
    batch_name = session.get('batch_name', None)
    return render_template("attendance_summary.html", students=students, batch=batch_name)


@app.route('/batch_attendance_upload', methods=['GET', 'POST'])
def batch_attendance_upload():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        return render_template('batch_attendance_upload.html', message="Feature under development.")
    
    return render_template('batch_attendance_upload.html')


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

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ER Number', 'Name', 'Subject Name', 'Batch', 'Date', 'Time'])

    for student in students:
        parts = student.split('_', 1)
        if len(parts) == 2:
            er_number, name = parts
        else:
            er_number, name = student, ''
        writer.writerow([er_number, name, subject_name, batch_name, current_date, current_time])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'{batch_name}_attendance.csv'
    )


if __name__ == '__main__':
    print("✅ Starting Flask server on http://localhost:5000 ...")
    app.run(debug=True)
