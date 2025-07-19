import os
import json
import sqlite3

DB_FILE = 'confessions.db'
CONFESSIONS_FILE = 'confessions.json'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    return conn

def migrate_confessions():
    if not os.path.exists(CONFESSIONS_FILE):
        print('No confessions.json file found.')
        return
    with open(CONFESSIONS_FILE, 'r', encoding='utf-8') as f:
        confessions = json.load(f)
    conn = get_db()
    c = conn.cursor()
    for conf in confessions:
        # Insert confession
        c.execute('''INSERT OR IGNORE INTO confessions (id, username, user, title, description, text, files, likes, hearts, time_posted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            conf.get('id'),
            conf.get('username'),
            conf.get('user'),
            conf.get('title'),
            conf.get('description'),
            conf.get('text'),
            json.dumps(conf.get('files', [])),
            conf.get('likes', 0),
            conf.get('hearts', 0),
            conf.get('time_posted', '')
        ))
        # Insert comments
        for comment in conf.get('comments', []):
            c.execute('''INSERT INTO comments (confession_id, username, avatar, text, time_posted)
                VALUES (?, ?, ?, ?, ?)''', (
                conf.get('id'),
                comment.get('username'),
                comment.get('avatar', ''),
                comment.get('text'),
                comment.get('time_posted', '')
            ))
    conn.commit()
    conn.close()
    print('Migration complete!')

if __name__ == '__main__':
    migrate_confessions()
