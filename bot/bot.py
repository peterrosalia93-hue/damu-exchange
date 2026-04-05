# DamuExchange - Blood Donation Bot + Web
# With polling + web interface

import os
import sqlite3
import requests
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ============================================
# CONFIG
# ============================================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""

BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

# Polling
LAST_UPDATE_ID = 0

# ============================================
# DATABASE
# ============================================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "damu.db")

def get_db():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""CREATE TABLE IF NOT EXISTS donors (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        name TEXT,
        phone TEXT,
        blood_type TEXT,
        location TEXT,
        available INTEGER DEFAULT 1,
        created_at TEXT
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        patient_name TEXT,
        blood_type TEXT,
        hospital TEXT,
        units INTEGER DEFAULT 1,
        urgency TEXT,
        doctor_phone TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )""")
    
    conn.commit()
    conn.close()

init_db()

# ============================================
# TELEGRAM
# ============================================
def send_message(chat_id, text, parse_mode="Markdown", reply_markup=None):
    if not API_URL:
        print(f"[DamuExchange] {text}")
        return
    url = f"{API_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        data["reply_markup"] = reply_markup
    try:
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        print(f"Error: {e}")

def main_menu_keyboard():
    return {
        "keyboard": [
            [{"text": "Register as Donor"}, {"text": "I Need Blood"}],
            [{"text": "Find Donor"}, {"text": "My Requests"}],
            [{"text": "Help"}],
        ],
        "resize_keyboard": True
    }

def blood_type_keyboard():
    return {
        "keyboard": [[{"text": t}] for t in BLOOD_TYPES] + [[{"text": "Cancel"}]],
        "resize_keyboard": True
    }

# ============================================
# STATE
# ============================================
user_state = {}

def set_state(chat_id, step, data=None):
    user_state[chat_id] = {"step": step, "data": data or {}}

def get_state(chat_id):
    return user_state.get(chat_id, {"step": None, "data": {}})

def clear_state(chat_id):
    user_state.pop(chat_id, None)

# ============================================
# HANDLERS
# ============================================
def handle_register(chat_id, name, phone, blood_type, location):
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO donors 
        (user_id, name, phone, blood_type, location, available, created_at)
        VALUES (?, ?, ?, ?, ?, 1, ?)""",
        (chat_id, name, phone, blood_type, location, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    send_message(chat_id, f"[OK] Registered!\n\nName: {name}\nBlood: {blood_type}\nLocation: {location}")

def handle_request_blood(chat_id, patient_name, blood_type, hospital, units, urgency, doctor_phone):
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO requests 
        (user_id, patient_name, blood_type, hospital, units, urgency, doctor_phone, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
        (chat_id, patient_name, blood_type, hospital, units, urgency, doctor_phone, datetime.now().isoformat()))
    request_id = c.lastrowid
    conn.commit()
    
    c.execute("""SELECT user_id, name, location FROM donors 
        WHERE blood_type = ? AND available = 1""", (blood_type,))
    donors = c.fetchall()
    conn.close()
    
    for donor in donors:
        donor_id, name, loc = donor
        send_message(donor_id, f"[NEEDED] {blood_type} needed at {hospital}")
    
    send_message(chat_id, f"[OK] Request #{request_id} created!")

def handle_find_donor(chat_id, blood_type):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT name, location, phone FROM donors 
        WHERE blood_type = ? AND available = 1""", (blood_type,))
    donors = c.fetchall()
    conn.close()
    
    if donors:
        text = f"[FOUND] {blood_type} donors:\n\n"
        for name, location, phone in donors:
            text += f"- {name} ({location}) - {phone}\n"
    else:
        text = f"[EMPTY] No {blood_type} donors available."
    send_message(chat_id, text)

def handle_my_requests(chat_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT id, patient_name, blood_type, status FROM requests 
        WHERE user_id = ? ORDER BY id DESC LIMIT 5""", (chat_id,))
    reqs = c.fetchall()
    conn.close()
    
    if reqs:
        text = "[REQUESTS]\n\n"
        for rid, patient, blood, status in reqs:
            text += f"#{rid} {patient} - {blood} ({status})\n"
    else:
        text = "[NONE] No requests."
    send_message(chat_id, text)

