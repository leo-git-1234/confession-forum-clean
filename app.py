import os
import openai
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session, jsonify
from werkzeug.utils import secure_filename
import uuid
import random
import json
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit per file
app.secret_key = 'supersecretkey'  # Needed for flash messages

# --- OpenAI API Key Setup ---
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    # Fallback to hardcoded key (not recommended for production)
    OPENAI_API_KEY = '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'
openai.api_key = OPENAI_API_KEY

# --- AI Chatbot API Endpoint ---
@app.route('/api/ai-chat', methods=['POST'])
def ai_chat():
    # Allow both authenticated and unauthenticated users to use the chatbot
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({'error': 'Empty message'}), 400
        ai_reply = generate_ai_comment(user_message)
        return jsonify({'reply': ai_reply})
    except Exception as e:
        print(f"[ERROR] /api/ai-chat: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# Config variables (must be before any route functions)
CONFESSIONS_FILE = 'confessions.json'
USERS_FILE = 'users.json'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}
USERNAMES = [
    'Anonymous Panda', 'Silent Tiger', 'Hidden Fox', 'Masked Owl', 'Secret Dolphin',
    'Clever Raven', 'Mysterious Cat', 'Quiet Wolf', 'Nameless Bear', 'Ghost Eagle'
]




def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2)


# Login and signup page
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        users = load_users()
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            error = 'Please enter both username and password.'
        elif username not in users or not check_password_hash(users[username]['password'], password):
            error = 'Invalid username or password.'
        else:
            session['user'] = {'username': username}
            return redirect(url_for('dashboard'))
    return render_template('login.html', error=error, hide_navbar=True)

