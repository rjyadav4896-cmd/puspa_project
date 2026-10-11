PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS students (
 id INTEGER PRIMARY KEY, student_number TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
 email TEXT NOT NULL, department TEXT NOT NULL, blood_group TEXT NOT NULL DEFAULT 'Unknown',
 allergies TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS doctors (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, specialty TEXT NOT NULL, email TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS appointments (
 id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
 doctor_id INTEGER NOT NULL REFERENCES doctors(id), scheduled_at TEXT NOT NULL,
 reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Scheduled'
 CHECK(status IN ('Scheduled','Completed','Cancelled'))
);
CREATE UNIQUE INDEX IF NOT EXISTS doctor_slot ON appointments(doctor_id,scheduled_at) WHERE status != 'Cancelled';
CREATE UNIQUE INDEX IF NOT EXISTS student_slot ON appointments(student_id,scheduled_at) WHERE status != 'Cancelled';
CREATE TABLE IF NOT EXISTS medicines (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, stock INTEGER NOT NULL CHECK(stock>=0),
 unit TEXT NOT NULL, reorder_level INTEGER NOT NULL DEFAULT 10 CHECK(reorder_level>=0), expiry_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prescriptions (
 id INTEGER PRIMARY KEY, appointment_id INTEGER NOT NULL UNIQUE REFERENCES appointments(id),
 diagnosis TEXT NOT NULL, instructions TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS prescription_items (
 id INTEGER PRIMARY KEY, prescription_id INTEGER NOT NULL REFERENCES prescriptions(id),
 medicine_id INTEGER NOT NULL REFERENCES medicines(id), quantity INTEGER NOT NULL CHECK(quantity>0), dosage TEXT NOT NULL,
 UNIQUE(prescription_id,medicine_id)
);
CREATE INDEX IF NOT EXISTS appointments_date ON appointments(scheduled_at);
CREATE INDEX IF NOT EXISTS appointments_student ON appointments(student_id);
CREATE VIEW IF NOT EXISTS appointment_details AS
 SELECT a.*,s.name student_name,s.student_number,s.department,d.name doctor_name,d.specialty
 FROM appointments a JOIN students s ON s.id=a.student_id JOIN doctors d ON d.id=a.doctor_id;
