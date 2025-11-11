"""
Alumni Meet Planning System — Single-file Flask app
White (iOS-like) theme, mobile responsive, and animated background with GitHub + LinkedIn logos.

Usage:
  1. Save as `alumni_meet.py`
  2. Place your image at `static/background.jpg`
  3. pip install flask
  4. python alumni_meet.py
  5. Open http://127.0.0.1:5000
"""

from flask import Flask, g, render_template_string, request, redirect, url_for, send_from_directory, Response
import sqlite3, os, csv, io
from datetime import datetime

# ---------- CONFIG ----------
DATABASE = "alumni_meet.db"
DEBUG = True
SECRET = "replace_this_secure_secret"
GITHUB_URL = "https://github.com/ZahikAbasDar"
LINKEDIN_URL = "https://www.linkedin.com/in/Zahik-Abas"
FOOTER_TAGLINE = "CSE PCTE Student — Alumni Meet Planning System"

# ---------- FLASK APP ----------
app = Flask(__name__)
app.config.from_object(__name__)

# ---------- DATABASE ----------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
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
    """)
    db.commit()

# ---------- HELPERS ----------
def sanitize_text(s, maxlen=300):
    if not s:
        return ""
    s = str(s).strip()
    return s[:maxlen]

# ---------- ROUTES ----------
@app.route("/")
def index():
    db = get_db()
    events = db.execute("SELECT * FROM events ORDER BY date DESC").fetchall()
    return render_template_string(TEMPLATE_INDEX, events=events, github=GITHUB_URL, linkedin=LINKEDIN_URL, tagline=FOOTER_TAGLINE)

@app.route("/init_db")
def route_init_db():
    init_db()
    return "✅ Database initialized successfully! <a href='/'>Go Home</a>"

@app.route("/event/new", methods=["GET", "POST"])
def new_event():
    if request.method == "POST":
        title = sanitize_text(request.form.get("title", ""))
        if not title:
            return "Title is required", 400
        description = sanitize_text(request.form.get("description", ""), 2000)
        date = sanitize_text(request.form.get("date", ""), 32)
        location = sanitize_text(request.form.get("location", ""), 200)
        db = get_db()
        db.execute(
            "INSERT INTO events (title, description, date, location, created_at) VALUES (?,?,?,?,?)",
            (title, description, date, location, datetime.utcnow().isoformat()),
        )
        db.commit()
        return redirect(url_for("index"))
    return render_template_string(TEMPLATE_NEW_EVENT, github=GITHUB_URL, linkedin=LINKEDIN_URL, tagline=FOOTER_TAGLINE)

@app.route("/event/<int:event_id>")
def view_event(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        return "Event not found", 404
    attendees = db.execute("SELECT * FROM attendees WHERE event_id = ?", (event_id,)).fetchall()
    return render_template_string(TEMPLATE_EVENT, event=event, attendees=attendees, github=GITHUB_URL, linkedin=LINKEDIN_URL, tagline=FOOTER_TAGLINE)

@app.route("/event/<int:event_id>/rsvp", methods=["POST"])
def rsvp(event_id):
    name = sanitize_text(request.form.get("name", ""), 150)
    if not name:
        return "Name required", 400
    email = sanitize_text(request.form.get("email", ""), 200)
    phone = sanitize_text(request.form.get("phone", ""), 40)
    status = sanitize_text(request.form.get("status", "Attending"), 32)
    db = get_db()
    ev = db.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
    if not ev:
        return "Event not found", 404
    db.execute(
        "INSERT INTO attendees (event_id,name,email,phone,rsvp_status,created_at) VALUES (?,?,?,?,?,?)",
        (event_id, name, email, phone, status, datetime.utcnow().isoformat()),
    )
    db.commit()
    return redirect(url_for("view_event", event_id=event_id))

@app.route("/attendee/<int:att_id>/toggle_checkin")
def toggle_checkin(att_id):
    db = get_db()
    row = db.execute("SELECT checked_in, event_id FROM attendees WHERE id = ?", (att_id,)).fetchone()
    if row:
        new = 0 if row["checked_in"] else 1
        db.execute("UPDATE attendees SET checked_in = ? WHERE id = ?", (new, att_id))
        db.commit()
        return redirect(url_for("view_event", event_id=row["event_id"]))
    return "Not found", 404

@app.route("/export/event/<int:event_id>/csv")
def export_event_csv(event_id):
    db = get_db()
    attendees = db.execute("SELECT * FROM attendees WHERE event_id = ?", (event_id,)).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Email", "Phone", "RSVP", "Checked In"])
    for a in attendees:
        writer.writerow([a["name"], a["email"], a["phone"], a["rsvp_status"], int(a["checked_in"])])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename=event_{event_id}_attendees.csv"})

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)

# ---------- FRONTEND (HTML/CSS/JS) ----------
BASE_HTML = r'''
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alumni Meet Planner</title>
<style>
:root {
  --accent1:#0ea5e9;
  --accent2:#7c3aed;
  --radius:14px;
}
* {box-sizing:border-box;}
body {
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial;
  margin:0;
  overflow-x:hidden;
  color:#0a0a0a;
}
.hero {
  position:relative;
  min-height:100vh;
  display:flex;
  flex-direction:column;
  justify-content:center;
  align-items:center;
  text-align:center;
  color:white;
  padding:0 20px;
}
h1 {
  font-size:clamp(28px,7vw,52px);
  font-weight:800;
  color:white;
  text-shadow:0 0 14px rgba(0,0,0,0.7);
}
p.lead {
  font-size:clamp(16px,3vw,22px);
  max-width:600px;
  margin:10px auto;
  color:#e0e6ed;
  text-shadow:0 0 10px rgba(0,0,0,0.6);
}
.btn {
  display:inline-flex;align-items:center;justify-content:center;
  padding:12px 22px;margin:6px;
  border:none;border-radius:999px;font-weight:700;
  transition:transform .2s, box-shadow .2s;
}
.btn-primary {
  background:linear-gradient(180deg,var(--accent1),var(--accent2));
  color:white;box-shadow:0 6px 20px rgba(0,0,0,0.2);
}
.btn:active {transform:scale(0.97);}
.container {padding:24px;max-width:1100px;margin:-60px auto 40px;}
.card {
  background:rgba(255,255,255,0.96);
  border-radius:var(--radius);
  padding:20px;
  box-shadow:0 10px 25px rgba(0,0,0,0.05);
}
footer {
  text-align:center;
  padding:20px;
  font-size:15px;
  color:white;
  text-shadow:0 0 8px rgba(0,0,0,0.6);
}
.bg-image {
  position:fixed;inset:0;
  background:url('/static/background.jpg') center/cover no-repeat;
  z-index:-3;
  filter:brightness(1.05) contrast(1.1);
}
.bg-overlay {
  position:fixed;inset:0;
  background:linear-gradient(180deg,rgba(0,0,0,0.35),rgba(0,0,0,0.85));
  z-index:-2;
}

/* Icons */
.icon {
  width:20px;height:20px;vertical-align:middle;margin-right:6px;
  filter:brightness(100);
}

/* Responsive */
@media(max-width:600px){
  .container{padding:12px;margin:-30px auto 24px;}
  .card{padding:14px;}
  footer{font-size:13px;}
  h1{font-size:32px;}
  .btn{padding:10px 18px;font-size:15px;}
}
</style>
</head>
<body>
<div class="bg-image"></div>
<div class="bg-overlay"></div>

<div class="hero">
  <h1>Alumni Meet Planner</h1>
  <p class="lead">Plan reunions, manage attendees, and make memorable events — elegant, simple, and open.</p>
  <div>
    <a class="btn btn-primary" href="/event/new">Create Event</a>
    <a class="btn btn-primary" href="#footer" style="background:rgba(255,255,255,0.15)">Profiles & Footer</a>
  </div>
</div>

<main class="container">
  <div class="card">{% block content %}{% endblock %}</div>
  <footer id="footer">
    <div>Made by ❤️ <strong>Zahik Abas Dar</strong> — App Developer</div>
    <div style="margin-top:8px">
      <a href="{{ github }}" target="_blank">
        <img class="icon" src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/github/github-original.svg" alt="GitHub Logo">
      </a>
      <a href="{{ linkedin }}" target="_blank">
        <img class="icon" src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linkedin/linkedin-original.svg" alt="LinkedIn Logo">
      </a>
    </div>
  </footer>
</main>

<script>
// Animated particle background
(function(){
  const c=document.createElement('canvas');document.body.appendChild(c);
  Object.assign(c.style,{position:'fixed',inset:0,zIndex:-1,pointerEvents:'none'});
  const ctx=c.getContext('2d');
  function resize(){const dpr=window.devicePixelRatio||1;c.width=innerWidth*dpr;c.height=innerHeight*dpr;c.style.width=innerWidth+'px';c.style.height=innerHeight+'px';ctx.scale(dpr,dpr);}
  window.addEventListener('resize',resize);resize();
  const ps=[];for(let i=0;i<120;i++)ps.push({x:Math.random()*innerWidth,y:Math.random()*innerHeight,vx:(Math.random()-0.5)*0.3,vy:(Math.random()-0.5)*0.3,r:1+Math.random()*1.3});
  function draw(){
    ctx.clearRect(0,0,innerWidth,innerHeight);
    for(const p of ps){
      p.x+=p.vx;p.y+=p.vy;
      if(p.x<0||p.x>innerWidth)p.vx*=-1;
      if(p.y<0||p.y>innerHeight)p.vy*=-1;
      ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
      ctx.fillStyle='rgba(255,255,255,0.7)';ctx.fill();
    }
    ctx.globalAlpha=0.06;ctx.strokeStyle='white';
    for(let i=0;i<ps.length;i++){for(let j=i+1;j<ps.length;j++){const a=ps[i],b=ps[j],dx=a.x-b.x,dy=a.y-b.y;if(dx*dx+dy*dy<13000){ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();}}}
    ctx.globalAlpha=1;
    requestAnimationFrame(draw);
  }
  draw();
})();
</script>
</body>
</html>
'''

# ---------- CONTENT PAGES ----------
TEMPLATE_INDEX = BASE_HTML.replace('{% block content %}{% endblock %}', r'''
{% block content %}
<h3>Upcoming & Recent Events</h3>
{% if events %}
  {% for e in events %}
  <div style="margin-bottom:12px;padding:14px;border-radius:12px;background:rgba(255,255,255,0.7)">
    <h4>{{ e['title'] }}</h4>
    <p>{{ e['date'] or 'Date not set' }} • {{ e['location'] or 'Location not set' }}</p>
    <a class="btn btn-primary" href="/event/{{ e['id'] }}">Open</a>
  </div>
  {% endfor %}
{% else %}
  <div style="text-align:center;padding:24px">
    <h4>No events yet</h4>
    <a class="btn btn-primary" href="/event/new">Create your first event</a>
  </div>
{% endif %}
{% endblock %}
''')

TEMPLATE_NEW_EVENT = BASE_HTML.replace('{% block content %}{% endblock %}', r'''
{% block content %}
<h3>Create New Event</h3>
<form method="post" style="margin-top:12px;display:grid;gap:8px">
  <input name="title" placeholder="Event title" required>
  <input name="date" placeholder="YYYY-MM-DD">
  <input name="location" placeholder="Location">
  <textarea name="description" rows="3" placeholder="Description"></textarea>
  <div style="display:flex;justify-content:flex-end;gap:10px">
    <a class="btn btn-primary" href="/">Cancel</a>
    <button class="btn btn-primary">Create</button>
  </div>
</form>
{% endblock %}
''')

TEMPLATE_EVENT = BASE_HTML.replace('{% block content %}{% endblock %}', r'''
{% block content %}
<h3>{{ event['title'] }}</h3>
<p>{{ event['date'] or '' }} • {{ event['location'] or '' }}</p>
<p>{{ event['description'] or 'No description.' }}</p>
<hr>
<form method="post" action="/event/{{ event['id'] }}/rsvp" style="display:grid;gap:8px">
  <input name="name" placeholder="Your name" required>
  <input name="email" placeholder="Email (optional)">
  <input name="phone" placeholder="Phone (optional)">
  <select name="status"><option>Attending</option><option>Not Attending</option><option>Maybe</option></select>
  <button class="btn btn-primary">Register</button>
</form>
<hr>
<h4>Attendees</h4>
{% if attendees %}
  {% for a in attendees %}
  <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid rgba(0,0,0,0.1)">
    <div><b>{{ a['name'] }}</b><br><small>{{ a['email'] or a['phone'] }}</small></div>
    {% if a['checked_in'] %}
      <a class="btn btn-primary" href="/attendee/{{ a['id'] }}/toggle_checkin">✅ Checked</a>
    {% else %}
      <a class="btn btn-primary" href="/attendee/{{ a['id'] }}/toggle_checkin">Check In</a>
    {% endif %}
  </div>
  {% endfor %}
{% else %}
<p>No attendees yet.</p>
{% endif %}
{% endblock %}
''')

# ---------- RUN ----------
if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        with app.app_context():
            init_db()
    os.makedirs("static", exist_ok=True)
    app.run(debug=DEBUG)
