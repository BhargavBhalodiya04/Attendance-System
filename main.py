from flask import Flask, render_template, request, redirect, url_for, session, send_file
import os
from werkzeug.utils import secure_filename
from core.upload_to_s3 import upload_multiple_images  # Handles Excel too
import sys
sys.dont_write_bytecode = True

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

USER = {'username': 'admin', 'password': 'admin'}

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

    return render_template('action.html', action=action)


@app.route('/start-train', methods=['POST'])
def start_train():
    print("✅ Training started")
    return redirect(url_for('home'))


@app.route('/start-mark', methods=['POST'])
def start_mark():
    print("✅ Attendance marking started")
    return redirect(url_for('home'))


@app.route('/download-pdf', methods=['POST'])
def download_pdf():
    file_path = os.path.join("uploads", 'attendance_report.pdf')
    if not os.path.exists(file_path):
        os.makedirs("uploads", exist_ok=True)
        with open(file_path, 'w') as f:
            f.write('Dummy Attendance Report')

    return send_file(file_path, as_attachment=True)


@app.route('/upload-image', methods=['POST'])
def upload_image():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    bucket_name = request.form.get('bucket_name')
    er_number = request.form.get('er_number')
    student_name = request.form.get('name')
    image_files = request.files.getlist('images')

    if not bucket_name or not er_number or not student_name or not image_files:
        return "❌ All fields are required."

    try:
        result = upload_multiple_images(bucket_name, er_number, student_name, image_files)
        return render_template('action.html', action='upload', results=result)
    except Exception as e:
        return f"❌ Upload failed: {str(e)}"


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)