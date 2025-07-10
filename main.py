from flask import Flask, render_template, request, redirect, url_for, session, send_file
import os
from upload_to_s3 import upload_images_to_s3
# from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Needed for session management

# Create uploads folder if it doesn't exist
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Simple login check (replace with DB if needed)
USER = {'username': 'admin', 'password': 'admin'}

# ------------------- Routes ------------------- #

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
    # Put your training code here
    print("Training started")
    return redirect(url_for('home'))

@app.route('/start-mark', methods=['POST'])
def start_mark():
    # Put your attendance marking code here
    print("Attendance marking started")
    return redirect(url_for('home'))

@app.route('/download-pdf', methods=['POST'])
def download_pdf():
    # Example: returning a dummy file, replace with your actual file
    file_path = os.path.join(UPLOAD_FOLDER, 'attendance_report.pdf')
    if not os.path.exists(file_path):
        with open(file_path, 'w') as f:
            f.write('Dummy Attendance Report')

    return send_file(file_path, as_attachment=True)

# ---------- Image Upload to S3 ---------- #
@app.route('/upload-image', methods=['POST'])
def upload_image():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    # Get bucket name and files from the form
    bucket_name = request.form.get('bucket_name')
    files = request.files.getlist('student_images')

    if not bucket_name:
        return "Error: Bucket name is required."

    try:
        # Call the upload function from your existing upload_to_s3.py
        upload_images_to_s3(bucket_name, files)
    except Exception as e:
        return f"Error uploading images: {str(e)}"

    # After uploading, redirect to the home page
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ------------------- Run ------------------- #

if __name__ == '__main__':
    app.run(debug=True)
