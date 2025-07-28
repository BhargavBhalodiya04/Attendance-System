from flask import Flask, render_template, request, redirect, url_for
import os
from werkzeug.utils import secure_filename

from core.upload_to_s3 import upload_file_to_s3
from core.rekognition_multi_search import recognize_faces_in_image
from core.mark_attendance import mark_attendance
from core.aws_config import BUCKET_NAME, COLLECTION_ID

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/action/<action>')
def action_page(action):
    return render_template('action.html', action=action)


# ✅ Upload student image(s)
@app.route('/upload_image', methods=['POST'])
def upload_image():
    bucket_name = request.form['bucket_name']
    er_number = request.form['er_number']
    name = request.form['name']
    files = request.files.getlist('images')

    results = []

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[1].lower()
            s3_key = f"{er_number}_{name}_{files.index(file)+1}.{ext}"

            local_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(local_path)

            upload_file_to_s3(local_path, bucket_name, s3_key)
            results.append(f"✅ {s3_key}")
        else:
            results.append(f"❌ Invalid file: {file.filename}")

    return render_template('action.html', action='upload', results=results)


# ✅ Mark attendance from class photo(s)
@app.route('/start_mark', methods=['POST'])
def start_mark():
    files = request.files.getlist('images')
    recognized_students = set()
    results = []

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            local_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(local_path)

            s3_key = f"class_images/{filename}"
            upload_file_to_s3(local_path, BUCKET_NAME, s3_key)

            matched_ids = recognize_faces_in_image(BUCKET_NAME, s3_key, COLLECTION_ID)

            if matched_ids:
                for student_id in matched_ids:
                    if student_id not in recognized_students:
                        try:
                            er, name = student_id.split('_', 1)
                            mark_attendance(er, name)
                            recognized_students.add(student_id)
                            results.append(f"✅ {student_id}")
                        except ValueError:
                            results.append(f"❌ Invalid student ID format: {student_id}")
            else:
                results.append(f"❌ No faces matched in {filename}")
        else:
            results.append(f"❌ Invalid file: {file.filename}")

    return render_template('upload_result.html', results=results)


if __name__ == '__main__':
    app.run(debug=True)
