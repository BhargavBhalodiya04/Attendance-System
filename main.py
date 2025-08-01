from flask import Flask, render_template, request, redirect, url_for, session
import os
from dotenv import load_dotenv
import sys
sys.dont_write_bytecode = True

load_dotenv()  # load .env variables

AWS_REGION = os.getenv("AWS_REGION")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
FLASK_SECRET_KEY = os.getenv("SECRET_KEY", "your_default_secret")

# Import your core logic modules and functions
from core.upload_to_s3 import upload_multiple_images, mark_attendance_s3
from core.update_excel import mark_attendance_local
from core.mark_batch_attendance import mark_batch_attendance_s3

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change to a real, secure secret key!

USER = {'username': 'admin', 'password': 'admin'}

# --- ROUTES ---

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

            s3_image_urls = []
            for msg in upload_results:
                if msg.startswith("✅ Uploaded:"):
                    # Parse the S3 key from the message
                    s3_key = msg.split("✅ Uploaded:")[-1].strip()
                    # Make S3 URL (adjust region/bucket as needed)
                    # s3_image_urls.append(f"https://{bucket_name}.s3.{AWS_REGION}.amazonaws.com/{s3_key}")

            student = {
                'er_number': er_number,
                'name': student_name,
                'batch_name': batch_name,
                'bucket_name': bucket_name,
                # 'image_urls': s3_image_urls
            }
            return render_template('upload.html', student=student)
        except Exception as e:
            error_msg = f"❌ Upload failed: {str(e)}"
            return render_template('upload.html', error=error_msg)

    # GET request: show upload form only
    return render_template('upload.html')

@app.route('/take_attendance', methods=['GET', 'POST'])
def take_attendance():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        method = request.form.get('method')
        if method == 'local':
            results = mark_attendance_local()
        elif method == 's3':
            results = mark_attendance_s3()
        else:
            results = ['❌ No attendance method selected.']
        return render_template('upload_result.html', results=results)
    return render_template('take_attendance.html')

# You may implement this route if you have batch-level attendance
@app.route('/batch_attendance_upload', methods=['GET', 'POST'])
def batch_attendance_upload():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        # Implement logic or render form
        pass
    return render_template('batch_attendance_upload.html')

if __name__ == '__main__':
    print("Starting Flask server...")
    app.run(debug=True)
