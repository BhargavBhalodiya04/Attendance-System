from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Needed for session management

# Simple login check (you can replace this with a database)
USER = {'username': 'admin', 'password': 'password'}

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

@app.route('/action/<action>')
def action_page(action):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    return render_template('action.html', action=action)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
