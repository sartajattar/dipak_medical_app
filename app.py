from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "dipak_medical_secret_key"
DB_NAME = "dipak_medical.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            medicine_name TEXT NOT NULL,
            dosage_days INTEGER NOT NULL,
            purchase_date TEXT NOT NULL,
            reminder_date TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            status TEXT DEFAULT 'Pending'
        )
    ''')
    cursor.execute("SELECT COUNT(*) FROM patients")
    if cursor.fetchone()[0] == 0:
        today = datetime.now()
        p1_purchase = (today - timedelta(days=13)).strftime("%Y-%m-%d")
        p1_reminder = today.strftime("%Y-%m-%d")
        p1_expiry = (today + timedelta(days=2)).strftime("%Y-%m-%d")

        p2_purchase = (today - timedelta(days=2)).strftime("%Y-%m-%d")
        p2_reminder = (today + timedelta(days=13)).strftime("%Y-%m-%d")
        p2_expiry = (today + timedelta(days=15)).strftime("%Y-%m-%d")

        cursor.executemany('''
            INSERT INTO patients (name, phone, medicine_name, dosage_days, purchase_date, reminder_date, expiry_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            ("Rahul Sharma", "9876543210", "Metformin 500mg", 15, p1_purchase, p1_reminder, p1_expiry, "Pending"),
            ("Amit Patil", "9822012345", "Telmisartan 40mg", 15, p2_purchase, p2_reminder, p2_expiry, "Pending"),
            ("Suresh Jadhav", "9123456780", "Thyronorm 50mcg", 30, p1_purchase, (today + timedelta(days=15)).strftime("%Y-%m-%d"), (today + timedelta(days=17)).strftime("%Y-%m-%d"), "Sent")
        ])
    conn.commit()
    conn.close()

@app.route('/')
def index():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("SELECT * FROM patients ORDER BY id DESC")
    patients = cursor.fetchall()

    total_patients = len(patients)
    due_today = [p for p in patients if p['reminder_date'] <= today_str and p['status'] != 'Sent']
    sent_count = len([p for p in patients if p['status'] == 'Sent'])

    conn.close()
    return render_template(
        'index.html',
        patients=patients,
        total_patients=total_patients,
        due_count=len(due_today),
        sent_count=sent_count,
        today_date=today_str
    )

@app.route('/add_patient', methods=['POST'])
def add_patient():
    name = request.form.get('name')
    phone = request.form.get('phone')
    medicine_name = request.form.get('medicine_name')
    dosage_days = int(request.form.get('dosage_days', 15))
    purchase_date_str = request.form.get('purchase_date')

    if not purchase_date_str:
        purchase_date = datetime.now()
    else:
        purchase_date = datetime.strptime(purchase_date_str, "%Y-%m-%d")

    offset = 2 if dosage_days >= 5 else 1
    reminder_days = max(1, dosage_days - offset)

    reminder_date = purchase_date + timedelta(days=reminder_days)
    expiry_date = purchase_date + timedelta(days=dosage_days)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO patients (name, phone, medicine_name, dosage_days, purchase_date, reminder_date, expiry_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending')
    ''', (name, phone, medicine_name, dosage_days, purchase_date.strftime("%Y-%m-%d"), reminder_date.strftime("%Y-%m-%d"), expiry_date.strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    flash("Patient added successfully!", "success")
    return redirect(url_for('index'))

@app.route('/mark_sent/<int:patient_id>')
def mark_sent(patient_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE patients SET status = 'Sent' WHERE id = ?", (patient_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete_patient/<int:patient_id>')
def delete_patient(patient_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
    conn.commit()
    conn.close()
    flash("Record deleted.", "danger")
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)