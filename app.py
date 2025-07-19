

# --- Utility route to reset follows and DMs for testing ---
import os
import re
import time
import uuid
import random
import json
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
# SocketIO for real-time updates
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit per file
app.secret_key = 'supersecretkey'  # Needed for flash messages
socketio = SocketIO(app)


# --- Socket.IO event for joining rooms ---
def register_socketio_events():
    @socketio.on('join')
    def on_join(data):
        room = data.get('room')
        if room:
            join_room(room)

register_socketio_events()
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
USERS_FILE = 'users.json'
CONFESSIONS_FILE = 'confessions.json'
DB_FILE = 'confessions.db'

# --- SQLite setup ---
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS confessions (
        id TEXT PRIMARY KEY,
        username TEXT,
        user TEXT,
        title TEXT,
        description TEXT,
        text TEXT,
        files TEXT,
        likes INTEGER,
        hearts INTEGER,
        time_posted TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        confession_id TEXT,
        username TEXT,
        avatar TEXT,
        text TEXT,
        time_posted TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT,
        hidden_comments TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS dms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        recipient TEXT,
        timestamp TEXT,
        text TEXT,
        files TEXT,
        read INTEGER,
        system INTEGER,
        blocked INTEGER,
        blocked_by TEXT,
        reported INTEGER,
        reported_by TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS follows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        follower TEXT,
        followed TEXT,
        anon TEXT,
        accepted INTEGER
    )''')
    conn.commit()
    conn.close()
# --- Helper functions for users ---
def db_get_users():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users')
    users = c.fetchall()
    result = {}
    for user in users:
        hidden = json.loads(user['hidden_comments']) if user['hidden_comments'] else []
        result[user['username']] = {
            'password': user['password'],
            'hidden_comments': hidden
        }
    conn.close()
    return result

def db_add_user(username, password):
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO users (username, password, hidden_comments) VALUES (?, ?, ?)', (username, password, json.dumps([])))
    conn.commit()
    conn.close()

def db_update_user_hidden(username, hidden_comments):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET hidden_comments = ? WHERE username = ?', (json.dumps(list(hidden_comments)), username))
    conn.commit()
    conn.close()

# --- Helper functions for DMs ---
def db_get_dms():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM dms')
    dms = c.fetchall()
    result = []
    for dm in dms:
        files = json.loads(dm['files']) if dm['files'] else []
        result.append({
            'sender': dm['sender'],
            'recipient': dm['recipient'],
            'timestamp': dm['timestamp'],
            'text': dm['text'],
            'files': files,
            'read': bool(dm['read']),
            'system': bool(dm['system']),
            'blocked': bool(dm['blocked']),
            'blocked_by': dm['blocked_by'],
            'reported': bool(dm['reported']),
            'reported_by': dm['reported_by']
        })
    conn.close()
    return result

def db_add_dm(dm):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO dms (sender, recipient, timestamp, text, files, read, system, blocked, blocked_by, reported, reported_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
        dm['sender'], dm['recipient'], dm['timestamp'], dm['text'], json.dumps(dm.get('files', [])),
        int(dm.get('read', False)), int(dm.get('system', False)), int(dm.get('blocked', False)),
        dm.get('blocked_by'), int(dm.get('reported', False)), dm.get('reported_by')
    ))
    conn.commit()
    conn.close()

# --- Helper functions for follows ---
def db_get_follows():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM follows')
    follows = c.fetchall()
    result = []
    for f in follows:
        result.append({
            'follower': f['follower'],
            'followed': f['followed'],
            'anon': f['anon'],
            'accepted': bool(f['accepted'])
        })
    conn.close()
    return result

def db_add_follow(follow):
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO follows (follower, followed, anon, accepted) VALUES (?, ?, ?, ?)', (
        follow['follower'], follow['followed'], follow['anon'], int(follow.get('accepted', False))
    ))
    conn.commit()
    conn.close()

# --- Helper functions for confessions ---
def db_get_confessions():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM confessions ORDER BY rowid DESC')
    confs = c.fetchall()
    result = []
    for conf in confs:
        files = json.loads(conf['files']) if conf['files'] else []
        comments = db_get_comments(conf['id'])
        result.append({
            'id': conf['id'],
            'username': conf['username'],
            'user': conf['user'],
            'title': conf['title'],
            'description': conf['description'],
            'text': conf['text'],
            'files': files,
            'comments': comments,
            'likes': conf['likes'],
            'hearts': conf['hearts'],
            'time_posted': conf['time_posted']
        })
    conn.close()
    return result

def db_add_confession(conf):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO confessions (id, username, user, title, description, text, files, likes, hearts, time_posted)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
        conf['id'], conf['username'], conf['user'], conf['title'], conf['description'], conf['text'],
        json.dumps(conf['files']), conf.get('likes', 0), conf.get('hearts', 0), conf['time_posted']
    ))
    conn.commit()
    conn.close()

def db_add_comment(confession_id, comment):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO comments (confession_id, username, avatar, text, time_posted)
        VALUES (?, ?, ?, ?, ?)''', (
        confession_id, comment.get('username'), comment.get('avatar'), comment.get('text'), comment.get('time_posted')
    ))
    conn.commit()
    conn.close()