# ============================================
# PROCESS MESSAGES
# ============================================
def process_message(chat_id, text):
    state = get_state(chat_id)
    
    if state["step"] == "register_name":
        set_state(chat_id, "register_phone", {"name": text})
        send_message(chat_id, "Phone number:")
        
    elif state["step"] == "register_phone":
        data = state["data"]
        data["phone"] = text
        set_state(chat_id, "register_blood", data)
        send_message(chat_id, "Blood type:", reply_markup=blood_type_keyboard())
        
    elif state["step"] == "register_blood":
        if text in BLOOD_TYPES:
            data = state["data"]
            data["blood_type"] = text
            set_state(chat_id, "register_location", data)
            send_message(chat_id, "Location:")
        
    elif state["step"] == "register_location":
        data = state["data"]
        handle_register(chat_id, data["name"], data["phone"], data["blood_type"], text)
        clear_state(chat_id)
    
    elif state["step"] == "request_patient":
        set_state(chat_id, "request_hospital", {"patient_name": text})
        send_message(chat_id, "Hospital:")
        
    elif state["step"] == "request_hospital":
        data = state["data"]
        data["hospital"] = text
        set_state(chat_id, "request_blood", data)
        send_message(chat_id, "Blood type needed:", reply_markup=blood_type_keyboard())
        
    elif state["step"] == "request_blood":
        if text in BLOOD_TYPES:
            data = state["data"]
            data["blood_type"] = text
            set_state(chat_id, "request_units", data)
            send_message(chat_id, "Units needed:")
        
    elif state["step"] == "request_units":
        data = state["data"]
        data["units"] = text
        set_state(chat_id, "request_urgency", data)
        send_message(chat_id, "Urgency (routine/urgent/critical):")
        
    elif state["step"] == "request_urgency":
        data = state["data"]
        data["urgency"] = text
        set_state(chat_id, "request_doctor", data)
        send_message(chat_id, "Doctor phone:")
        
    elif state["step"] == "request_doctor":
        data = state["data"]
        handle_request_blood(chat_id, data["patient_name"], data["blood_type"], 
            data["hospital"], data["units"], data["urgency"], text)
        clear_state(chat_id)
    
    elif state["step"] == "find_donor":
        if text in BLOOD_TYPES:
            handle_find_donor(chat_id, text)
            clear_state(chat_id)
    
    elif text == "/start" or text == "Help":
        send_message(chat_id, "[DamuExchange] Blood Donation\n\nChoose:", reply_markup=main_menu_keyboard())
        
    elif text == "Register as Donor":
        set_state(chat_id, "register_name")
        send_message(chat_id, "Enter full name:")
        
    elif text == "I Need Blood":
        set_state(chat_id, "request_patient")
        send_message(chat_id, "Patient name:")
        
    elif text == "Find Donor":
        set_state(chat_id, "find_donor")
        send_message(chat_id, "Blood type:", reply_markup=blood_type_keyboard())
        
    elif text == "My Requests":
        handle_my_requests(chat_id)
        
    else:
        if text != "Cancel":
            send_message(chat_id, "Use menu or /start", reply_markup=main_menu_keyboard())

# ============================================
# POLLING
# ============================================
def poll_updates():
    global LAST_UPDATE_ID
    print("[Polling] DamuExchange started...")
    
    while True:
        try:
            url = f"{API_URL}/getUpdates?timeout=10"
            if LAST_UPDATE_ID > 0:
                url += f"&offset={LAST_UPDATE_ID + 1}"
            
            resp = requests.get(url, timeout=15).json()
            
            if resp.get("ok"):
                updates = resp.get("result", [])
                if updates:
                    print(f"[Polling] Got {len(updates)} updates")
                    
                for update in updates:
                    LAST_UPDATE_ID = update["update_id"]
                    
                    if "message" in update:
                        msg = update["message"]
                        chat_id = msg["chat"]["id"]
                        text = msg.get("text", "")
                        print(f"[Message] {chat_id}: {text}")
                        process_message(chat_id, text)
            
        except Exception as e:
            print(f"[Polling] Error: {e}")
            time.sleep(3)

