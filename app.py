from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def home():
    action = request.form.get("action", "Train Model")

    if request.method == "POST":
        if action == "Train Model":
            message = "Training model started..."
        elif action == "Mark Attendance":
            message = "Marking attendance..."
        elif action == "Download Attendance PDF":
            message = "Downloading attendance PDF..."
        else:
            message = ""
        return render_template("index.html", action=action, message=message)

    return render_template("index.html", action=action, message="")

if __name__ == "__main__":
    app.run(debug=True)
