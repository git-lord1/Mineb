from flask import Flask, render_template_string, request, redirect, session, jsonify, url_for
import sqlite3, os, time, random

app = Flask(__name__)
app.secret_key = "super_secret_key"

# --- DATABASE SETUP ---
DB = "users.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        tokens INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

def get_user(username):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    u = c.fetchone()
    conn.close()
    return u

def update_tokens(username, tokens):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE users SET tokens=? WHERE username=?", (tokens, username))
    conn.commit()
    conn.close()

init_db()

# --- HTML BASE ---
BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ title }}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background: #0a0a0a; color: #fff; font-family: 'Segoe UI', sans-serif; }
    .card { background: #1c1c1c; border-radius: 15px; box-shadow: 0 0 10px #0f0; }
    .btn-success { background-color: #28a745; border: none; }
    .btn-outline-danger { color: #ff5a5a; border: 1px solid #ff5a5a; }
    .progress { background: #333; }
    .progress-bar { background-color: #00ff88; color: #000; }
  </style>
</head>
<body class="p-4">
<div class="container mt-5" style="max-width:600px;">
  {{ body|safe }}
</div>
</body>
</html>
"""

# --- ROUTES ---
@app.route('/')
def home():
    if 'user' in session:
        return redirect('/dashboard')
    body = """
    <div class="text-center">
      <h2>⚡ Welcome to PyMiner ⚡</h2>
      <p>Mine tokens by running your browser-based miner.</p>
      <a href='/register' class='btn btn-success m-2'>Create Account</a>
      <a href='/login' class='btn btn-outline-light m-2'>Login</a>
    </div>
    """
    return render_template_string(BASE_HTML, title="Home", body=body)

@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if get_user(username):
            msg = "⚠ Username already exists."
        else:
            conn = sqlite3.connect(DB)
            c = conn.cursor()
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            conn.close()
            return redirect('/login')
    body = f"""
    <h3>Register</h3>
    <form method="POST">
      <input class="form-control mb-2" name="username" placeholder="Username" required>
      <input class="form-control mb-2" name="password" type="password" placeholder="Password" required>
      <button class="btn btn-success w-100">Register</button>
      <p class="mt-2 text-danger">{msg}</p>
    </form>
    """
    return render_template_string(BASE_HTML, title="Register", body=body)

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = get_user(username)
        if user and user[2] == password:
            session['user'] = username
            return redirect('/dashboard')
        else:
            msg = "❌ Invalid login credentials."
    body = f"""
    <h3>Login</h3>
    <form method="POST">
      <input class="form-control mb-2" name="username" placeholder="Username" required>
      <input class="form-control mb-2" name="password" type="password" placeholder="Password" required>
      <button class="btn btn-success w-100">Login</button>
      <p class="mt-2 text-danger">{msg}</p>
    </form>
    """
    return render_template_string(BASE_HTML, title="Login", body=body)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')
    username = session['user']
    user = get_user(username)
    tokens = user[3]
    body = """
    <div class="card p-4 mining-card">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <div>
          <h4>Welcome, <strong>{{ username }}</strong></h4>
          <p class="mb-0">Tokens: <span id="token-count">{{ tokens }}</span></p>
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
      interval = setInterval(async () => {
        try {
          const resp = await fetch('/mine', { method: 'POST' });
          const data = await resp.json();
          tokenCountEl.textContent = data.tokens;
          const pct = Math.min(100, Math.floor(Math.random()*100));
          progressBar.style.width = pct + '%';
          progressBar.textContent = pct + '%';
          log.textContent = `+${data.last_reward} tokens mined!\\n` + log.textContent;
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
    return render_template_string(BASE_HTML, title="Dashboard", body=body, username=username, tokens=tokens)

@app.route('/mine', methods=['POST'])
def mine():
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 403
    username = session['user']
    user = get_user(username)
    tokens = user[3]
    reward = random.randint(1, 5)
    tokens += reward
    update_tokens(username, tokens)
    return jsonify({"tokens": tokens, "last_reward": reward})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
