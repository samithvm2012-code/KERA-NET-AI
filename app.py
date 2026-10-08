import os
import sqlite3
import urllib.request
import urllib.parse
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'samith_secret_key_sagesecure'

# Flask-Login Setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

ENGINE_NAME = "Samith Architecture Grid Engine (SAGE)"
VERSION = "v4.0-MULTIUSER-SECURE"

# Database Setup for Users and Chats
def init_db():
    conn = sqlite3.connect('kera_net.db')
    cursor = conn.cursor()
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT
        )
    ''')
    # Chats table linked to email
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            session_id TEXT,
            title TEXT,
            sender TEXT,
            message TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

class User(UserMixin):
    def __init__(self, id, email):
        self.id = id
        self.email = email
        self.username = email.split('@')[0]

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('kera_net.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, email FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return User(row[0], row[1])
    return None

def send_login_notification(email, ip_address):
    print(f"[SECURITY ALERT] Successful login/signup detected for '{email}' from IP: {ip_address}. Notification triggered for samithvm2012@gmail.com")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        action = request.form.get('action') # 'login' or 'register'
        
        conn = sqlite3.connect('kera_net.db')
        cursor = conn.cursor()
        
        if action == 'register':
            cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
            if cursor.fetchone():
                conn.close()
                flash('Email already exists! Please login.', 'danger')
                return render_template('login.html', engine=ENGINE_NAME)
            
            hashed_pw = generate_password_hash(password)
            cursor.execute('INSERT INTO users (email, password) VALUES (?, ?)', (email, hashed_pw))
            conn.commit()
            cursor.execute('SELECT id, email FROM users WHERE email = ?', (email,))
            row = cursor.fetchone()
            conn.close()
            
            user = User(row[0], row[1])
            login_user(user)
            send_login_notification(email, request.remote_addr)
            return redirect(url_for('home'))
            
        else: # Login
            cursor.execute('SELECT id, email, password FROM users WHERE email = ?', (email,))
            row = cursor.fetchone()
            conn.close()
            
            if row and check_password_hash(row[2], password):
                user = User(row[0], row[1])
                login_user(user)
                send_login_notification(email, request.remote_addr)
                return redirect(url_for('home'))
            else:
                flash('Invalid email or password!', 'danger')
                
    return render_template('login.html', engine=ENGINE_NAME)

@app.route('/')
@login_required
def home():
    return render_template('index.html', engine=ENGINE_NAME, version=VERSION, user_email=current_user.email)

@app.route('/api/sessions', methods=['GET'])
@login_required
def get_sessions():
    conn = sqlite3.connect('kera_net.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT session_id, title FROM chats WHERE email = ? ORDER BY id DESC', (current_user.email,))
    rows = cursor.fetchall()
    conn.close()
    
    sessions = [{'id': row[0], 'title': row[1]} for row in rows]
    return jsonify({'success': True, 'sessions': sessions})

@app.route('/api/chat/<session_id>', methods=['GET'])
@login_required
def get_chat_history(session_id):
    conn = sqlite3.connect('kera_net.db')
    cursor = conn.cursor()
    cursor.execute('SELECT sender, message FROM chats WHERE email = ? AND session_id = ?', (current_user.email, session_id))
    rows = cursor.fetchall()
    conn.close()
    
    messages = [{'sender': row[0], 'message': row[1]} for row in rows]
    return jsonify({'success': True, 'messages': messages})

@app.route('/ask', methods=['POST'])
@login_required
def ask_question():
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        session_id = data.get('session_id')
        
        if not question or not session_id:
            return jsonify({'success': False, 'error': 'Question and Session ID are required'}), 400
        
        # Query SAGE AI Knowledge API
        encoded_q = urllib.parse.quote(question)
        api_url = f"https://text.pollinations.ai/{encoded_q}"
        
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            answer = response.read().decode('utf-8')
            
        # Save messages to database under the current user's email
        conn = sqlite3.connect('kera_net.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM chats WHERE session_id = ? AND email = ?', (session_id, current_user.email))
        if cursor.fetchone()[0] == 0:
            title = question[:25] + "..." if len(question) > 25 else question
        else:
            cursor.execute('SELECT title FROM chats WHERE session_id = ? AND email = ? LIMIT 1', (session_id, current_user.email))
            res = cursor.fetchone()
            title = res[0] if res else "New Chat"

        cursor.execute('INSERT INTO chats (email, session_id, title, sender, message) VALUES (?, ?, ?, ?, ?)',
                       (current_user.email, session_id, title, 'user', question))
        cursor.execute('INSERT INTO chats (email, session_id, title, sender, message) VALUES (?, ?, ?, ?, ?)',
                       (current_user.email, session_id, title, 'ai', answer))
        conn.commit()
        conn.close()
            
        return jsonify({
            'success': True,
            'answer': answer,
            'title': title,
            'engine': ENGINE_NAME
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)