# Signup page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        users = load_users()
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            error = 'Please enter both username and password.'
        elif username in users:
            error = 'Username already exists.'
        else:
            users[username] = {'password': generate_password_hash(password)}
            save_users(users)
            flash('Account created! Please log in.')
            return redirect(url_for('index'))
    return render_template('signup.html', error=error, hide_navbar=True)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    # Load confessions
    confessions = []
    if os.path.exists(CONFESSIONS_FILE):
        with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
            confessions = json.load(f)
    user_confessions = [c for c in confessions if c.get('user') == username]
    # dashboard route is now just a redirect to confessions page
    return redirect(url_for('confessions_page'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/confess', methods=['GET', 'POST'])
def home():
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        confession = request.form.get('confession')
        files = request.files.getlist('files')
        file_links = []
        if confession and title and description:
            for file in files:
                if file and allowed_file(file.filename):
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    filename = f"{uuid.uuid4().hex}.{ext}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    file_links.append(filename)
            post_id = uuid.uuid4().hex
            confessions = []
            if os.path.exists(CONFESSIONS_FILE):
                with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
                    confessions = json.load(f)
            confessions.append({
                'id': post_id,
                'username': random.choice(USERNAMES),
                'user': username,
                'title': title,
                'description': description,
                'text': confession,
                'files': file_links,
                'comments': [],
                'likes': 0,
                'hearts': 0,
                'notifications': []
            })
            with open(CONFESSIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(confessions, f, indent=2)
            flash('Confession submitted!')
            return redirect(url_for('confessions_page'))
    return render_template('index.html', confessions=[])
    # ...existing code...

@app.route('/comment/<post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user' not in session:
        return redirect(url_for('index'))
    comment_text = request.form.get('comment')
    if not comment_text:
        return redirect(url_for('home'))
    confessions = []
    if os.path.exists(CONFESSIONS_FILE):
        with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
            confessions = json.load(f)
    for confession in confessions:
        if confession.get('id') == post_id:
            comment = {
                'username': random.choice(USERNAMES),
                'text': comment_text
            }
            if 'comments' not in confession or not isinstance(confession['comments'], list):
                confession['comments'] = []
            confession['comments'].append(comment)
            break
    with open(CONFESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(confessions, f, indent=2)
    return redirect(url_for('confessions_page'))

@app.route('/confessions')
def confessions_page():
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    confessions = []
    if os.path.exists(CONFESSIONS_FILE):
        with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
            confessions = json.load(f)
    return render_template('confessions.html', user_name=username, confessions=confessions)

@app.route('/post', methods=['GET', 'POST'])
def post_confession():
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        confession = request.form.get('confession')
        files = request.files.getlist('files')
        ai_autocomment = request.form.get('ai_autocomment') == 'on'
        file_links = []
        if confession and title and description:
            for file in files:
                if file and allowed_file(file.filename):
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    filename = f"{uuid.uuid4().hex}.{ext}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    file_links.append(filename)
            post_id = uuid.uuid4().hex
            confessions = []
            if os.path.exists(CONFESSIONS_FILE):
                with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
                    confessions = json.load(f)
            # Always start with an empty list for new confession
            comments = []
            if ai_autocomment:
                ai_comment = generate_ai_comment(confession)
                print(f"[DEBUG] Adding AI comment: {ai_comment}")
                comments.append({
                    'username': 'Supportive AI',
                    'text': ai_comment
                })
            confession_obj = {
                'id': post_id,
                'username': random.choice(USERNAMES),
                'user': username,
                'title': title,
                'description': description,
                'text': confession,
                'files': file_links,
                'comments': comments,
                'likes': 0,
                'hearts': 0
            }
            print(f"[DEBUG] Final confession object: {confession_obj}")
            confessions.append(confession_obj)
            with open(CONFESSIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(confessions, f, indent=2)
            flash('Confession submitted!')
            return redirect(url_for('confessions_page'))
    return render_template('post.html', user_name=username)

# --- AI comment generator ---
def generate_ai_comment(confession_text):
    """
    Generate a gentle, hopeful, honest, and helpful AI comment using OpenAI's GPT-3.5/4 API.
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a supportive, gentle, and helpful assistant. Respond to confessions with empathy, hope, and honesty."},
                {"role": "user", "content": confession_text}
            ],
            max_tokens=120,
            temperature=0.7
        )
        ai_reply = response.choices[0].message['content'].strip()
        return ai_reply
    except Exception as e:
        print(f"[ERROR] OpenAI API error: {e}")
        return "[AI Error: Could not generate a response. Please try again later.]"

@app.route('/like/<post_id>', methods=['POST'])
def like_confession(post_id):
    if 'user' not in session:
        return redirect(url_for('index'))
    confessions = []
    if os.path.exists(CONFESSIONS_FILE):
        with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
            confessions = json.load(f)
    for confession in confessions:
        if confession.get('id') == post_id:
            confession['likes'] = confession.get('likes', 0) + 1
            break
    with open(CONFESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(confessions, f, indent=2)
    return redirect(url_for('confessions_page'))

# Heart (love) a confession
@app.route('/heart/<post_id>', methods=['POST'])
def heart_confession(post_id):
    if 'user' not in session:
        return redirect(url_for('index'))
    confessions = []
    if os.path.exists(CONFESSIONS_FILE):
        with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
            confessions = json.load(f)
    for confession in confessions:
        if confession.get('id') == post_id:
            confession['hearts'] = confession.get('hearts', 0) + 1
            break
    with open(CONFESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(confessions, f, indent=2)
    return redirect(url_for('confessions_page'))
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

@app.route('/my_confessions')
def my_confessions():
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    confessions = []
    if os.path.exists(CONFESSIONS_FILE):
        with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
            confessions = json.load(f)
    user_confessions = [c for c in confessions if c.get('user') == username]
    return render_template('my_confessions.html', confessions=user_confessions, user_name=username)

# Route to edit a confession
@app.route('/edit_confession/<post_id>', methods=['GET', 'POST'])
def edit_confession(post_id):
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    confessions = []
    if os.path.exists(CONFESSIONS_FILE):
        with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
            confessions = json.load(f)
    confession = next((c for c in confessions if c.get('id') == post_id and c.get('user') == username), None)
    if not confession:
        flash('Confession not found or you do not have permission to edit it.')
        return redirect(url_for('my_confessions'))
    if request.method == 'POST':
        confession['title'] = request.form.get('title')
        confession['description'] = request.form.get('description')
        confession['text'] = request.form.get('confession')
        # Handle file removals
        remove_files = request.form.getlist('remove_files')
        if 'files' not in confession or not isinstance(confession['files'], list):
            confession['files'] = []
        for filename in remove_files:
            if filename in confession['files']:
                confession['files'].remove(filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
        # Handle new file uploads
        files = request.files.getlist('files')
        for file in files:
            if file and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                confession['files'].append(filename)
        with open(CONFESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(confessions, f, indent=2)
        flash('Confession updated!')
        return redirect(url_for('my_confessions'))
    return render_template('edit_confession.html', confession=confession, user_name=username)

# Route to delete a confession
@app.route('/delete_confession/<post_id>', methods=['POST'])
def delete_confession(post_id):
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    confessions = []
    if os.path.exists(CONFESSIONS_FILE):
        with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
            confessions = json.load(f)
    new_confessions = [c for c in confessions if not (c.get('id') == post_id and c.get('user') == username)]
    if len(new_confessions) == len(confessions):
        flash('Confession not found or you do not have permission to delete it.')
    else:
        with open(CONFESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_confessions, f, indent=2)
        flash('Confession deleted!')
    return redirect(url_for('my_confessions'))



if __name__ == '__main__':
    # Ensure uploads folder exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # Ensure confessions.json exists
    if not os.path.exists(CONFESSIONS_FILE):
        with open(CONFESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)

    # Ensure users.json exists
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)

    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)


