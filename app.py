from flask import Flask, render_template, request, redirect, session, jsonify, flash
import sqlite3, hashlib, json, random
from datetime import datetime

app = Flask(__name__)
app.secret_key = "agri_secure_2024"
DB = "agriculture.db"

# ─── DB HELPERS ───────────────────────────────────────────────
def get_db():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db

def query(sql, params=()):
    db = get_db()
    rows = [dict(r) for r in db.execute(sql, params).fetchall()]
    db.close()
    # Convert date strings → datetime objects so templates can use .strftime()
    for row in rows:
        for key in ('created_at', 'last_login', 'recorded_on'):
            if key in row and row[key] and isinstance(row[key], str):
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
                    try:
                        row[key] = datetime.strptime(row[key], fmt)
                        break
                    except ValueError:
                        pass
    return rows

def execute(sql, params=()):
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    last_id = cur.lastrowid
    db.close()
    return last_id

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def role_required(role):
    return session.get('role') == role

# ─── INIT DB ──────────────────────────────────────────────────
def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT DEFAULT 'farmer',
        phone TEXT,
        email TEXT,
        is_active INTEGER DEFAULT 1,
        last_login TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS farmers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        village TEXT,
        district TEXT,
        land_acres REAL DEFAULT 0,
        crop_type TEXT,
        aadhaar TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS crops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        crop_name TEXT NOT NULL,
        variety TEXT,
        price_per_kg REAL NOT NULL,
        market_name TEXT,
        district TEXT,
        season TEXT DEFAULT 'Kharif',
        moisture_pct REAL DEFAULT 0,
        quality_grade TEXT DEFAULT 'A',
        added_by INTEGER,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS price_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        crop_name TEXT,
        market_name TEXT,
        alert_type TEXT DEFAULT 'Advisory',
        message TEXT,
        severity TEXT DEFAULT 'Medium',
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        farmer_id INTEGER,
        message TEXT,
        sent_by INTEGER,
        sent_by_name TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    """)

    existing = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not existing:
        db.executescript(f"""
        INSERT INTO users (username,password,full_name,role,phone,email) VALUES
          ('admin',   '{hash_pw("admin123")}',   'System Administrator','admin',  '9000000001','admin@agri.gov.in'),
          ('officer1','{hash_pw("officer123")}', 'Rajan Kumar',         'officer','9000000002','rajan@agri.gov.in'),
          ('officer2','{hash_pw("officer123")}', 'Priya Devi',          'officer','9000000003','priya@agri.gov.in');

        INSERT INTO farmers (name,phone,village,district,land_acres,crop_type,aadhaar) VALUES
          ('Murugan Selvam','9876543210','Palayam',    'Coimbatore',  3.5,'Paddy',    '1234-5678-9012'),
          ('Ravi Krishnan', '9876543211','Kolathur',   'Thanjavur',   5.0,'Sugarcane','2345-6789-0123'),
          ('Anbalagan P',   '9876543212','Vadapalani', 'Salem',       2.0,'Banana',   '3456-7890-1234'),
          ('Kamalam Devi',  '9876543213','Sirkazhi',   'Nagapattinam',4.5,'Cotton',   '4567-8901-2345'),
          ('Suresh Babu',   '9876543214','Palani',     'Dindigul',    6.0,'Turmeric', '5678-9012-3456');

        INSERT INTO users (username,password,full_name,role,phone) VALUES
          ('9876543210','{hash_pw("3210")}','Murugan Selvam','farmer','9876543210'),
          ('9876543211','{hash_pw("3211")}','Ravi Krishnan', 'farmer','9876543211'),
          ('9876543212','{hash_pw("3212")}','Anbalagan P',   'farmer','9876543212');

        INSERT INTO crops (crop_name,variety,price_per_kg,market_name,district,season,quality_grade,added_by) VALUES
          ('Paddy',    'IR-36',       22.50,'Coimbatore APMC',    'Coimbatore',  'Kharif',    'A',1),
          ('Paddy',    'BPT-5204',    25.00,'Thanjavur Market',   'Thanjavur',   'Rabi',      'A',1),
          ('Sugarcane','Co-86032',     3.20,'Erode Sugar Mill',   'Erode',       'All Season','A',1),
          ('Banana',   'Nendran',     35.00,'Coimbatore Market',  'Coimbatore',  'All Season','A',1),
          ('Cotton',   'MCU-5',       65.00,'Rajapalayam Market', 'Virudhunagar','Kharif',    'B',1),
          ('Turmeric', 'Erode Local', 120.00,'Erode Turmeric Mkt','Erode',       'Rabi',      'A',1),
          ('Tomato',   'Hybrid',      18.00,'Koyambedu Market',   'Chennai',     'Summer',    'B',1),
          ('Onion',    'Bellary',     25.00,'Perambalur Market',  'Perambalur',  'Rabi',      'A',1),
          ('Groundnut','TMV-2',       55.00,'Tirunelveli Market', 'Tirunelveli', 'Kharif',    'A',1),
          ('Maize',    'DHM-117',     19.50,'Dharmapuri Market',  'Dharmapuri',  'Kharif',    'A',1);

        INSERT INTO price_alerts (crop_name,market_name,alert_type,message,severity) VALUES
          ('Turmeric','Erode Market','Rise',   'Turmeric price surged 15% due to export demand. Good time to sell!','High'),
          ('Tomato',  'Koyambedu',  'Fall',   'Tomato price dropped. Delay selling if possible for 2 weeks.',      'High'),
          ('Paddy',   'FCI Centers','Advisory','Paddy procurement window open. Register at nearest FCI center.',    'Medium');
        """)
    db.commit()
    db.close()

# ─── AUTH ─────────────────────────────────────────────────────
@app.route('/')
def index():
    return redirect('/login')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username'].strip()
        pwd   = hash_pw(request.form['password'])
        rows  = query("SELECT * FROM users WHERE username=? AND password=? AND is_active=1", (uname, pwd))
        if rows:
            u = rows[0]
            session.update({'user_id':u['id'],'username':u['username'],
                            'role':u['role'],'fullname':u['full_name']})
            execute("UPDATE users SET last_login=datetime('now','localtime') WHERE id=?", (u['id'],))
            return redirect(f"/{u['role']}/dashboard")
        flash('Invalid username or password!', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ─── ADMIN ────────────────────────────────────────────────────
@app.route('/admin/dashboard')
def admin_dashboard():
    if not role_required('admin'): return redirect('/login')
    total_farmers  = query("SELECT COUNT(*) as c FROM farmers")[0]['c']
    total_crops    = query("SELECT COUNT(*) as c FROM crops")[0]['c']
    total_officers = query("SELECT COUNT(*) as c FROM users WHERE role='officer'")[0]['c']
    total_alerts   = query("SELECT COUNT(*) as c FROM price_alerts WHERE is_read=0")[0]['c']
    recent_crops   = query("SELECT * FROM crops ORDER BY id DESC LIMIT 6")
    recent_farmers = query("SELECT * FROM farmers ORDER BY id DESC LIMIT 6")
    chart_data     = query("SELECT strftime('%m',created_at) as month, COUNT(*) as count FROM crops GROUP BY strftime('%m',created_at) ORDER BY month")
    return render_template('admin_dashboard.html',
        total_farmers=total_farmers, total_crops=total_crops,
        total_officers=total_officers, total_alerts=total_alerts,
        recent_crops=recent_crops, recent_farmers=recent_farmers,
        chart_data=json.dumps(chart_data))

@app.route('/admin/farmers')
def admin_farmers():
    if not role_required('admin'): return redirect('/login')
    farmers = query("SELECT * FROM farmers ORDER BY id DESC")
    return render_template('farmers.html', farmers=farmers)

@app.route('/admin/farmers/add', methods=['POST'])
def add_farmer():
    if not role_required('admin'): return redirect('/login')
    f = request.form
    execute("INSERT INTO farmers (name,phone,village,district,land_acres,crop_type,aadhaar) VALUES (?,?,?,?,?,?,?)",
            (f['name'], f['phone'], f.get('village',''), f.get('district',''),
             f.get('land_acres',0), f.get('crop_type',''), f.get('aadhaar','')))
    execute("INSERT OR IGNORE INTO users (username,password,full_name,role,phone) VALUES (?,?,?,'farmer',?)",
            (f['phone'], hash_pw(f['phone'][-4:]), f['name'], f['phone']))
    flash('Farmer registered successfully!', 'success')
    return redirect('/admin/farmers')

@app.route('/admin/farmers/delete/<int:fid>')
def delete_farmer(fid):
    if not role_required('admin'): return redirect('/login')
    execute("DELETE FROM farmers WHERE id=?", (fid,))
    flash('Farmer deleted.', 'info')
    return redirect('/admin/farmers')

@app.route('/admin/crops')
def admin_crops():
    if not role_required('admin'): return redirect('/login')
    crops = query("SELECT * FROM crops ORDER BY id DESC")
    return render_template('crops.html', crops=crops)

@app.route('/admin/crops/add', methods=['POST'])
def add_crop():
    if session.get('role') not in ('admin','officer'): return redirect('/login')
    f = request.form
    execute("INSERT INTO crops (crop_name,variety,price_per_kg,market_name,district,season,moisture_pct,quality_grade,added_by) VALUES (?,?,?,?,?,?,?,?,?)",
            (f['crop_name'], f.get('variety',''), float(f['price_per_kg']),
             f['market_name'], f.get('district',''), f.get('season','Kharif'),
             float(f.get('moisture_pct',0)), f.get('quality_grade','A'), session['user_id']))
    flash('Crop price added successfully!', 'success')
    return redirect('/admin/crops' if session['role']=='admin' else '/officer/dashboard')

@app.route('/admin/crops/delete/<int:cid>')
def delete_crop(cid):
    if not role_required('admin'): return redirect('/login')
    execute("DELETE FROM crops WHERE id=?", (cid,))
    flash('Crop deleted.', 'info')
    return redirect('/admin/crops')

@app.route('/admin/users')
def admin_users():
    if not role_required('admin'): return redirect('/login')
    users = query("SELECT * FROM users ORDER BY role, id DESC")
    return render_template('users.html', users=users)

@app.route('/admin/users/add', methods=['POST'])
def add_user():
    if not role_required('admin'): return redirect('/login')
    f = request.form
    execute("INSERT OR IGNORE INTO users (username,password,full_name,role,phone,email) VALUES (?,?,?,?,?,?)",
            (f['username'], hash_pw(f['password']), f['full_name'],
             f['role'], f.get('phone',''), f.get('email','')))
    flash('User created successfully!', 'success')
    return redirect('/admin/users')

@app.route('/admin/alerts')
def admin_alerts():
    if not role_required('admin'): return redirect('/login')
    alerts = query("SELECT * FROM price_alerts ORDER BY id DESC")
    return render_template('alerts.html', alerts=alerts)

@app.route('/admin/alerts/add', methods=['POST'])
def add_alert():
    if not role_required('admin'): return redirect('/login')
    f = request.form
    execute("INSERT INTO price_alerts (crop_name,market_name,alert_type,message,severity) VALUES (?,?,?,?,?)",
            (f.get('crop_name',''), f.get('market_name',''),
             f.get('alert_type','Advisory'), f['message'], f.get('severity','Medium')))
    flash('Alert created successfully!', 'success')
    return redirect('/admin/alerts')

@app.route('/admin/alerts/delete/<int:aid>')
def delete_alert(aid):
    if not role_required('admin'): return redirect('/login')
    execute("DELETE FROM price_alerts WHERE id=?", (aid,))
    flash('Alert deleted.', 'info')
    return redirect('/admin/alerts')

@app.route('/admin/reports')
def admin_reports():
    if not role_required('admin'): return redirect('/login')
    district_data   = query("SELECT district, ROUND(AVG(price_per_kg),2) as avg_price, COUNT(*) as count FROM crops WHERE district!='' GROUP BY district")
    season_data     = query("SELECT season, COUNT(*) as count, ROUND(AVG(price_per_kg),2) as avg_price FROM crops GROUP BY season")
    top_crops       = query("SELECT crop_name, ROUND(MAX(price_per_kg),2) as max_price, ROUND(AVG(price_per_kg),2) as avg_price FROM crops GROUP BY crop_name ORDER BY avg_price DESC LIMIT 10")
    farmer_district = query("SELECT district, COUNT(*) as count, ROUND(SUM(land_acres),2) as total_acres FROM farmers WHERE district!='' GROUP BY district")
    return render_template('reports.html',
        district_data=json.dumps(district_data), season_data=json.dumps(season_data),
        top_crops=top_crops, farmer_district=json.dumps(farmer_district))

@app.route('/admin/notify', methods=['POST'])
def send_notification():
    if not role_required('admin'): return jsonify({'success':False})
    data = request.json
    ids  = data.get('farmer_ids', [])
    msg  = data.get('message','')
    for fid in ids:
        execute("INSERT INTO notifications (farmer_id,message,sent_by,sent_by_name) VALUES (?,?,?,?)",
                (fid, msg, session['user_id'], session['fullname']))
    return jsonify({'success':True, 'count':len(ids)})

# ─── OFFICER ──────────────────────────────────────────────────
@app.route('/officer/dashboard')
def officer_dashboard():
    if not role_required('officer'): return redirect('/login')
    crops   = query("SELECT * FROM crops ORDER BY id DESC LIMIT 20")
    farmers = query("SELECT * FROM farmers ORDER BY id DESC LIMIT 20")
    alerts  = query("SELECT * FROM price_alerts WHERE is_read=0 ORDER BY id DESC")
    return render_template('officer_dashboard.html', crops=crops, farmers=farmers, alerts=alerts)

@app.route('/officer/crops/add', methods=['POST'])
def officer_add_crop():
    if not role_required('officer'): return redirect('/login')
    f = request.form
    execute("INSERT INTO crops (crop_name,variety,price_per_kg,market_name,district,season,moisture_pct,quality_grade,added_by) VALUES (?,?,?,?,?,?,?,?,?)",
            (f['crop_name'], f.get('variety',''), float(f['price_per_kg']),
             f['market_name'], f.get('district',''), f.get('season','Kharif'),
             float(f.get('moisture_pct',0)), f.get('quality_grade','A'), session['user_id']))
    flash('Crop price submitted!', 'success')
    return redirect('/officer/dashboard')

# ─── FARMER ───────────────────────────────────────────────────
@app.route('/farmer/dashboard')
def farmer_dashboard():
    if not role_required('farmer'): return redirect('/login')
    crops  = query("SELECT * FROM crops ORDER BY id DESC")
    alerts = query("SELECT * FROM price_alerts WHERE is_read=0 ORDER BY id DESC LIMIT 5")
    # Safe notification query — LEFT JOIN so missing farmers don't crash
    notifs = query("""
        SELECT n.id, n.message, n.created_at, n.is_read,
               COALESCE(u.full_name,'Admin') as sent_by_name
        FROM notifications n
        LEFT JOIN users u ON n.sent_by = u.id
        WHERE n.farmer_id = (
            SELECT id FROM farmers WHERE phone=? LIMIT 1
        )
        ORDER BY n.id DESC LIMIT 10
    """, (session['username'],))
    return render_template('farmer_dashboard.html',
                           crops=crops, alerts=alerts, notifications=notifs)

# ─── APIs ─────────────────────────────────────────────────────
@app.route('/api/predict_price', methods=['POST'])
def predict_price():
    data   = request.json
    crop   = data.get('crop_name','')
    season = data.get('season','Kharif')
    rows   = query("SELECT AVG(price_per_kg) as avg FROM crops WHERE crop_name=?", (crop,))
    avg    = float(rows[0]['avg'] or 25)
    trend  = {'Kharif':1.10,'Rabi':1.05,'Summer':0.95}.get(season, 1.0)
    predicted  = round(avg * trend + random.uniform(-2,2), 2)
    confidence = round(random.uniform(78,95), 1)
    return jsonify({'predicted_price':predicted,'confidence':confidence,
                    'trend':'Rising' if trend>1 else 'Stable',
                    'recommendation':f'{crop} expected ₹{predicted}/kg in {season} season (confidence: {confidence}%)'})

@app.route('/api/weather')
def get_weather():
    district = request.args.get('district','Chennai')
    return jsonify({'district':district,
                    'temperature':round(random.uniform(24,38),1),
                    'humidity':random.randint(55,90),
                    'rainfall':round(random.uniform(0,15),1),
                    'condition':random.choice(['Sunny','Partly Cloudy','Cloudy','Light Rain']),
                    'advisory': random.choice([
                        'Good conditions for sowing. Ensure adequate irrigation.',
                        'Heavy rain expected. Delay harvesting operations.',
                        'Moderate temperature. Suitable for all crop activities.'
                    ])})

@app.route('/api/search_crops')
def search_crops():
    q = request.args.get('q','')
    rows = query("SELECT * FROM crops WHERE crop_name LIKE ? OR market_name LIKE ? OR district LIKE ? ORDER BY id DESC LIMIT 20",
                 (f'%{q}%',f'%{q}%',f'%{q}%'))
    return jsonify(rows)

@app.route('/api/farmers')
def get_farmers():
    return jsonify(query("SELECT id,name,phone,district FROM farmers ORDER BY name"))

if __name__ == '__main__':
    init_db()
    print("\n✅ Agriculture System Ready!")
    print("🌐 http://localhost:5000")
    print("Admin: admin / admin123")
    print("Officer: officer1 / officer123")
    print("Farmer: 9876543210 / 3210\n")
    app.run(debug=True, port=5000)
