# app.py  -- single-file Flask app with simple auth + mining simulator
import sqlite3
import os
import time
import secrets
from functools import wraps
from flask import Flask, g, render_template_string, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash

# ------------ Config ------------
APP_SECRET = os.environ.get("APP_SECRET") or secrets.token_hex(16)
DB_PATH = os.environ.get("DATABASE_URL") or "app.db"

app = Flask(__name__)
app.secret_key = APP_SECRET
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# ------------ DB helpers ------------
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        tokens INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    db.commit()

@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# call once at startup if DB missing
with app.app_context():
    init_db()

# ------------ simple auth decorators ------------
def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapped

def get_current_user():
    if 'user_id' not in session:
        return None
    db = get_db()
    user = db.execute("SELECT id, username, tokens FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    return user

# ------------ Routes & views ------------
BASE_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{{ title or "MinerSite" }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
      body { background: linear-gradient(180deg,#f8fafc,#ffffff); }
      .mining-card { max-width:900px; margin:30px auto; }
      .brand { font-weight:700; letter-spacing:1px; }
    </style>
  </head>
  <body>
    <nav class="navbar navbar-expand-lg navbar-light bg-white shadow-sm">
      <div class="container">
        <a class="navbar-brand brand" href="{{ url_for('index') }}">SharpMine</a>
        <div class="collapse navbar-collapse">
          <ul class="navbar-nav ms-auto">
            {% if current_user %}
              <li class="nav-item"><a class="nav-link" href="{{ url_for('dashboard') }}">Dashboard</a></li>
              <li class="nav-item"><a class="nav-link" href="{{ url_for('logout') }}">Logout</a></li>
            {% else %}
              <li class="nav-item"><a class="nav-link" href="{{ url_for('login') }}">Login</a></li>
              <li class="nav-item"><a class="nav-link" href="{{ url_for('register') }}">Sign up</a></li>
            {% endif %}
          </ul>
        </div>
      </div>
    </nav>
    <div class="container py-4">
      {% with messages = get_flashed_messages() %}
        {% if messages %}
          <div class="alert alert-info">{{ messages[0] }}</div>
        {% endif %}
      {% endwith %}
      {{ body|safe }}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
  </body>
</html>
"""

@app.route("/")
def index():
    user = get_current_user()
    body = """
    <div class="text-center py-5">
      <h1 class="display-6">Welcome to SharpMine</h1>
      <p class="lead">Create an account, jump into the dashboard, and start simulated mining to earn tokens.</p>
      <div class="mt-4">
        {% if current_user %}
          <a href="{{ url_for('dashboard') }}" class="btn btn-primary btn-lg">Go to Dashboard</a>
        {% else %}
          <a href="{{ url_for('register') }}" class="btn btn-success me-2">Create account</a>
          <a href="{{ url_for('login') }}" class="btn btn-outline-primary">Login</a>
        {% endif %}
      </div>
    </div>
    """
    return render_template_string(BASE_HTML, title="SharpMine", body=body, current_user=user)

@app.route("/register", methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or not password:
            flash("Username and password required.")
            return redirect(url_for('register'))
        db = get_db()
        try:
            db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                       (username, generate_password_hash(password)))
            db.commit()
            flash("Account created — please log in.")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already taken.")
            return redirect(url_for('register'))
    user = get_current_user()
    body = """
    <div class="card p-4 mx-auto" style="max-width:420px">
      <h3 class="mb-3">Create account</h3>
      <form method="post">
        <div class="mb-3">
          <label class="form-label">Username</label>
          <input name="username" class="form-control" required maxlength="50">
        </div>
        <div class="mb-3">
          <label class="form-label">Password</label>
          <input name="password" class="form-control" required type="password" minlength="6">
        </div>
        <button class="btn btn-success w-100">Sign up</button>
      </form>
    </div>
    """
    return render_template_string(BASE_HTML, title="Register", body=body, current_user=user)

@app.route("/login", methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        db = get_db()
        row = db.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,)).fetchone()
        if row and check_password_hash(row['password_hash'], password):
            session.clear()
            session['user_id'] = row['id']
            flash("Logged in.")
            return redirect(url_for('dashboard'))
        flash("Invalid username or password.")
        return redirect(url_for('login'))
    user = get_current_user()
    body = """
    <div class="card p-4 mx-auto" style="max-width:420px">
      <h3 class="mb-3">Login</h3>
      <form method="post">
        <div class="mb-3">
          <label class="form-label">Username</label>
          <input name="username" class="form-control" required>
        </div>
        <div class="mb-3">
          <label class="form-label">Password</label>
          <input name="password" class="form-control" required type="password">
        </div>
        <button class="btn btn-primary w-100">Login</button>
      </form>
    </div>
    """
    return render_template_string(BASE_HTML, title="Login", body=body, current_user=user)

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for('index'))

@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    body = f"""
    <div class="card p-4 mining-card">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <div>
          <h4>Welcome, <strong>{user['username']}</strong></h4>
          <p class="mb-0">Tokens: <span id="token-count">{user['tokens']}</span></p>
        </div>
        <div>
          <button id="start-btn" class="btn btn-success me-2">Start Mining</button>
          <button id="stop-btn" class="btn btn-outline-danger">Stop</button>
        </div>
      </div>

      <div class="mb-3">
        <div class="progress" style="height:22px;">
          <div id="progress-bar" class="progress-bar" role="progressbar" style="width:0%">0%</div>
        </div>
      </div>

      <div id="log" style="min-height:60px; font-family:monospace;"></div>
    </div>

    <script>
    let mining = false;
    let interval = null;
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const progressBar = document.getElementById('progress-bar');
    const tokenCountEl = document.getElementById('token-count');
    const log = document.getElementById('log');

    startBtn.addEventListener('click', () => {
      if (mining) return;
      mining = true;
      progressBar.style.width = '0%';
      progressBar.textContent = '0%';
      log.textContent = 'Mining started...\\n';
      // every 2 seconds we request the server to credit a small random number of tokens
      interval = setInterval(async () => {
        try {
          const resp = await fetch('/mine', { method: 'POST' });
          const data = await resp.json();
          tokenCountEl.textContent = data.tokens;
          // animate progress to reflect server-reported progress (pseudo)
          const pct = Math.min(100, Math.floor((data.session_progress || 0)));
          progressBar.style.width = pct + '%';
          progressBar.textContent = pct + '%';
          log.textContent = `Last reward: ${data.last_reward} tokens — total ${data.tokens}\\n` + log.textContent;
        } catch (e) {
          log.textContent = 'Network error\\n' + log.textContent;
        }
      }, 2000);
    });

    stopBtn.addEventListener('click', () => {
      if (!mining) return;
      mining = false;
      clearInterval(interval);
      log.textContent = 'Mining stopped.\\n' + log.textContent;
    });
    </script>
    """
    return render_template_string(BASE_HTML, title="Dashboard", body=body, current_user=user)

# ------------ Mining endpoint (safe simulator) ------------
# This route simulates mining work server-side and credits the account with a small random reward.
# It also returns a session_progress value (0-100) to show a progress bar client-side.
import random
@app.route("/mine", methods=['POST'])
@login_required
def mine():
    # careful: do not perform expensive CPU loops here in production
    user = get_current_user()
    db = get_db()
    # compute a small random reward (simulate variable block finds)
    reward = random.randint(1, 5)  # 1-5 tokens per tick
    new_total = user['tokens'] + reward
    db.execute("UPDATE users SET tokens = ? WHERE id = ?", (new_total, user['id']))
    db.commit()
    # session progress is a cosmetic number: random walk toward 100 then reset
    sess_prog = session.get('sess_prog', 0) + random.randint(5, 20)
    if sess_prog >= 100:
        sess_prog = 0
    session['sess_prog'] = sess_prog
    return jsonify({
        "tokens": new_total,
        "last_reward": reward,
        "session_progress": sess_prog
    })

# ------------ basic status route ------------
@app.route("/status")
def status():
    return jsonify({"ok": True, "version": "1.0"})

# ------------ run ------------
if __name__ == "__main__":
    # use 0.0.0.0 in production/containers
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
