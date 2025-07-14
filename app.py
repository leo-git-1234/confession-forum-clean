# Config variables (must be before any route functions)
CONFESSIONS_FILE = 'confessions.json'
USERS_FILE = 'users.json'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}
USERNAMES = [
    'Anonymous Panda', 'Silent Tiger', 'Hidden Fox', 'Masked Owl', 'Secret Dolphin',
    'Clever Raven', 'Mysterious Cat', 'Quiet Wolf', 'Nameless Bear', 'Ghost Eagle'
]
import os
import re
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



# --- OpenAI Model Selection ---
# You can try changing this to a model your account supports, e.g. 'gpt-3.5-turbo-0125', 'gpt-4o', etc.
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo')

# Try to support both openai>=1.x and openai<1.0


# --- AI Chatbot API Endpoint ---
@app.route('/api/ai-chat', methods=['POST'])
def ai_chat():
    # Allow both authenticated and unauthenticated users to use the chatbot
    data = request.get_json()
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({'error': 'Empty message'}), 400

    # --- Begin chatbot logic (formerly generate_ai_comment) ---
    import string
    greetings = [
        r"^hi[.!]*$", r"^hello[.!]*$", r"^hey[.!]*$", r"^yo[.!]*$", r"^sup[.!]*$", r"^good (morning|afternoon|evening)[.!]*$"
    ]
    confession_text_clean = user_message.strip().lower()
    # Greeting detection
    for pattern in greetings:
        if re.match(pattern, confession_text_clean):
            return jsonify({'reply': random.choice([
                "Hello! How can I support you today?",
                "Hi there! I'm here to listen if you want to share anything.",
                "Hey! Feel free to talk to me about anything on your mind.",
                "Hello! I'm always here if you need someone to talk to.",
                "Hi! What's on your mind today?"
            ])})

    # Question detection and expanded scenario handling
    if confession_text_clean.endswith('?'):
        question = confession_text_clean.translate(str.maketrans('', '', string.punctuation))
        # Social/relationship scenarios
        if 'block' in question or 'blocked' in question:
            return jsonify({'reply': random.choice([
                "Being blocked can feel really hurtful and confusing. Sometimes people need space, but it doesn't define your worth.",
                "If someone blocked you, it's okay to feel sad or regretful. Give it time and focus on your own healing.",
                "It's tough to be blocked by someone you care about. Try to respect their boundaries and take care of yourself."
            ])})
        if 'regret' in question or 'regretful' in question:
            return jsonify({'reply': random.choice([
                "Regret is a normal feeling. Try to learn from the experience and be gentle with yourself.",
                "Everyone makes mistakes. What matters is how you move forward and grow from them.",
                "If you're feeling regretful, consider what you can do differently next time. Self-forgiveness is important."
            ])})
        if 'breakup' in question or 'ex' in question or 'move on' in question:
            return jsonify({'reply': random.choice([
                "Breakups are hard. Allow yourself to grieve and lean on friends or family for support.",
                "Moving on takes time. Focus on self-care and things that make you happy.",
                "It's normal to miss your ex, but remember why things ended and prioritize your own well-being."
            ])})
        if 'family' in question or 'parent' in question or 'mom' in question or 'dad' in question or 'sibling' in question:
            return jsonify({'reply': random.choice([
                "Family relationships can be complicated. Open communication and setting boundaries can help.",
                "If you're struggling with family, try to express your feelings calmly and seek support if needed.",
                "Remember, it's okay to ask for help if family issues are overwhelming. You're not alone."
            ])})
        if 'bully' in question or 'bullied' in question or 'harass' in question:
            return jsonify({'reply': random.choice([
                "Bullying is never okay. If you feel safe, reach out to a trusted adult or authority for help.",
                "You deserve respect. Don't hesitate to seek support if you're being bullied or harassed.",
                "Remember, you're not alone. There are people who care and want to help you through this."
            ])})
        if 'selfesteem' in question or 'self esteem' in question or 'confidence' in question:
            return jsonify({'reply': random.choice([
                "Building self-esteem takes time. Celebrate your small wins and be kind to yourself.",
                "Confidence grows with practice. Try to challenge negative thoughts and focus on your strengths.",
                "Everyone has insecurities. Remember, you have unique qualities that make you valuable."
            ])})
        if 'stress' in question or 'anxious' in question or 'anxiety' in question:
            return jsonify({'reply': random.choice([
                "When you're feeling stressed, try taking a few deep breaths and give yourself a short break. Would you like some relaxation tips?",
                "Managing anxiety can be tough. Sometimes writing down your thoughts or talking to a friend helps. Want more advice?",
                "It's normal to feel anxious sometimes. Try to focus on what you can control and let go of what you can't."
            ])})
        if 'friend' in question or 'relationship' in question or 'crush' in question:
            return jsonify({'reply': random.choice([
                "Relationships can be complicated. Honest communication is often the best first step.",
                "If you're having trouble with a friend, try to see things from their perspective and talk openly.",
                "Crushes can be exciting and confusing! Be yourself and take things slow."
            ])})
        if 'sad' in question or 'depressed' in question or 'down' in question:
            return jsonify({'reply': random.choice([
                "If you're feeling down, remember it's okay to ask for help. You're not alone.",
                "Sometimes talking to someone you trust can make a big difference when you're sad.",
                "Try to do something small that you enjoy, even if it's just listening to music or going for a walk."
            ])})
        if 'motivation' in question or 'procrastinate' in question:
            return jsonify({'reply': random.choice([
                "Motivation can come and go. Setting small, achievable goals can help you get started.",
                "If you're procrastinating, try breaking your task into tiny steps and reward yourself for progress.",
                "Everyone struggles with motivation sometimes. Be kind to yourself and start with one small action."
            ])})
        if 'future' in question or 'goal' in question or 'dream' in question:
            return jsonify({'reply': random.choice([
                "Thinking about the future can be overwhelming. Focus on what you can do today to move closer to your goals.",
                "Dreams are important! Break them into small steps and celebrate your progress.",
                "It's okay if you don't have everything figured out. Take it one day at a time."
            ])})
        if 'health' in question or 'sick' in question or 'ill' in question:
            return jsonify({'reply': random.choice([
                "Health is important. Make sure to rest, eat well, and reach out to a doctor if needed.",
                "If you're feeling unwell, don't hesitate to ask for help or support.",
                "Taking care of your body and mind is a priority. Listen to what you need."
            ])})
        if 'money' in question or 'finance' in question or 'broke' in question:
            return jsonify({'reply': random.choice([
                "Money worries are common. Try to make a simple budget and reach out for advice if you need it.",
                "Financial stress can be tough. Remember, your value isn't defined by your bank account.",
                "If you're struggling financially, look for local resources or support groups that can help."
            ])})
        # General advice for questions
        return jsonify({'reply': random.choice([
            "That's a great question. Sometimes, reflecting on what you truly want can help you find the answer.",
            "I'm here to help! Can you tell me a bit more about your situation?",
            "There's no one-size-fits-all answer, but I'm happy to listen and offer advice if you'd like.",
            "Life is full of ups and downs. Trust yourself to get through this.",
            "If you want, I can help you brainstorm some next steps."
        ])})

    # Feeling/venting detection
    feeling_keywords = [
        'sad', 'depressed', 'anxious', 'anxiety', 'stress', 'angry', 'lonely', 'alone', 'tired', 'overwhelmed', 'hopeless', 'lost', 'scared', 'afraid', 'worry', 'worried', 'panic', 'cry', 'cried', 'crying'
    ]
    for word in feeling_keywords:
        if word in confession_text_clean:
            return jsonify({'reply': random.choice([
                f"I'm sorry you're feeling {word}. Remember, it's okay to feel this way and you're not alone.",
                f"It takes courage to talk about feeling {word}. If you want advice or just to vent, I'm here.",
                f"When you feel {word}, try to take a break and do something kind for yourself."
            ])})

    # Advice for life/school/work
    if any(x in confession_text_clean for x in ['school', 'exam', 'study', 'work', 'job', 'career', 'future']):
        return jsonify({'reply': random.choice([
            "Balancing everything can be tough. Remember to take breaks and ask for help if you need it.",
            "It's okay to feel uncertain about the future. Focus on what you can do today, one step at a time.",
            "Studying is important, but so is your well-being. Make sure to rest and take care of yourself."
        ])})

    # If user says thanks or expresses gratitude
    if any(x in confession_text_clean for x in ['thank', 'thanks', 'appreciate', 'grateful']):
        return jsonify({'reply': random.choice([
            "You're very welcome! If you ever need to talk, I'm here.",
            "No problem at all! Let me know if you have more on your mind.",
            "I'm glad I could help. Take care!"
        ])})

    # General fallback: more variety, advice, and conversation
    general_responses = [
        "I'm here for you. If you want advice or just someone to listen, let me know!",
        "Life can be challenging, but you're stronger than you think.",
        "If you want to talk more about it, I'm all ears.",
        "Sometimes sharing your thoughts is the first step to feeling better.",
        "Would you like some advice or just to vent? Either way, I'm here.",
        "Remember, every day is a new opportunity. What would you like to focus on today?",
        "If you have a specific problem, feel free to ask and I'll do my best to help!",
        "You matter, and your feelings are important."
    ]
    return jsonify({'reply': random.choice(general_responses)})


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
            # AI auto-comment feature is disabled since generate_ai_comment is removed.
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


