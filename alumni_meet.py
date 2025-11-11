"""
Alumni Meet Planning System — Single-file Flask app
White (iOS-like) theme, single-file (frontend + backend) + static/background.jpg

Usage:
  1. Save this file as `alumni_meet.py`.
  2. Put your uploaded image at `static/background.jpg` (keep the filename).
  3. Install Flask: `pip install flask`
  4. Run: `python alumni_meet.py` then open http://127.0.0.1:5000

Notes:
 - This version is "open to everyone" (no auth). It's optimized for clarity, performance and
   safe CSV exporting using the csv module. Particle animation is tuned to look elegant
   and not conflict with layout or readability.
 - Replace GITHUB_URL and LINKEDIN_URL with your real profile links if desired.
"""

from flask import Flask, g, render_template_string, request, redirect, url_for, send_from_directory, Response
import sqlite3
import os
from datetime import datetime
import csv
import io

# ---------- Configuration ----------
DATABASE = 'alumni_meet.db'
DEBUG = True
SECRET = 'replace_this_with_a_secure_secret'

GITHUB_URL = 'https://github.com/ZahikAbasDar'
LINKEDIN_URL = 'https://www.linkedin.com/in/Zahik-Abas'
FOOTER_TAGLINE = 'CSE PCTE Student — Alumni Meet Planning System'

# ---------- Flask app ----------
app = Flask(__name__)
app.config.from_object(__name__)

# ---------- Database helpers: small wrapper for convenience ----------

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        # set detect_types if you want to handle dates specially later
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript('''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        date TEXT,
        location TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS attendees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        rsvp_status TEXT DEFAULT 'Pending',
        checked_in INTEGER DEFAULT 0,
        created_at TEXT,
        FOREIGN KEY (event_id) REFERENCES events(id)
    );
    ''')
    db.commit()

# ---------- Small utilities ----------

def sanitize_text(s, maxlen=300):
    if s is None:
        return ''
    s = str(s).strip()
    if len(s) > maxlen:
        return s[:maxlen]
    return s

# ---------- Routes ----------

@app.route('/init_db')
def route_init_db():
    init_db()
    return "Database initialized. <a href='/'>Go home</a>"

@app.route('/')
def index():
    db = get_db()
    events = db.execute('SELECT * FROM events ORDER BY date DESC').fetchall()
    return render_template_string(TEMPLATE_INDEX, events=events, github=GITHUB_URL, linkedin=LINKEDIN_URL, tagline=FOOTER_TAGLINE)

@app.route('/event/new', methods=['GET','POST'])
def new_event():
    if request.method == 'POST':
        title = sanitize_text(request.form.get('title', ''), maxlen=120)
        if not title:
            return "Title required", 400
        description = sanitize_text(request.form.get('description', ''), maxlen=2000)
        date = sanitize_text(request.form.get('date', ''), maxlen=32)
        location = sanitize_text(request.form.get('location', ''), maxlen=200)
        db = get_db()
        db.execute('INSERT INTO events (title, description, date, location, created_at) VALUES (?,?,?,?,?)',
                   (title, description, date, location, datetime.utcnow().isoformat()))
        db.commit()
        return redirect(url_for('index'))
    return render_template_string(TEMPLATE_NEW_EVENT, github=GITHUB_URL, linkedin=LINKEDIN_URL, tagline=FOOTER_TAGLINE)

@app.route('/event/<int:event_id>')
def view_event(event_id):
    db = get_db()
    event = db.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
    if not event:
        return 'Event not found', 404
    attendees = db.execute('SELECT * FROM attendees WHERE event_id = ? ORDER BY created_at DESC', (event_id,)).fetchall()
    return render_template_string(TEMPLATE_EVENT, event=event, attendees=attendees, github=GITHUB_URL, linkedin=LINKEDIN_URL, tagline=FOOTER_TAGLINE)

