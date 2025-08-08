from flask import Flask, render_template, request, redirect, url_for, session
import os
import boto3
from dotenv import load_dotenv
import sys
sys.dont_write_bytecode = True

# Load .env variables
load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
FLASK_SECRET_KEY = os.getenv("SECRET_KEY", "your_default_secret")

# Import your core logic modules and functions
from core.upload_to_s3 import upload_multiple_images, mark_attendance_s3
from core.update_excel import mark_attendance_local
from core.mark_batch_attendance import mark_batch_attendance_s3

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

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


@app.route('/upload-image', methods=['GET', 'POST'])
def upload_image():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        bucket_name = request.form.get('bucket_name')
        batch_name = request.form.get('batch_name')
        er_number = request.form.get('er_number')
        student_name = request.form.get('name')
        image_files = request.files.getlist('images')

        # Validate inputs and files
        if not all([bucket_name, batch_name, er_number, student_name]) or not image_files or not any(file.filename for file in image_files):
            error_msg = "❌ All fields are required and images must be selected."
            return render_template('upload.html', error=error_msg)

        try:
            upload_results = upload_multiple_images(batch_name, er_number, student_name, image_files)
            student = {
                'er_number': er_number,
                'name': student_name,
                'batch_name': batch_name,
                'bucket_name': bucket_name,
            }
            return render_template('upload.html', student=student, results=upload_results)
        except Exception as e:
            error_msg = f"❌ Upload failed: {str(e)}"
            return render_template('upload.html', error=error_msg)

    return render_template('upload.html')


@app.route('/take_attendance', methods=['GET', 'POST'])
def take_attendance():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    recognized_students = []

    if request.method == 'POST':
        batch_name = request.form.get('batch_name')  # 👈 get batch folder from form
        uploaded_file = request.files['class_image']

        if not uploaded_file or not batch_name:
            return render_template("take_attendance.html", error="❌ Batch and Image are required.")

        img_bytes = uploaded_file.read()
        rekognition = boto3.client('rekognition', region_name='ap-south-1')
        s3 = boto3.client('s3')

        bucket_name = "ict-attendance"
        prefix = f"{batch_name}/"  # 👈 dynamic batch folder

        try:
            result = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            if 'Contents' not in result:
                return render_template("attendance_summary.html", students=[],
                                       error=f"No students found in batch {batch_name}.")

            for obj in result['Contents']:
                if obj['Key'].endswith(('.jpg', '.jpeg', '.png')):
                    source_key = obj['Key']
                    try:
                        response = rekognition.compare_faces(
                            SourceImage={'S3Object': {'Bucket': bucket_name, 'Name': source_key}},
                            TargetImage={'Bytes': img_bytes},
                            SimilarityThreshold=85
                        )
                        for match in response['FaceMatches']:
                            student_name = source_key.split("/")[-1].split(".")[0]
                            if student_name not in recognized_students:
                                recognized_students.append(student_name)
                    except Exception as e:
                        print(f"Error comparing {source_key}: {str(e)}")

            return render_template("attendance_summary.html",
                                   students=recognized_students,
                                   batch=batch_name)

        except Exception as e:
            return render_template("take_attendance.html", error=f"❌ Error: {str(e)}")

    return render_template("take_attendance.html")


@app.route('/batch_attendance_upload', methods=['GET', 'POST'])
def batch_attendance_upload():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Placeholder for future batch logic
        return render_template('batch_attendance_upload.html', message="Feature under development.")
    
    return render_template('batch_attendance_upload.html')


# ------------- ENTRY POINT ------------- #

if __name__ == '__main__':
    print("✅ Starting Flask server on http://localhost:5000 ...")
    app.run(debug=True)
