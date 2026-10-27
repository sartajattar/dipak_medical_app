from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'dose_in_secret_key_super_secure'

DB_FILE = 'dose_in.db'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Medicals (Users & Super Admin) Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medicals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medical_name TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            location TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'medical',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Patients Table (linked to medical_id)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medical_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            medicine_name TEXT NOT NULL,
            dosage_days INTEGER NOT NULL,
            purchase_date TEXT NOT NULL,
            reminder_date TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (medical_id) REFERENCES medicals (id)
        )
    ''')

    # Default Super Admin for Dipak Medical
    cursor.execute("SELECT * FROM medicals WHERE phone = '7387260111'")
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO medicals (medical_name, owner_name, phone, location, password, role, status)
            VALUES ('Dipak Medical', 'Dipak', '7387260111', 'Main Branch', 'admin123', 'admin', 'approved')
        ''')

    conn.commit()
    conn.close()

init_db()

# --- AUTH ROUTES ---
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('medical_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone'].strip()
        password = request.form['password'].strip()

        conn = get_db()
        user = conn.execute("SELECT * FROM medicals WHERE phone = ?", (phone,)).fetchone()
        conn.close()

        # 1. मोबाईल नंबर नोंदणीकृत नसेल तर:
        if not user:
            flash('हा मोबाईल नंबर नोंदणीकृत नाही. कृपया आधी नोंदणी करा!', 'danger')
            return render_template('login.html')

        # 2. अप्रूव्हल पेंडिंग किंवा रिजेक्ट असेल तर थेट मेसेज:
        if user['status'] == 'pending':
            flash('तुमचे अकाउंट अजून दीपक मेडिकल (Admin) कडून अप्रूव्ह झालेले नाही. कृपया वाट पहा!', 'warning')
            return render_template('login.html')
        elif user['status'] == 'rejected':
            flash('तुमचे अकाउंट दीपक मेडिकलकडून नाकारण्यात (Reject) आले आहे.', 'danger')
            return render_template('login.html')

        # 3. पासवर्ड चुकीचा असेल तर:
        if user['password'] != password:
            flash('तुम्ही टाकलेला पासवर्ड चुकीचा आहे.', 'danger')
            return render_template('login.html')

        # 4. सर्व माहिती बरोबर असल्यास लॉगिन:
        session['user_id'] = user['id']
        session['medical_name'] = user['medical_name']
        session['role'] = user['role']

        return redirect(url_for('medical_dashboard'))

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        medical_name = request.form['medical_name'].strip()
        owner_name = request.form['owner_name'].strip()
        phone = request.form['phone'].strip()
        location = request.form['location'].strip()
        password = request.form['password'].strip()

        conn = get_db()
        try:
            conn.execute('''
                INSERT INTO medicals (medical_name, owner_name, phone, location, password, role, status)
                VALUES (?, ?, ?, ?, ?, 'medical', 'pending')
            ''', (medical_name, owner_name, phone, location, password))
            conn.commit()
            flash('नोंदणी यशस्वी झाली! दीपक मेडिकलने अप्रूव्ह केल्यानंतर तुम्हाला लॉगिन करता येईल.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('हा मोबाईल नंबर आधीच नोंदणीकृत आहे.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- SUPER ADMIN (दीपक मेडिकल अप्रूव्हल पॅनेल) ---
@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        flash('फक्त मुख्य ॲडमिनसाठी परवानगी आहे.', 'danger')
        return redirect(url_for('medical_dashboard'))

    conn = get_db()
    medicals = conn.execute("SELECT * FROM medicals WHERE role != 'admin' ORDER BY id DESC").fetchall()
    total_medicals = len(medicals)
    pending_count = len([m for m in medicals if m['status'] == 'pending'])
    conn.close()

    return render_template('admin.html', medicals=medicals, total_medicals=total_medicals, pending_count=pending_count)

@app.route('/admin/action/<int:med_id>/<action>')
def medical_action(med_id, action):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    new_status = 'approved' if action == 'approve' else 'rejected'
    conn = get_db()
    conn.execute("UPDATE medicals SET status = ? WHERE id = ?", (new_status, med_id))
    conn.commit()
    conn.close()
    flash(f"मेडिकल स्टेटस '{new_status}' करण्यात आले.", 'info')
    return redirect(url_for('admin_dashboard'))

# --- PATIENT TRACKER, REMINDER & REFILL DASHBOARD ---
@app.route('/dashboard')
def medical_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    med_id = session['user_id']
    conn = get_db()
    patients = conn.execute("SELECT * FROM patients WHERE medical_id = ? ORDER BY id DESC", (med_id,)).fetchall()
    conn.close()

    today_str = datetime.now().strftime('%Y-%m-%d')
    total_patients = len(patients)
    due_count = len([p for p in patients if p['reminder_date'] <= today_str and p['status'] != 'Sent'])
    sent_count = len([p for p in patients if p['status'] == 'Sent'])

    return render_template('dashboard.html', 
                           patients=patients, 
                           today_date=today_str,
                           total_patients=total_patients,
                           due_count=due_count,
                           sent_count=sent_count,
                           medical_name=session.get('medical_name'),
                           is_admin=(session.get('role') == 'admin'))

@app.route('/add_patient', methods=['POST'])
def add_patient():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    med_id = session['user_id']
    name = request.form['name'].strip()
    phone = request.form['phone'].strip()
    medicine_name = request.form['medicine_name'].strip()
    dosage_days = int(request.form['dosage_days'])
    purchase_date_str = request.form.get('purchase_date') or datetime.now().strftime('%Y-%m-%d')

    p_date = datetime.strptime(purchase_date_str, '%Y-%m-%d')
    rem_days = max(1, dosage_days - 2)
    reminder_date_str = (p_date + timedelta(days=rem_days)).strftime('%Y-%m-%d')
    expiry_date_str = (p_date + timedelta(days=dosage_days)).strftime('%Y-%m-%d')

    conn = get_db()
    conn.execute('''
        INSERT INTO patients (medical_id, name, phone, medicine_name, dosage_days, purchase_date, reminder_date, expiry_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
    ''', (med_id, name, phone, medicine_name, dosage_days, purchase_date_str, reminder_date_str, expiry_date_str))
    conn.commit()
    conn.close()

    flash('नवीन पेशंट यशस्वीरीत्या जोडला गेला!', 'success')
    return redirect(url_for('medical_dashboard'))

@app.route('/repeat_refill/<int:patient_id>', methods=['POST'])
def repeat_refill(patient_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    dosage_days = int(request.form['dosage_days'])
    medicine_name = request.form.get('medicine_name', '').strip()
    purchase_date_str = request.form.get('purchase_date') or datetime.now().strftime('%Y-%m-%d')

    p_date = datetime.strptime(purchase_date_str, '%Y-%m-%d')
    rem_days = max(1, dosage_days - 2)
    reminder_date_str = (p_date + timedelta(days=rem_days)).strftime('%Y-%m-%d')
    expiry_date_str = (p_date + timedelta(days=dosage_days)).strftime('%Y-%m-%d')

    conn = get_db()
    if medicine_name:
        conn.execute('''
            UPDATE patients 
            SET medicine_name = ?, dosage_days = ?, purchase_date = ?, reminder_date = ?, expiry_date = ?, status = 'Pending'
            WHERE id = ? AND medical_id = ?
        ''', (medicine_name, dosage_days, purchase_date_str, reminder_date_str, expiry_date_str, patient_id, session['user_id']))
    else:
        conn.execute('''
            UPDATE patients 
            SET dosage_days = ?, purchase_date = ?, reminder_date = ?, expiry_date = ?, status = 'Pending'
            WHERE id = ? AND medical_id = ?
        ''', (dosage_days, purchase_date_str, reminder_date_str, expiry_date_str, patient_id, session['user_id']))
    
    conn.commit()
    conn.close()

    flash('डोस पुन्हा रिफिल केला गेला आणि नवीन रिमाइंडर सेट झाले!', 'success')
    return redirect(url_for('medical_dashboard'))

@app.route('/mark_sent/<int:patient_id>')
def mark_sent(patient_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    conn.execute("UPDATE patients SET status = 'Sent' WHERE id = ? AND medical_id = ?", (patient_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('medical_dashboard'))

@app.route('/delete_patient/<int:patient_id>')
def delete_patient(patient_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    conn.execute("DELETE FROM patients WHERE id = ? AND medical_id = ?", (patient_id, session['user_id']))
    conn.commit()
    conn.close()
    flash('रेकॉर्ड काढून टाकले.', 'info')
    return redirect(url_for('medical_dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)