@app.route('/event/<int:event_id>/rsvp', methods=['POST'])
def rsvp(event_id):
    name = sanitize_text(request.form.get('name', ''), maxlen=150)
    if not name:
        return 'Name is required', 400
    email = sanitize_text(request.form.get('email', ''), maxlen=200)
    phone = sanitize_text(request.form.get('phone', ''), maxlen=40)
    status = sanitize_text(request.form.get('status', 'Attending'), maxlen=32)
    db = get_db()
    # Ensure event exists
    ev = db.execute('SELECT id FROM events WHERE id = ?', (event_id,)).fetchone()
    if not ev:
        return 'Event not found', 404
    db.execute('INSERT INTO attendees (event_id,name,email,phone,rsvp_status,created_at) VALUES (?,?,?,?,?,?)',
               (event_id, name, email, phone, status, datetime.utcnow().isoformat()))
    db.commit()
    return redirect(url_for('view_event', event_id=event_id))

@app.route('/attendee/<int:att_id>/toggle_checkin')
def toggle_checkin(att_id):
    db = get_db()
    row = db.execute('SELECT checked_in, event_id FROM attendees WHERE id = ?', (att_id,)).fetchone()
    if row:
        new = 0 if row['checked_in'] else 1
        db.execute('UPDATE attendees SET checked_in = ? WHERE id = ?', (new, att_id))
        db.commit()
        return redirect(url_for('view_event', event_id=row['event_id']))
    return 'Not found', 404

@app.route('/export/event/<int:event_id>/csv')
def export_event_csv(event_id):
    db = get_db()
    event = db.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
    if not event:
        return 'Event not found', 404
    attendees = db.execute('SELECT * FROM attendees WHERE event_id = ? ORDER BY created_at DESC', (event_id,)).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Email', 'Phone', 'RSVP', 'Checked In'])
    for a in attendees:
        writer.writerow([a['name'] or '', a['email'] or '', a['phone'] or '', a['rsvp_status'] or '', int(a['checked_in'])])
    csv_data = output.getvalue()
    output.close()
    return Response(csv_data, mimetype='text/csv', headers={
        'Content-Disposition': f'attachment; filename=event_{event_id}_attendees.csv'
    })

# Let Flask serve static normally; keep a small explicit route if necessary
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# ---------- Embedded Templates (clean white theme, accessible) ----------

