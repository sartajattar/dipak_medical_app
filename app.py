import os
import psycopg2
from psycopg2.extras import RealDictCursor
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'dose_in_secret_key_super_secure'

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect('dose_in.db')
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    if DATABASE_URL:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medicals (
                id SERIAL PRIMARY KEY,
                medical_name TEXT NOT NULL,
                owner_name TEXT NOT NULL,
                phone TEXT UNIQUE NOT NULL,
                location TEXT NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'medical',
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id SERIAL PRIMARY KEY,
                medical_id INTEGER NOT NULL REFERENCES medicals(id),
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                medicine_name TEXT NOT NULL,
                dosage_days INTEGER NOT NULL,
                purchase_date TEXT NOT NULL,
                reminder_date TEXT NOT NULL,
                expiry_date TEXT NOT NULL,
                status TEXT DEFAULT 'Pending'
            );
        ''')
        cursor.execute("SELECT * FROM medicals WHERE phone = '7387260111'")
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO medicals (medical_name, owner_name, phone, location, password, role, status)
                VALUES ('Dipak Medical', 'Dipak', '7387260111', 'Main Branch', 'admin123', 'admin', 'approved');
            ''')
    else:
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
        cursor = conn.cursor()
        if DATABASE_URL:
            cursor.execute("SELECT * FROM medicals WHERE phone = %s", (phone,))
        else:
            cursor.execute("SELECT * FROM medicals WHERE phone = ?", (phone,))
        user = cursor.fetchone()
        conn.close()

        if not user:
            flash('Ha mobile number register nahiye. Krupaya aadhi register kara!', 'danger')
            return render_template('login.html')

        if user['status'] == 'pending':
            flash('Tumche account ajun Deepak Medical (Admin) kadun approve zale nahi. Krupaya vat paha!', 'warning')
            return render_template('login.html')
        elif user['status'] == 'rejected':
            flash('Tumche account Dipak Medical kadun reject kele gele aahe.', 'danger')
            return render_template('login.html')

        if user['password'] != password:
            flash('Tumhi taklela password chukicha aahe.', 'danger')
            return render_template('login.html')

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
        cursor = conn.cursor()
        try:
            if DATABASE_URL:
                cursor.execute('''
                    INSERT INTO medicals (medical_name, owner_name, phone, location, password, role, status)
                    VALUES (%s, %s, %s, %s, %s, 'medical', 'pending')
                ''', (medical_name, owner_name, phone, location, password))
            else:
                cursor.execute('''
                    INSERT INTO medicals (medical_name, owner_name, phone, location, password, role, status)
                    VALUES (?, ?, ?, ?, ?, 'medical', 'pending')
                ''', (medical_name, owner_name, phone, location, password))
            conn.commit()
            flash('Registration yashaswi zale! Dipak Medical approval dilyanantar tumhi login karu shakta.', 'success')
            return redirect(url_for('login'))
        except Exception:
            flash('Ha mobile number aadhich register aahe.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ADMIN PANEL ---
@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        flash('Fakt super admin sathi permission aahe.', 'danger')
        return redirect(url_for('medical_dashboard'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM medicals WHERE role != 'admin' ORDER BY id DESC")
    medicals = cursor.fetchall()
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
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("UPDATE medicals SET status = %s WHERE id = %s", (new_status, med_id))
    else:
        cursor.execute("UPDATE medicals SET status = ? WHERE id = ?", (new_status, med_id))
    conn.commit()
    conn.close()
    flash(f"Medical status '{new_status}' kela gela.", 'info')
    return redirect(url_for('admin_dashboard'))

# --- PATIENT DASHBOARD ---
@app.route('/dashboard')
def medical_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    med_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("SELECT * FROM patients WHERE medical_id = %s ORDER BY id DESC", (med_id,))
    else:
        cursor.execute("SELECT * FROM patients WHERE medical_id = ? ORDER BY id DESC", (med_id,))
    patients = cursor.fetchall()
    conn.close()

    today_str = datetime.now().strftime('%Y-%m-%d')
    total_patients = len(patients)
    due_count = len([p for p in patients if str(p['reminder_date']) <= today_str and p['status'] != 'Sent'])
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
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute('''
            INSERT INTO patients (medical_id, name, phone, medicine_name, dosage_days, purchase_date, reminder_date, expiry_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Pending')
        ''', (med_id, name, phone, medicine_name, dosage_days, purchase_date_str, reminder_date_str, expiry_date_str))
    else:
        cursor.execute('''
            INSERT INTO patients (medical_id, name, phone, medicine_name, dosage_days, purchase_date, reminder_date, expiry_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
        ''', (med_id, name, phone, medicine_name, dosage_days, purchase_date_str, reminder_date_str, expiry_date_str))
    conn.commit()
    conn.close()

    flash('Navin patient nondavla gela!', 'success')
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
    cursor = conn.cursor()
    if DATABASE_URL:
        if medicine_name:
            cursor.execute('''
                UPDATE patients 
                SET medicine_name = %s, dosage_days = %s, purchase_date = %s, reminder_date = %s, expiry_date = %s, status = 'Pending'
                WHERE id = %s AND medical_id = %s
            ''', (medicine_name, dosage_days, purchase_date_str, reminder_date_str, expiry_date_str, patient_id, session['user_id']))
        else:
            cursor.execute('''
                UPDATE patients 
                SET dosage_days = %s, purchase_date = %s, reminder_date = %s, expiry_date = %s, status = 'Pending'
                WHERE id = %s AND medical_id = %s
            ''', (dosage_days, purchase_date_str, reminder_date_str, expiry_date_str, patient_id, session['user_id']))
    else:
        if medicine_name:
            cursor.execute('''
                UPDATE patients 
                SET medicine_name = ?, dosage_days = ?, purchase_date = ?, reminder_date = ?, expiry_date = ?, status = 'Pending'
                WHERE id = ? AND medical_id = ?
            ''', (medicine_name, dosage_days, purchase_date_str, reminder_date_str, expiry_date_str, patient_id, session['user_id']))
        else:
            cursor.execute('''
                UPDATE patients 
                SET dosage_days = ?, purchase_date = ?, reminder_date = ?, expiry_date = ?, status = 'Pending'
                WHERE id = ? AND medical_id = ?
            ''', (dosage_days, purchase_date_str, reminder_date_str, expiry_date_str, patient_id, session['user_id']))

    conn.commit()
    conn.close()

    flash('Dose parat refill kela gela aani navin reminder set zale!', 'success')
    return redirect(url_for('medical_dashboard'))

@app.route('/mark_sent/<int:patient_id>')
def mark_sent(patient_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("UPDATE patients SET status = %s WHERE id = %s AND medical_id = %s", (patient_id, session['user_id']))
    else:
        cursor.execute("UPDATE patients SET status = ? WHERE id = ?", (patient_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('medical_dashboard'))

@app.route('/delete_patient/<int:patient_id>')
def delete_patient(patient_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("DELETE FROM patients WHERE id = %s AND medical_id = %s", (patient_id, session['user_id']))
    else:
        cursor.execute("DELETE FROM patients WHERE id = ? AND medical_id = ?", (patient_id, session['user_id']))
    conn.commit()
    conn.close()
    flash('Record delete kele.', 'info')
    return redirect(url_for('medical_dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)