# ============================================
# WEB ROUTES
# ============================================
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>DamuExchange - Blood Donation</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               background: #e74c3c; min-height: 100vh; padding: 20px; }
        .container { max-width: 500px; margin: 0 auto; }
        h1 { color: white; text-align: center; margin-bottom: 20px; font-size: 28px; }
        h1 span { display: block; font-size: 14px; opacity: 0.8; font-weight: normal; }
        
        .card { background: white; border-radius: 16px; padding: 20px; margin-bottom: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        .card h2 { color: #e74c3c; font-size: 18px; margin-bottom: 15px; display: flex; align-items: center; gap: 8px; }
        
        .stats { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; text-align: center; margin-bottom: 20px; }
        .stat { background: white; padding: 15px; border-radius: 12px; }
        .stat-num { font-size: 24px; font-weight: bold; color: #e74c3c; }
        .stat-label { font-size: 12px; color: #666; }
        
        input, select { width: 100%; padding: 12px; margin-bottom: 10px; border: 2px solid #eee; 
                        border-radius: 8px; font-size: 16px; }
        input:focus, select:focus { outline: none; border-color: #e74c3c; }
        
        button { width: 100%; padding: 14px; background: #e74c3c; color: white; border: none; 
                 border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; }
        button:hover { background: #c0392b; }
        button.secondary { background: #2c3e50; }
        
        .tabs { display: flex; gap: 10px; margin-bottom: 15px; }
        .tab { flex: 1; padding: 10px; background: white; border: none; border-radius: 8px; 
               cursor: pointer; text-align: center; font-weight: bold; }
        .tab.active { background: white; color: #e74c3c; }
        
        .donor-list { list-style: none; }
        .donor-item { padding: 12px; background: #f8f9fa; border-radius: 8px; margin-bottom: 8px; 
                      display: flex; justify-content: space-between; align-items: center; }
        .donor-info { font-weight: bold; }
        .donor-contact { font-size: 14px; color: #666; }
        
        .request-item { padding: 12px; background: #f8f9fa; border-radius: 8px; margin-bottom: 8px; }
        .request-header { display: flex; justify-content: space-between; font-weight: bold; }
        .request-details { font-size: 14px; color: #666; margin-top: 5px; }
        
        .status-pending { color: #f39c12; }
        .status-matched { color: #27ae60; }
        
        .telegram-link { display: block; text-align: center; color: white; margin-top: 20px; 
                        font-size: 14px; opacity: 0.8; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🩸 DamuExchange<span>Kenya Blood Donation Network</span></h1>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-num">{{ donors|length }}</div>
                <div class="stat-label">Donors</div>
            </div>
            <div class="stat">
                <div class="stat-num">{{ requests|length }}</div>
                <div class="stat-label">Requests</div>
            </div>
            <div class="stat">
                <div class="stat-num">{{ matched }}</div>
                <div class="stat-label">Matched</div>
            </div>
        </div>
        
        <div class="card">
            <h2>📋 Actions</h2>
            <div class="tabs">
                <button class="tab active" onclick="showTab('donor')">Donor</button>
                <button class="tab" onclick="showTab('request')">Request</button>
            </div>
            
            <div id="donor-form">
                <input type="text" id="donor-name" placeholder="Full Name">
                <input type="tel" id="donor-phone" placeholder="Phone Number">
                <select id="donor-blood">
                    <option value="">Select Blood Type</option>
                    {% for bt in blood_types %}<option value="{{ bt }}">{{ bt }}</option>{% endfor %}
                </select>
                <input type="text" id="donor-location" placeholder="Location (e.g., Nairobi)">
                <button onclick="registerDonor()">Register as Donor</button>
            </div>
            
            <div id="request-form" style="display:none;">
                <input type="text" id="req-patient" placeholder="Patient Name">
                <select id="req-blood">
                    <option value="">Blood Type Needed</option>
                    {% for bt in blood_types %}<option value="{{ bt }}">{{ bt }}</option>{% endfor %}
                </select>
                <input type="text" id="req-hospital" placeholder="Hospital Name">
                <input type="number" id="req-units" placeholder="Units Needed" value="1">
                <select id="req-urgency">
                    <option value="routine">Routine</option>
                    <option value="urgent">Urgent</option>
                    <option value="critical">Critical</option>
                </select>
                <input type="tel" id="req-phone" placeholder="Doctor's Phone">
                <button onclick="createRequest()">Submit Request</button>
            </div>
        </div>
        
        <div class="card">
            <h2>🩸 Available Donors</h2>
            {% if donors %}
            <ul class="donor-list">
                {% for d in donors %}
                <li class="donor-item">
                    <div>
                        <div class="donor-info">{{ d.name }} - {{ d.blood_type }}</div>
                        <div class="donor-contact">{{ d.location }} | {{ d.phone }}</div>
                    </div>
                </li>
                {% endfor %}
            </ul>
            {% else %}
            <p style="color:#666;text-align:center;">No donors registered yet</p>
            {% endif %}
        </div>
        
        <div class="card">
            <h2>📋 Blood Requests</h2>
            {% if requests %}
            <ul class="donor-list">
                {% for r in requests %}
                <li class="request-item">
                    <div class="request-header">
                        <span>{{ r.patient_name }}</span>
                        <span class="status-{{ r.status }}">{{ r.status }}</span>
                    </div>
                    <div class="request-details">
                        {{ r.blood_type }} | {{ r.hospital }} | {{ r.units }} unit(s)
                    </div>
                </li>
                {% endfor %}
            </ul>
            {% else %}
            <p style="color:#666;text-align:center;">No requests yet</p>
            {% endif %}
        </div>
        
        <a href="https://t.me/Upendo_bot" class="telegram-link">Open in Telegram @Upendo_bot</a>
    </div>
    
    <script>
        function showTab(tab) {
            document.getElementById('donor-form').style.display = tab === 'donor' ? 'block' : 'none';
            document.getElementById('request-form').style.display = tab === 'request' ? 'block' : 'none';
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
        }
        
        async function registerDonor() {
            const data = {
                name: document.getElementById('donor-name').value,
                phone: document.getElementById('donor-phone').value,
                blood_type: document.getElementById('donor-blood').value,
                location: document.getElementById('donor-location').value
            };
            if (!data.name || !data.phone || !data.blood_type || !data.location) {
                alert('Please fill all fields');
                return;
            }
            const res = await fetch('/api/donor', { method: 'POST', 
                headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) });
            if (res.ok) { alert('Registered!'); location.reload(); }
        }
        
        async function createRequest() {
            const data = {
                patient_name: document.getElementById('req-patient').value,
                blood_type: document.getElementById('req-blood').value,
                hospital: document.getElementById('req-hospital').value,
                units: document.getElementById('req-units').value,
                urgency: document.getElementById('req-urgency').value,
                doctor_phone: document.getElementById('req-phone').value
            };
            if (!data.patient_name || !data.blood_type || !data.hospital) {
                alert('Please fill required fields');
                return;
            }
            const res = await fetch('/api/request', { method: 'POST', 
                headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data) });
            if (res.ok) { alert('Request created!'); location.reload(); }
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT name, phone, blood_type, location FROM donors WHERE available = 1")
    donors = c.fetchall()
    
    c.execute("SELECT patient_name, blood_type, hospital, units, status FROM requests ORDER BY id DESC LIMIT 10")
    requests_list = c.fetchall()
    
    c.execute("SELECT COUNT(*) FROM requests WHERE status = 'matched'")
    matched = c.fetchone()[0]
    
    conn.close()
    
    donors_list = [{"name": d[0], "phone": d[1], "blood_type": d[2], "location": d[3]} for d in donors]
    requests_list = [{"patient_name": r[0], "blood_type": r[1], "hospital": r[2], "units": r[3], "status": r[4]} for r in requests_list]
    
    return render_template_string(HTML, donors=donors_list, requests=requests_list, 
                                   matched=matched, blood_types=BLOOD_TYPES)

@app.route("/api/donor", methods=["POST"])
def add_donor():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO donors (user_id, name, phone, blood_type, location, available, created_at)
        VALUES (?, ?, ?, ?, ?, 1, ?)""",
        (0, data["name"], data["phone"], data["blood_type"], data["location"], datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/request", methods=["POST"])
def add_request():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO requests (user_id, patient_name, blood_type, hospital, units, urgency, doctor_phone, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
        (0, data["patient_name"], data["blood_type"], data["hospital"], data["units"], 
         data["urgency"], data["doctor_phone"], datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ============================================
# START
# ============================================
if __name__ == "__main__":
    if BOT_TOKEN and not os.getenv("VERCEL"):
        threading.Thread(target=poll_updates, daemon=True).start()

    port = int(os.getenv("PORT", 5005))
    print(f"DamuExchange Web: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port)