BASE_HTML = r'''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Alumni Meet — {{ title if title else 'Home' }}</title>
  <style>
    :root{
      --glass-bg: rgba(255,255,255,0.82);
      --glass-border: rgba(0,0,0,0.06);
      --muted: #6b7280;
      --accent1: #0ea5e9; /* light blue */
      --accent2: #7c3aed; /* violet */
      --radius: 14px;
    }
    *{box-sizing:border-box}
    body{font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial; margin:0;background:#ffffff;color:#0f172a}
    a{text-decoration:none}

    /* Hero/Background */
    .hero{position:relative;min-height:420px;display:flex;align-items:center;justify-content:center;padding:48px 20px}
    .bg-image{position:absolute;inset:0;background-size:cover;background-position:center;filter:contrast(.9) brightness(.9);z-index:0}
    .bg-overlay{position:absolute;inset:0;background:linear-gradient(180deg,rgba(255,255,255,0.48),rgba(255,255,255,0.72));mix-blend-mode:normal;z-index:1}

    .hero-inner{position:relative;z-index:2;max-width:1100px;text-align:center}
    h1{font-size:clamp(22px,4vw,34px);margin:0;color:#071132}
    p.lead{margin-top:8px;color:var(--muted)}

    /* Card */
    .container{padding:24px;max-width:1100px;margin: -80px auto 32px}
    .card{background:var(--glass-bg);backdrop-filter: blur(8px);border-radius:var(--radius);box-shadow:0 10px 30px rgba(16,24,40,0.06);border:1px solid var(--glass-border);padding:18px}

    /* Buttons (iPhone-like) */
    .btn{display:inline-flex;align-items:center;gap:10px;padding:10px 16px;border-radius:999px;border:none;cursor:pointer;font-weight:700;box-shadow:0 8px 24px rgba(12,18,30,0.06);transition:transform .14s ease,box-shadow .14s ease}
    .btn:active{transform:translateY(1px)}
    .btn-primary{background:linear-gradient(180deg,var(--accent1),var(--accent2));color:white}
    .btn-ghost{background:transparent;border:1px solid rgba(15,23,42,0.06);color:#0f172a}

    /* Layout */
    .flex{display:flex;gap:12px;align-items:center}
    .grid{display:grid;grid-template-columns:1fr;gap:12px}
    @media(min-width:880px){.grid{grid-template-columns:2fr 1fr}}

    input,textarea,select{width:100%;padding:10px;border-radius:10px;border:1px solid rgba(15,23,42,0.06);outline:none;background:white}
    label{font-size:0.95rem;color:#0f172a}

    .muted{color:var(--muted)}
    .att-item{display:flex;justify-content:space-between;padding:10px;border-bottom:1px dashed rgba(15,23,42,0.04)}

    footer{padding:18px;text-align:center;color:#334155;margin-top:18px}
  </style>
</head>
<body>
  <div class="hero" role="banner">
    <div class="bg-image" id="bg-image"></div>
    <div class="bg-overlay"></div>
    <div class="hero-inner">
      <h1>{{ title or 'Alumni Meet Planner' }}</h1>
      <p class="lead">Plan reunions, manage attendees, and make memorable events — polished, simple and open.</p>
      <div style="margin-top:14px" class="flex">
        <a class="btn btn-primary" href="/event/new">Create Event</a>
        <a class="btn btn-ghost" href="#footer">Profiles & Footer</a>
      </div>
    </div>
  </div>

  <main class="container">
    <div class="card">
      {% block content %}{% endblock %}
    </div>

    <footer id="footer">
      <div style="display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap">
        <div class="muted">{{ tagline }}</div>
        <a class="muted" href="{{ github }}" target="_blank">GitHub</a>
        <a class="muted" href="{{ linkedin }}" target="_blank">LinkedIn</a>
      </div>
      <div style="margin-top:8px" class="muted">Made with ❤️ — Customize links in the python file (GITHUB_URL & LINKEDIN_URL)</div>
    </footer>
  </main>

  <script>
  // Safe background loader — will fall back to a soft gradient if static image missing
  (function(){
    const el = document.getElementById('bg-image');
    const url = '/static/background.jpg';
    fetch(url, {method:'HEAD'}).then(r=>{ if(r.ok){ el.style.backgroundImage = `url(${url})`; } else { el.style.backgroundImage = `linear-gradient(180deg, #f8fafc, #eef2ff)`; }}).catch(e=>{ el.style.backgroundImage = `linear-gradient(180deg, #f8fafc, #eef2ff)`; });
  })();

  // Gentle particle animation using canvas overlay but tuned for performance and compatibility
  (function(){
    const container = document.createElement('div');
    container.style.position='absolute'; container.style.inset='0'; container.style.zIndex='1'; container.style.pointerEvents='none';
    document.querySelector('.hero').appendChild(container);
    const canvas = document.createElement('canvas'); container.appendChild(canvas);
    const ctx = canvas.getContext('2d');

    function resize(){
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(300, Math.floor(container.clientWidth * dpr));
      canvas.height = Math.max(200, Math.floor(container.clientHeight * dpr));
      canvas.style.width = container.clientWidth + 'px';
      canvas.style.height = container.clientHeight + 'px';
      ctx.scale(dpr, dpr);
    }
    window.addEventListener('resize', resize);
    resize();

    // moderate particle count for smoothness on most devices
    const PARTICLES = 140;
    const particles = [];
    for(let i=0;i<PARTICLES;i++){
      particles.push({
        x: Math.random()*container.clientWidth,
        y: Math.random()*container.clientHeight,
        vx: (Math.random()-0.5)*0.4,
        vy: (Math.random()-0.5)*0.4,
        r: 0.7 + Math.random()*1.6,
        alpha: 0.08 + Math.random()*0.35
      });
    }

    // only draw limited linking lines to avoid O(n^2) cost explosion
    function step(){
      ctx.clearRect(0,0,canvas.width,canvas.height);
      const W = container.clientWidth, H = container.clientHeight;
      for(const p of particles){
        p.x += p.vx; p.y += p.vy;
        if(p.x < 0 || p.x > W) p.vx *= -1;
        if(p.y < 0 || p.y > H) p.vy *= -1;
        ctx.beginPath(); ctx.globalAlpha = p.alpha; ctx.fillStyle = '#0f172a'; ctx.arc(p.x, p.y, p.r, 0, Math.PI*2); ctx.fill();
      }
      // link only nearest neighbours using spatial hashing-ish approach (simple grid)
      const gridSize = 120;
      const grid = new Map();
      for(let i=0;i<particles.length;i++){
        const p = particles[i];
        const gx = Math.floor(p.x / gridSize), gy = Math.floor(p.y / gridSize);
        const key = gx+','+gy; if(!grid.has(key)) grid.set(key, []); grid.get(key).push(i);
      }
      ctx.globalAlpha = 0.06; ctx.strokeStyle = '#0f172a';
      for(const [key,cells] of grid.entries()){
        for(const idx of cells){
          const a = particles[idx];
          // check same cell and neighbor cells
          const [gx,gy] = key.split(',').map(Number);
          for(let dx=-1; dx<=1; dx++) for(let dy=-1; dy<=1; dy++){
            const key2 = (gx+dx)+','+(gy+dy);
            const arr = grid.get(key2); if(!arr) continue;
            for(const j of arr){ if(j<=idx) continue; const b = particles[j];
              const dxp = a.x - b.x, dyp = a.y - b.y; const dist2 = dxp*dxp + dyp*dyp;
              if(dist2 < 9000){ ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke(); }
            }
          }
        }
      }
      requestAnimationFrame(step);
    }
    step();
  })();
  </script>
</body>
</html>
'''