def db_get_comments(confession_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM comments WHERE confession_id = ? ORDER BY id ASC', (confession_id,))
    comments = c.fetchall()
    result = []
    for com in comments:
        result.append({
            'username': com['username'],
            'avatar': com['avatar'],
            'text': com['text'],
            'time_posted': com['time_posted']
        })
    conn.close()
    return result

def db_like_confession(post_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE confessions SET likes = likes + 1 WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()

def db_heart_confession(post_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE confessions SET hearts = hearts + 1 WHERE id = ?', (post_id,))
    conn.commit()
    conn.close()

# Anonymous username generator
ADJECTIVES = [
    "Mysterious", "Brave", "Silent", "Curious", "Gentle", "Bold", "Clever", "Witty", "Kind", "Lively"
]
ANIMALS = [
    "Fox", "Owl", "Cat", "Wolf", "Bear", "Hawk", "Rabbit", "Lion", "Tiger", "Dolphin"
]
def generate_anonymous_username():
    return f"{random.choice(ADJECTIVES)} {random.choice(ANIMALS)}"

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
    confessions = load_confessions()
    real_user = None
    for confession in confessions:
        if confession.get('username') == anon_username:
            real_user = confession.get('user')
            break
    if not real_user:
        flash('Could not find user for this confession.')
        print(f"[DEBUG] No real user found for anon_username={anon_username}")
        return redirect(url_for('confessions_page'))
    # Prevent self-follow
    if username == real_user:
        flash("You can't follow yourself.")
        return redirect(url_for('confessions_page'))
    print(f"[DEBUG] Follow request received: follower={username}, followed={real_user} (anon={anon_username})")
    follows = load_follows()
    # Remove any previous requests for this user/real_user/anon_username
    follows = [f for f in follows if not (f.get('follower') == username and f.get('followed') == real_user and f.get('anon') == anon_username)]
    # Check if an accepted follow already exists (shouldn't, but just in case)
    accepted_exists = any(f.get('follower') == username and f.get('followed') == real_user and f.get('anon') == anon_username and f.get('accepted') for f in follows)
    # Get persistent anon_map for sender
    anon_map_file = 'anon_map.json'
    if os.path.exists(anon_map_file):
        with open(anon_map_file, 'r', encoding='utf-8') as f:
            anon_map = json.load(f)
    else:
        anon_map = {}
    sender_anon = anon_map.get(username, anon_username)
    if not accepted_exists:
        follows.append({'follower': username, 'followed': real_user, 'anon': anon_username, 'accepted': False})
        save_follows(follows)
        flash('Follow request sent!')
        # Emit real-time event to followed user, include sender's anonymous username
        socketio.emit('follow_request', {'follower': username, 'anon': anon_username, 'follower_anon': sender_anon}, room=real_user)
    else:
        print(f"[DEBUG] Follow request already accepted: follower={username}, followed={real_user}, anon={anon_username}")
        flash('You are already following this user!')
    return redirect(url_for('confessions_page'))

@app.route('/accept_follow/<follower>/<anon_username>', methods=['POST'])
def accept_follow(follower, anon_username):
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    follows = load_follows()
    updated = False
    for f in follows:
        if f.get('follower') == follower and f.get('followed') == username and f.get('anon') == anon_username and not f.get('accepted'):
            f['accepted'] = True
            updated = True
            break
    if updated:
        save_follows(follows)
        flash('Follow request accepted!')
        # Automatically create a DM conversation entry so chat appears in inbox for both users
        dms = load_dms()
        from datetime import datetime
        now = datetime.now()
        timestamp = now.strftime('%B %d, %Y, %I:%M %p')
        # Create chat for both directions if not present
        if not any((dm['sender'] == username and dm['recipient'] == follower) or (dm['sender'] == follower and dm['recipient'] == username) for dm in dms):
            dms.append({'sender': username, 'recipient': follower, 'timestamp': timestamp, 'text': '', 'read': True, 'system': True})
            dms.append({'sender': follower, 'recipient': username, 'timestamp': timestamp, 'text': '', 'read': True, 'system': True})
            save_dms(dms)
        # Emit real-time event to all users (broadcast by default)
        socketio.emit('follow_accepted', {'followed': username, 'anon': anon_username})
        return redirect(url_for('inbox'))
    else:
        flash('No pending follow request found.')
        return redirect(url_for('inbox'))

@app.route('/decline_follow/<follower>/<anon_username>', methods=['POST'])
def decline_follow(follower, anon_username):
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    follows = load_follows()
    # Remove the pending follow request for this anon_username
    new_follows = [f for f in follows if not (f.get('follower') == follower and f.get('followed') == username and not f.get('accepted') and f.get('anon') == anon_username)]
    save_follows(new_follows)
    flash('Follow request declined.')
    # Emit real-time event to follower
    socketio.emit('follow_declined', {'followed': username, 'anon': anon_username}, room=follower)
    return redirect(url_for('inbox'))

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
    # Reset and unify inbox tab logic
    # Pending follow requests: where user is the target and not accepted
    # Use persistent anon_map for all users
    anon_map_file = 'anon_map.json'
    if os.path.exists(anon_map_file):
        with open(anon_map_file, 'r', encoding='utf-8') as f:
            anon_map = json.load(f)
    else:
        anon_map = {}
    # Attach sender's anonymous username to each pending request
    pending_requests = []
    for f in follows:
        if f.get('followed') == username and not f.get('accepted'):
            sender_anon = anon_map.get(f.get('follower'), f.get('anon'))
            req = f.copy()
            req['follower_anon'] = sender_anon
            pending_requests.append(req)
    # Accepted follows: all users with accepted follows (either direction)
    accepted_users = set()
    for f in follows:
        if f.get('accepted'):
            accepted_users.add(f.get('follower'))
            accepted_users.add(f.get('followed'))
    # Group DM conversations by all accepted users except self
    confessions = load_confessions()
    # Use persistent anon_map for all users
    anon_map_file = 'anon_map.json'
    if os.path.exists(anon_map_file):
        with open(anon_map_file, 'r', encoding='utf-8') as f:
            anon_map = json.load(f)
    else:
        anon_map = {}
    conversations = {}
    for party in accepted_users:
        if party == username:
            continue
        convo = [dm for dm in dms if (dm.get('sender') == username and dm.get('recipient') == party) or (dm.get('recipient') == username and dm.get('sender') == party)]
        if convo:
            anon_party = anon_map.get(party, party)
            conversations[anon_party] = {"convo": convo, "real_user": party}
    # Notification: check for unread messages
    has_new_messages = any(dm for dm in dms if dm.get('recipient') == username and not dm.get('read'))
    return render_template('inbox.html', conversations=conversations, pending_requests=pending_requests, user_name=username, has_new_messages=has_new_messages)

@app.route('/chat/<sender>/<recipient>', methods=['GET', 'POST'])
def chat(sender, recipient):
    if 'user' not in session:
        return redirect(url_for('index'))
    dms = load_dms()
    # Always show only anonymous usernames for both sender and recipient
    confessions = load_confessions()
    # Persistent anonymous username mapping for all users
    anon_map_file = 'anon_map.json'
    if os.path.exists(anon_map_file):
        with open(anon_map_file, 'r', encoding='utf-8') as f:
            anon_map = json.load(f)
    else:
        anon_map = {}
    # Ensure every user in chat has an anonymous username
    for user in [sender, recipient]:
        if user not in anon_map:
            # Try to get from confession
            confession_anon = next((c.get('username') for c in confessions if c.get('user') == user), None)
            if confession_anon:
                anon_map[user] = confession_anon
            else:
                anon_map[user] = generate_anonymous_username()
    # Persist anon_map
    with open(anon_map_file, 'w', encoding='utf-8') as f:
        json.dump(anon_map, f, indent=2)
    sender_anon = anon_map.get(sender, sender)
    recipient_anon = anon_map.get(recipient, recipient)
    # Replace all real usernames in convo with anonymous names for rendering
    convo = []
    for dm in dms:
        if (dm['sender'] == sender and dm['recipient'] == recipient) or (dm['sender'] == recipient and dm['recipient'] == sender):
            dm_copy = dm.copy()
            if dm['sender'] == sender:
                dm_copy['sender'] = 'You'
                dm_copy['recipient'] = recipient_anon
            else:
                dm_copy['sender'] = recipient_anon
                dm_copy['recipient'] = 'You'
            convo.append(dm_copy)
    # Mark messages as read for the current user
    for dm in dms:
        if dm['recipient'] == sender and dm['sender'] == recipient and not dm.get('read'):
            dm['read'] = True
    save_dms(dms)
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
            files = request.files.getlist('files') if 'files' in request.files else []
            file_links = []
            if files:
                for file in files:
                    if file and allowed_file(file.filename):
                        ext = file.filename.rsplit('.', 1)[1].lower()
                        filename = f"{uuid.uuid4().hex}.{ext}"
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)
                        file_links.append(filename)
            if (text or file_links) and not blocked:
                from datetime import datetime
                now = datetime.now()
                timestamp = now.strftime('%B %d, %Y, %I:%M %p')
                dms.append({'sender': sender, 'recipient': recipient, 'timestamp': timestamp, 'text': text, 'files': file_links, 'read': False})
                save_dms(dms)
                # Emit real-time event to recipient
                socketio.emit('new_message', {'sender': sender_anon, 'recipient': recipient_anon, 'text': text, 'files': file_links, 'timestamp': timestamp}, room=recipient)
                return redirect(url_for('chat', sender=sender, recipient=recipient))
    # Unify notification badge logic for all pages
    follows = load_follows()
    dms = load_dms()
    has_new_messages = any(dm for dm in dms if dm.get('recipient') == sender and not dm.get('read'))
    pending_requests = [f for f in follows if f.get('followed') == sender and not f.get('accepted')]
    return render_template(
        'chat.html',
        sender=sender_anon,
        recipient=recipient_anon,
        convo=convo,
        blocked=blocked,
        reported=reported,
        user_name=sender,  # Pass real username for welcome
        active=active,
        last_seen=last_seen_str,
        has_new_messages=has_new_messages,
        pending_requests=pending_requests
    )

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

# Place DM-related code after config variables and helper functions


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
    has_new_messages = False
    pending_requests = []
    if 'user' in session:
        username = session['user']['username']
        dms = load_dms()
        follows = load_follows()
        has_new_messages = any(dm for dm in dms if dm.get('recipient') == username and not dm.get('read'))
        pending_requests = [f for f in follows if f.get('followed') == username and not f.get('accepted')]
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
    return render_template('login.html', error=error, hide_navbar=True, has_new_messages=has_new_messages, pending_requests=pending_requests)

# Signup page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    error = None
    has_new_messages = False
    pending_requests = []
    if 'user' in session:
        username = session['user']['username']
        dms = load_dms()
        follows = load_follows()
        has_new_messages = any(dm for dm in dms if dm.get('recipient') == username and not dm.get('read'))
        pending_requests = [f for f in follows if f.get('followed') == username and not f.get('accepted')]
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
    return render_template('signup.html', error=error, hide_navbar=True, has_new_messages=has_new_messages, pending_requests=pending_requests)

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
    # Pass inbox notification context
    follows = load_follows()
    dms = load_dms()
    has_new_messages = any(dm for dm in dms if dm.get('recipient') == username and not dm.get('read'))
    pending_requests = [f for f in follows if f.get('followed') == username and not f.get('accepted')]
    return render_template('index.html', confessions=[], has_new_messages=has_new_messages, pending_requests=pending_requests)

@app.route('/comment/<post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user' not in session:
        return redirect(url_for('index'))
    comment_text = request.form.get('comment')
    if not comment_text:
        return redirect(url_for('home'))
    anon_username = generate_anonymous_username()
    from datetime import datetime
    import locale
    locale.setlocale(locale.LC_TIME, '')
    now = datetime.now()
    time_posted = now.strftime('%B %d, %Y, %I:%M %p')
    comment = {
        'username': anon_username,
        'text': comment_text,
        'avatar': '',
        'time_posted': time_posted
    }
    db_add_comment(post_id, comment)
    return redirect(url_for('confessions_page'))

@app.route('/confessions')
def confessions_page():
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    confessions = db_get_confessions()
    follows = load_follows()
    # Always show newest first, no filtering
    sorted_confessions = confessions
    hidden_comments = get_hidden_comments(username)
    dms = load_dms()
    has_new_messages = any(dm for dm in dms if dm.get('recipient') == username and not dm.get('read'))
    follow_status_map = {}
    accepted_users = set()
    pending_users = set()
    for f in follows:
        if f.get('accepted'):
            accepted_users.add(f.get('follower'))
            accepted_users.add(f.get('followed'))
        else:
            pending_users.add(f.get('follower'))
            pending_users.add(f.get('followed'))
    for confession in sorted_confessions:
        real_user = confession.get('user')
        if real_user == username:
            status = None
        elif real_user in accepted_users:
            status = 'accepted'
        elif real_user in pending_users:
            status = 'pending'
        else:
            status = None
        follow_status_map[confession.get('username')] = status
    pending_requests = [f for f in follows if f.get('followed') == username and not f.get('accepted')]
    return render_template(
        'confessions.html',
        user_name=username,
        confessions=sorted_confessions,
        follows=follows,
        hidden_comments=hidden_comments,
        has_new_messages=has_new_messages,
        follow_status_map=follow_status_map,
        pending_requests=pending_requests
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
                'likes': 0,
                'hearts': 0,
                'time_posted': time_posted
            }
            db_add_confession(confession_obj)
            flash('Confession submitted!')
            return redirect(url_for('confessions_page'))
    # Pass inbox notification context
    follows = load_follows()
    dms = load_dms()
    has_new_messages = any(dm for dm in dms if dm.get('recipient') == username and not dm.get('read'))
    pending_requests = [f for f in follows if f.get('followed') == username and not f.get('accepted')]
    return render_template('post.html', user_name=username, has_new_messages=has_new_messages, pending_requests=pending_requests)


@app.route('/like/<post_id>', methods=['POST'])
def like_confession(post_id):
    if 'user' not in session:
        return redirect(url_for('index'))
    db_like_confession(post_id)
    return redirect(url_for('confessions_page'))

# Heart (love) a confession
@app.route('/heart/<post_id>', methods=['POST'])
def heart_confession(post_id):
    if 'user' not in session:
        return redirect(url_for('index'))
    db_heart_confession(post_id)
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
    confessions = db_get_confessions()
    user_confessions = [c for c in confessions if c.get('user') == username]
    # Pass inbox notification context
    follows = load_follows()
    dms = load_dms()
    has_new_messages = any(dm for dm in dms if dm.get('recipient') == username and not dm.get('read'))
    pending_requests = [f for f in follows if f.get('followed') == username and not f.get('accepted')]
    return render_template('my_confessions.html', confessions=user_confessions, user_name=username, has_new_messages=has_new_messages, pending_requests=pending_requests)

# Route to edit a confession
@app.route('/edit_confession/<post_id>', methods=['GET', 'POST'])
def edit_confession(post_id):
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    confessions = db_get_confessions()
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
        # Update confession in DB
        conn = get_db()
        c = conn.cursor()
        c.execute('''UPDATE confessions SET title=?, description=?, text=?, files=? WHERE id=? AND user=?''', (
            confession['title'], confession['description'], confession['text'], json.dumps(confession['files']), post_id, username
        ))
        conn.commit()
        conn.close()
        flash('Confession updated!')
        return redirect(url_for('my_confessions'))
    return render_template('edit_confession.html', confession=confession, user_name=username)

# Route to delete a confession
@app.route('/delete_confession/<post_id>', methods=['POST'])
def delete_confession(post_id):
    if 'user' not in session:
        return redirect(url_for('index'))
    username = session['user']['username']
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM confessions WHERE id=? AND user=?', (post_id, username))
    if c.rowcount == 0:
        flash('Confession not found or you do not have permission to delete it.')
    else:
        conn.commit()
        flash('Confession deleted!')
    conn.close()
    return redirect(url_for('my_confessions'))



if __name__ == '__main__':
    # Ensure uploads folder exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # Initialize SQLite database tables
    init_db()

    socketio.run(app, host='127.0.0.1', port=5000, debug=False)


