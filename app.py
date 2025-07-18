# Constants and config variables
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
USERS_FILE = 'users.json'
CONFESSIONS_FILE = 'confessions.json'

# Anonymous username generator
ADJECTIVES = [
    "Mysterious", "Brave", "Silent", "Curious", "Gentle", "Bold", "Clever", "Witty", "Kind", "Lively"
]
ANIMALS = [
    "Fox", "Owl", "Cat", "Wolf", "Bear", "Hawk", "Rabbit", "Lion", "Tiger", "Dolphin"
]
def generate_anonymous_username():
    return f"{random.choice(ADJECTIVES)} {random.choice(ANIMALS)}"


import os
import re
import time
import uuid
import random
import json
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit per file
app.secret_key = 'supersecretkey'  # Needed for flash messages

# --- User activity tracking ---
USER_ACTIVITY_FILE = 'user_activity.json'

def load_user_activity():
    if os.path.exists(USER_ACTIVITY_FILE):
        with open(USER_ACTIVITY_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_user_activity(activity):
    with open(USER_ACTIVITY_FILE, 'w', encoding='utf-8') as f:
        json.dump(activity, f, indent=2)

# Track user activity before each request
@app.before_request
def track_user_activity():
    if 'user' in session:
        username = session['user']['username']
        activity = load_user_activity()
        activity[username] = int(time.time())
        save_user_activity(activity)

# --- Follow and DM routes ---
@app.route('/follow/<anon_username>', methods=['POST'])
def follow_user(anon_username):
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    follows = load_follows()
    # Only allow one follow request per user per anon_username
    if not any(f for f in follows if f['follower'] == username and f['followed'] == anon_username):
        follows.append({'follower': username, 'followed': anon_username, 'accepted': False})
        save_follows(follows)
        flash('Follow request sent!')
    return redirect(url_for('confessions_page'))

@app.route('/accept_follow/<follower>/<anon_username>', methods=['POST'])
def accept_follow(follower, anon_username):
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    follows = load_follows()
    for f in follows:
        if f['follower'] == follower and f['followed'] == anon_username and not f['accepted']:
            f['accepted'] = True
            save_follows(follows)
            flash('Follow request accepted!')
            break
    return redirect(url_for('confessions_page'))

@app.route('/start_dm/<anon_username>', methods=['POST'])
def start_dm(anon_username):
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    follows = load_follows()
    # Only allow DM if follow is accepted
    if any(f for f in follows if f['follower'] == username and f['followed'] == anon_username and f['accepted']):
        return redirect(url_for('chat', sender=username, recipient=anon_username))
    flash('You must be accepted as a follower to send a message.')
    return redirect(url_for('confessions_page'))

@app.route('/inbox')
def inbox():
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    dms = load_dms()
    follows = load_follows()
    # Pending follow requests: where user is the target and not accepted
    pending_requests = [f for f in follows if f['followed'] == username and not f['accepted']]
    # Accepted follows: where user is follower or followed and accepted
    accepted_follows = [f for f in follows if (f['follower'] == username or f['followed'] == username) and f['accepted']]
    # Only show DM conversations for accepted follows
    allowed_parties = set()
    for f in accepted_follows:
        if f['follower'] == username:
            allowed_parties.add(f['followed'])
        elif f['followed'] == username:
            allowed_parties.add(f['follower'])
    # Group DM conversations by other party
    conversations = {}
    for party in allowed_parties:
        convo = [dm for dm in dms if (dm['sender'] == username and dm['recipient'] == party) or (dm['recipient'] == username and dm['sender'] == party)]
        if convo:
            conversations[party] = convo
    return render_template('inbox.html', conversations=conversations, pending_requests=pending_requests, user_name=username)

@app.route('/chat/<sender>/<recipient>', methods=['GET', 'POST'])
def chat(sender, recipient):
    if 'user' not in session:
        return redirect(url_for('index'))
    dms = load_dms()
    convo = [dm for dm in dms if (dm['sender'] == sender and dm['recipient'] == recipient) or (dm['sender'] == recipient and dm['recipient'] == sender)]
    blocked = any(dm.get('blocked') for dm in convo if dm.get('blocked_by') == sender)
    reported = any(dm.get('reported') for dm in convo if dm.get('reported_by') == sender)
    # Active status logic
    activity = load_user_activity()
    now_ts = int(time.time())
    recipient_last_seen = activity.get(recipient)
    active = False
    last_seen_str = None
    if recipient_last_seen:
        if now_ts - recipient_last_seen < 120:
            active = True
        else:
            last_seen_str = time.strftime('%B %d, %Y, %I:%M %p', time.localtime(recipient_last_seen))
    if request.method == 'POST':
        if 'block' in request.form:
            dms.append({'sender': sender, 'recipient': recipient, 'blocked': True, 'blocked_by': sender, 'timestamp': '', 'text': ''})
            save_dms(dms)
            flash('User blocked.')
            return redirect(url_for('inbox'))
        elif 'report' in request.form:
            dms.append({'sender': sender, 'recipient': recipient, 'reported': True, 'reported_by': sender, 'timestamp': '', 'text': ''})
            save_dms(dms)
            flash('User reported.')
            return redirect(url_for('inbox'))
        else:
            text = request.form.get('message')
            if text and not blocked:
                from datetime import datetime
                now = datetime.now()
                timestamp = now.strftime('%B %d, %Y, %I:%M %p')
                dms.append({'sender': sender, 'recipient': recipient, 'timestamp': timestamp, 'text': text})
                save_dms(dms)
                return redirect(url_for('chat', sender=sender, recipient=recipient))
    return render_template('chat.html', sender=sender, recipient=recipient, convo=convo, blocked=blocked, reported=reported, user_name=sender, active=active, last_seen=last_seen_str)

# DM and Follow storage files
DM_FILE = 'dms.json'
FOLLOWS_FILE = 'follows.json'

# Helper functions for DM loading/saving
def load_dms():
    if os.path.exists(DM_FILE):
        with open(DM_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def save_dms(dms):
    with open(DM_FILE, 'w', encoding='utf-8') as f:
        json.dump(dms, f, indent=2)

# Helper functions for follow loading/saving
def load_follows():
    if os.path.exists(FOLLOWS_FILE):
        with open(FOLLOWS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def save_follows(follows):
    with open(FOLLOWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(follows, f, indent=2)


# Lightweight rule-based AI chatbot logic
def generate_ai_response(user_message):

    msg = user_message.lower()
    rules_path = os.path.join(os.path.dirname(__file__), 'ai_chatbot_rules.json')
    try:
        with open(rules_path, 'r', encoding='utf-8') as f:
            rules_data = json.load(f)
    except Exception:
        return "I'm here to support you! If you want to talk about something specific, just let me know."

    for rule in rules_data.get('rules', []):
        keywords = rule.get('keywords', [])
        require_all = rule.get('require_all', False)
        if require_all:
            if all(word in msg for word in keywords):
                return rule['response']
        else:
            if any(word in msg for word in keywords):
                return rule['response']
    return rules_data.get('default', "I'm here to support you! If you want to talk about something specific, just let me know.")

# AI Chatbot API endpoint
@app.route('/api/ai_chat', methods=['POST'])
def api_ai_chat():
    data = request.get_json()
    user_message = data.get('message', '')
    if not user_message:
        return jsonify({'response': "Please enter a message."})
    ai_reply = generate_ai_response(user_message)
    return jsonify({'response': ai_reply})

# ...existing code...


# ...existing code...






# ...existing code...

# Place DM-related code after config variables and helper functions, before route definitions


# ...existing code...







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


# Helper functions for robust confession loading/saving
def load_confessions():
    if os.path.exists(CONFESSIONS_FILE):
        with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def save_confessions(confessions):
    with open(CONFESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(confessions, f, indent=2)

# --- Hide/Show comment logic ---
def get_hidden_comments(username):
    users = load_users()
    user_data = users.get(username, {})
    return set(user_data.get('hidden_comments', []))

def hide_comment_for_user(username, comment_id):
    users = load_users()
    user_data = users.get(username, {})
    hidden = set(user_data.get('hidden_comments', []))
    hidden.add(comment_id)
    user_data['hidden_comments'] = list(hidden)
    users[username] = user_data
    save_users(users)

def show_comment_for_user(username, comment_id):
    users = load_users()
    user_data = users.get(username, {})
    hidden = set(user_data.get('hidden_comments', []))
    hidden.discard(comment_id)
    user_data['hidden_comments'] = list(hidden)
    users[username] = user_data
    save_users(users)

# Route to hide a comment for the current user
@app.route('/hide_comment/<post_id>/<int:comment_idx>', methods=['POST'], endpoint='hide_comment')
def hide_comment(post_id, comment_idx):
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    comment_id = f"{post_id}:{comment_idx}"
    hide_comment_for_user(username, comment_id)
    return redirect(url_for('confessions_page'))

# Route to show a comment for the current user
@app.route('/show_comment/<post_id>/<int:comment_idx>', methods=['POST'], endpoint='show_comment')
def show_comment(post_id, comment_idx):
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    comment_id = f"{post_id}:{comment_idx}"
    show_comment_for_user(username, comment_id)
    return redirect(url_for('confessions_page'))


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
        elif username not in users:
            error = 'Username does not exist.'
        elif not check_password_hash(users[username]['password'], password):
            error = 'Incorrect password.'
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
        elif any(u for u in users if u.lower() == username.lower()):
            error = 'Username already exists (case-insensitive check).'
        elif password == username:
            error = 'Password cannot be the same as username.'
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
            confessions = load_confessions()
            anon_username = generate_anonymous_username()
            from datetime import datetime
            import locale
            locale.setlocale(locale.LC_TIME, '')
            now = datetime.now()
            time_posted = now.strftime('%B %d, %Y, %I:%M %p')
            confession_obj = {
                'id': post_id,
                'username': anon_username,
                'user': username,
                'title': title,
                'description': description,
                'text': confession,
                'files': file_links,
                'comments': [],
                'likes': 0,
                'hearts': 0,
                'notifications': [],
                'time_posted': time_posted
            }
            confessions.append(confession_obj)
            save_confessions(confessions)
            flash('Confession submitted!')
            return redirect(url_for('confessions_page'))
    return render_template('index.html', confessions=[])

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
            # Use confession's anonymous username and avatar for comments
            anon_username = generate_anonymous_username()
            from datetime import datetime
            import locale
            locale.setlocale(locale.LC_TIME, '')
            now = datetime.now()
            time_posted = now.strftime('%B %d, %Y, %I:%M %p')
            comment = {
                'username': anon_username,
                'text': comment_text,
                'time_posted': time_posted
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
    confessions = load_confessions()
    follows = load_follows()
    # Always show newest first, no filtering
    sorted_confessions = list(reversed(confessions))
    # Compute hidden comments for this user
    hidden_comments = get_hidden_comments(username)
    return render_template(
        'confessions.html',
        user_name=username,
        confessions=sorted_confessions,
        follows=follows,
        hidden_comments=hidden_comments
    )

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
            confessions = load_confessions()
            anon_username = generate_anonymous_username()
            from datetime import datetime
            import locale
            locale.setlocale(locale.LC_TIME, '')
            now = datetime.now()
            time_posted = now.strftime('%B %d, %Y, %I:%M %p')
            confession_obj = {
                'id': post_id,
                'username': anon_username,
                'user': username,
                'title': title,
                'description': description,
                'text': confession,
                'files': file_links,
                'comments': [],
                'likes': 0,
                'hearts': 0,
                'notifications': [],
                'time_posted': time_posted
            }
            confessions.append(confession_obj)
            save_confessions(confessions)
            flash('Confession submitted!')
            return redirect(url_for('confessions_page'))
    return render_template('post.html', user_name=username)


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