TEMPLATE_INDEX = BASE_HTML.replace('{% block content %}{% endblock %}', r'''
{% block content %}
  <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
    <div>
      <h3 style="margin:0">Upcoming & Recent Events</h3>
      <p class="muted" style="margin-top:6px">Create events, view attendees, export lists and manage check-ins.</p>
    </div>
    <div>
      <a class="btn btn-primary" href="/event/new">+ New Event</a>
    </div>
  </div>
  <hr style="margin:14px 0;border:none;border-top:1px solid rgba(15,23,42,0.06)">

  {% if events and events|length > 0 %}
    <div class="grid">
      <div>
        {% for e in events %}
          <div style="margin-bottom:12px;padding:14px;border-radius:12px;background:transparent;box-shadow:none">
            <div style="display:flex;justify-content:space-between;align-items:center">
              <div>
                <h4 style="margin:0">{{ e['title'] }}</h4>
                <div class="muted" style="margin-top:6px">{{ e['date'] or 'Date not set' }} • {{ e['location'] or 'Location not set' }}</div>
              </div>
              <div style="display:flex;gap:8px">
                <a class="btn btn-ghost" href="/event/{{ e['id'] }}">Open</a>
              </div>
            </div>
          </div>
        {% endfor %}
      </div>
      <aside>
        <div style="padding:8px">
          <h4 style="margin:0">Quick Actions</h4>
          <p class="muted" style="margin-top:6px">Useful developer and project notes</p>
          <ul class="muted" style="margin-top:8px">
            <li>Init DB: <code>/init_db</code></li>
            <li>Export attendees: open event and click Export CSV</li>
            <li>Toggle check-in from event page</li>
          </ul>
        </div>
      </aside>
    </div>
  {% else %}
    <div style="padding:24px;text-align:center">
      <h3>No events yet — create one</h3>
      <a class="btn btn-primary" href="/event/new">Create your first event</a>
    </div>
  {% endif %}
{% endblock %}
''')

