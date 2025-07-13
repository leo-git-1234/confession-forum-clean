
import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session
from werkzeug.utils import secure_filename
import uuid
import random
import json
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.contrib.azure import make_azure_blueprint, azure


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit per file
app.secret_key = 'supersecretkey'  # Needed for flash messages
CONFESSIONS_FILE = 'confessions.json'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}
USERNAMES = [
    'Anonymous Panda', 'Silent Tiger', 'Hidden Fox', 'Masked Owl', 'Secret Dolphin',
    'Clever Raven', 'Mysterious Cat', 'Quiet Wolf', 'Nameless Bear', 'Ghost Eagle'
]

# OAuth setup (replace with your real client IDs and secrets)
google_bp = make_google_blueprint(
    client_id="832834040325-n98nrnnrkjamh4k8o8frr6cdlmkitllq.apps.googleusercontent.com",
    client_secret="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",
    scope=[
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid"
    ]
)
azure_bp = make_azure_blueprint(
    client_id="MICROSOFT_CLIENT_ID",
    client_secret="MICROSOFT_CLIENT_SECRET"
)
app.register_blueprint(google_bp, url_prefix="/login")
app.register_blueprint(azure_bp, url_prefix="/login")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    user = None
    print('DEBUG: google.authorized =', google.authorized)
    print('DEBUG: session =', dict(session))
    print('DEBUG: google token =', google.token)
    if google.authorized:
        resp = google.get("/oauth2/v2/userinfo")
        print('DEBUG: Google userinfo response:', resp)
        if resp.ok:
            user = resp.json()
            print('DEBUG: Google user info:', user)
        else:
            print('DEBUG: Google userinfo request failed:', resp.text)
    elif azure.authorized:
        resp = azure.get("/v1.0/me")
        print('DEBUG: Azure userinfo response:', resp)
        if resp.ok:
            user = resp.json()
            print('DEBUG: Azure user info:', user)
        else:
            print('DEBUG: Azure userinfo request failed:', resp.text)
    if not user:
        print('DEBUG: No user info found, redirecting to index')
        return redirect(url_for('index'))
    session['user'] = user
    user_email = user.get('email') or user.get('userPrincipalName')
    user_name = user.get('name') or user.get('displayName') or user_email
    # Load confessions
    confessions = []
    if os.path.exists(CONFESSIONS_FILE):
        with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
            confessions = json.load(f)
    user_confessions = [c for c in confessions if c.get('user_email') == user_email]
    return render_template('dashboard.html', user_name=user_name, user_confessions=user_confessions, all_confessions=confessions)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Old home route for posting confessions (now requires login)
@app.route('/confess', methods=['GET', 'POST'])
def home():
    if 'user' not in session:
        return redirect(url_for('index'))
    user = session['user']
    user_email = user.get('email') or user.get('userPrincipalName')
    if request.method == 'POST':
        confession = request.form.get('confession')
        files = request.files.getlist('files')
        file_links = []
        if confession:
            for file in files:
                if file and allowed_file(file.filename):
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    filename = f"{uuid.uuid4().hex}.{ext}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    file_links.append(filename)
            username = random.choice(USERNAMES)
            post_id = uuid.uuid4().hex
            confessions = []
            if os.path.exists(CONFESSIONS_FILE):
                with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
                    confessions = json.load(f)
            confessions.append({
                'id': post_id,
                'username': username,
                'user_email': user_email,
                'text': confession,
                'files': file_links,
                'comments': []
            })
            with open(CONFESSIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(confessions, f, indent=2)
            flash('Confession submitted!')
            return redirect(url_for('dashboard'))
    return render_template('index.html', confessions=[])
    if request.method == 'POST':
        confession = request.form.get('confession')
        files = request.files.getlist('files')
        file_links = []
        if confession:
            for file in files:
                if file and allowed_file(file.filename):
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    filename = f"{uuid.uuid4().hex}.{ext}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    file_links.append(filename)
            # Assign random username and unique id
            username = random.choice(USERNAMES)
            post_id = uuid.uuid4().hex
            # Load existing confessions
            confessions = []
            if os.path.exists(CONFESSIONS_FILE):
                with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
                    confessions = json.load(f)
            # Add new confession
            confessions.append({
                'id': post_id,
                'username': username,
                'text': confession,
                'files': file_links,
                'comments': []
            })
            with open(CONFESSIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(confessions, f, indent=2)
            flash('Confession submitted!')
            return redirect(url_for('home'))
    confessions = []
    if os.path.exists(CONFESSIONS_FILE):
        with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
            confessions = json.load(f)
    return render_template('index.html', confessions=confessions)

@app.route('/comment/<post_id>', methods=['POST'])
def add_comment(post_id):
    comment = request.form.get('comment')
    if not comment:
        return redirect(url_for('home'))
    confessions = []
    if os.path.exists(CONFESSIONS_FILE):
        with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
            confessions = json.load(f)
    for confession in confessions:
        if confession['id'] == post_id:
            confession.setdefault('comments', []).append(comment)
            break
    with open(CONFESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(confessions, f, indent=2)
    return redirect(url_for('home'))

@app.route('/edit/<filename>', methods=['GET', 'POST'])
def edit_file(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(filepath):
        flash('File not found.')
        return redirect(url_for('home'))
    if request.method == 'POST':
        new_content = request.form.get('filecontent')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        flash('File updated!')
        return redirect(url_for('home'))
    # Only allow editing text files
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ['txt']:
        flash('Only .txt files can be edited in browser.')
        return redirect(url_for('home'))
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return f'''<h2>Editing {filename}</h2><form method="POST"><textarea name="filecontent" rows="20" cols="80">{content}</textarea><br><button type="submit">Save</button></form>'''
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