TEMPLATE_NEW_EVENT = BASE_HTML.replace('{% block content %}{% endblock %}', r'''
{% block content %}
  <h3 style="margin:0 0 6px 0">Create New Event</h3>
  <form method="post" style="margin-top:12px;display:grid;gap:8px">
    <label>Title</label>
    <input name="title" placeholder="e.g. 2026 Batch Reunion" required>
    <label>Date</label>
    <input name="date" placeholder="YYYY-MM-DD" >
    <label>Location</label>
    <input name="location" placeholder="e.g. PCTE Seminar Hall">
    <label>Description</label>
    <textarea name="description" rows="4" placeholder="Short description"></textarea>
    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:8px">
      <a class="btn btn-ghost" href="/">Cancel</a>
      <button class="btn btn-primary" type="submit">Create Event</button>
    </div>
  </form>
{% endblock %}
''')

TEMPLATE_EVENT = BASE_HTML.replace('{% block content %}{% endblock %}', r'''
{% block content %}
  <div style="display:flex;gap:12px;flex-wrap:wrap">
    <div style="flex:1">
      <h3 style="margin:0">{{ event['title'] }}</h3>
      <div class="muted" style="margin-top:6px">{{ event['date'] or 'Date not set' }} • {{ event['location'] or 'Location not set' }}</div>
      <p style="margin-top:12px">{{ event['description'] or 'No description.' }}</p>

      <hr style="margin:12px 0">
      <h4 style="margin:0 0 8px 0">RSVP / Register</h4>
      <form method="post" action="/event/{{ event['id'] }}/rsvp" style="display:grid;gap:8px;margin-top:8px">
        <input name="name" placeholder="Your name" required>
        <input name="email" placeholder="Email (optional)">
        <input name="phone" placeholder="Phone (optional)">
        <select name="status">
          <option>Attending</option>
          <option>Not Attending</option>
          <option>Maybe</option>
        </select>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button class="btn btn-ghost" type="reset">Reset</button>
          <button class="btn btn-primary" type="submit">Register</button>
        </div>
      </form>

      <div style="margin-top:16px;display:flex;gap:8px">
        <a class="btn btn-ghost" href="/">Back</a>
        <a class="btn btn-ghost" href="/export/event/{{ event['id'] }}/csv">Export CSV</a>
      </div>
    </div>

    <aside style="width:360px;max-width:100%">
      <h4 style="margin:0">Attendees</h4>
      {% if attendees and attendees|length > 0 %}
        <ul style="margin-top:8px;list-style:none;padding:0">
          {% for a in attendees %}
            <li class="att-item">
              <div>
                <strong>{{ a['name'] }}</strong>
                <div class="muted" style="margin-top:6px">{{ a['email'] or a['phone'] or 'No contact' }}</div>
              </div>
              <div style="display:flex;align-items:center;gap:8px">
                <div class="muted">{{ a['rsvp_status'] }}</div>
                {% if a['checked_in'] %}
                  <a class="btn btn-ghost" href="/attendee/{{ a['id'] }}/toggle_checkin">Checked-in ✅</a>
                {% else %}
                  <a class="btn btn-primary" href="/attendee/{{ a['id'] }}/toggle_checkin">Check In</a>
                {% endif %}
              </div>
            </li>
          {% endfor %}
        </ul>
      {% else %}
        <div class="muted" style="margin-top:8px">No attendees yet. Share the event link to invite.</div>
      {% endif %}
    </aside>
  </div>
{% endblock %}
''')

# ---------- Run ----------

if __name__ == '__main__':
    # ensure DB exists
    if not os.path.exists(DATABASE):
        with app.app_context():
            init_db()
    # make sure static folder exists (user already uploaded background.jpg)
    if not os.path.isdir('static'):
        os.makedirs('static', exist_ok=True)
    app.run(debug=DEBUG)
