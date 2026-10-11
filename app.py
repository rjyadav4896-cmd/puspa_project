"""CampusCare: college health centre demonstration application."""
import os
import secrets
import sqlite3
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from functools import wraps

from flask import Flask, g, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from documents import DocumentStore

ROOT = Path(__file__).resolve().parent


def create_app(test_config=None):
    app = Flask(__name__)
    default_data_dir = Path(tempfile.gettempdir()) / 'campuscare' if os.getenv('VERCEL') == '1' else ROOT / 'data'
    app.config.update(DATA_DIR=os.getenv('DATA_DIR', str(default_data_dir)), SECRET_KEY=os.getenv('SECRET_KEY'),
                      MONGO_URI=os.getenv('MONGO_URI'), SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Strict', MAX_CONTENT_LENGTH=128 * 1024)
    if test_config:
        app.config.update(test_config)
    folder = Path(app.config['DATA_DIR'])
    folder.mkdir(parents=True, exist_ok=True)
    if not app.config['SECRET_KEY']:
        secret_file = folder / '.session_secret'
        if not secret_file.exists():
            secret_file.write_text(secrets.token_hex(32), encoding='utf-8')
        app.config['SECRET_KEY'] = secret_file.read_text(encoding='utf-8')
    app.config['DATABASE'] = str(folder / 'campuscare.sqlite3')
    app.extensions['documents'] = DocumentStore(folder, app.config['MONGO_URI'])

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'], timeout=10)
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys=ON')
        return g.db

    @app.teardown_appcontext
    def close_db(error=None):
        connection = g.pop('db', None)
        if connection is not None:
            connection.close()

    def rows(sql, params=()):
        return [dict(r) for r in db().execute(sql, params).fetchall()]

    def require_login(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if not session.get('user_id'):
                return jsonify(error='Please sign in to continue.'), 401
            return func(*args, **kwargs)
        return wrapped

    @app.before_request
    def csrf():
        if request.path.startswith('/api/') and request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            token = session.get('csrf')
            if not token or not secrets.compare_digest(token, request.headers.get('X-CSRF-Token', '')):
                return jsonify(error='Session expired. Refresh the page and try again.'), 403

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(ValueError)
    def validation(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(sqlite3.IntegrityError)
    def conflict(error):
        db().rollback()
        return jsonify(error='This conflicts with an existing record. Check student numbers, medicine names, appointment slots, and prescriptions.'), 409

    def payload():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError('Please submit a valid JSON object.')
        return data

    def text(data, key, optional=False, limit=2000):
        value = data.get(key, '')
        if not isinstance(value, str):
            raise ValueError(f'{key.replace("_", " ").title()} must be text.')
        value = value.strip()
        if not value and not optional:
            raise ValueError(f'{key.replace("_", " ").title()} is required.')
        if len(value) > limit:
            raise ValueError(f'{key.replace("_", " ").title()} is too long (maximum {limit} characters).')
        return value

    def integer(data, key, minimum=1):
        value = data.get(key)
        if isinstance(value, bool) or not str(value).isdigit() or int(value) < minimum:
            raise ValueError(f'{key.replace("_", " ").title()} must be an integer of at least {minimum}.')
        return int(value)

    def exists(table, identity):
        record = db().execute(f'SELECT * FROM {table} WHERE id=?', (identity,)).fetchone()
        if record is None:
            raise ValueError(f'The selected {table.rstrip("s")} does not exist.')
        return record

    def valid_date(value):
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            raise ValueError('Enter a valid date.')

    @app.get('/')
    def index():
        return render_template('index.html')

    @app.get('/api/session')
    def current_session():
        session.setdefault('csrf', secrets.token_hex(24))
        return jsonify(username=session.get('username'), csrf=session['csrf'])

    @app.post('/api/login')
    def login():
        data = payload()
        user = db().execute('SELECT * FROM users WHERE username=?', (text(data, 'username'),)).fetchone()
        if not user or not check_password_hash(user['password_hash'], text(data, 'password')):
            return jsonify(error='Incorrect username or password.'), 401
        session.clear()
        session.update(user_id=user['id'], username=user['username'], csrf=secrets.token_hex(24))
        return jsonify(username=user['username'], csrf=session['csrf'])

    @app.post('/api/logout')
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get('/api/<entity>')
    @require_login
    def list_entity(entity):
        queries = {
            'students': 'SELECT * FROM students ORDER BY name',
            'doctors': 'SELECT * FROM doctors ORDER BY name',
            'medicines': 'SELECT * FROM medicines ORDER BY name',
            'appointments': 'SELECT * FROM appointment_details ORDER BY scheduled_at DESC',
            'prescriptions': '''SELECT p.*,a.student_name,a.doctor_name,a.student_id FROM prescriptions p
                JOIN appointment_details a ON a.id=p.appointment_id ORDER BY p.id DESC'''
        }
        if entity not in queries:
            return jsonify(error='Unknown resource.'), 404
        result = rows(queries[entity])
        if entity == 'prescriptions':
            items = rows('SELECT i.*,m.name medicine_name,m.unit FROM prescription_items i JOIN medicines m ON m.id=i.medicine_id')
            for record in result:
                record['items'] = [i for i in items if i['prescription_id'] == record['id']]
        return jsonify(result)

    @app.post('/api/<entity>')
    @app.put('/api/<entity>/<int:identity>')
    @require_login
    def add_entity(entity, identity=None):
        data = payload()
        if identity is not None:
            if entity not in ('students', 'doctors'):
                return jsonify(error='This record type cannot be edited directly.'), 405
            exists(entity, identity)
        if entity == 'students':
            blood = text(data, 'blood_group')
            if blood not in ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'Unknown'):
                raise ValueError('Select a valid blood group.')
            email = text(data, 'email', limit=254)
            if '@' not in email or '.' not in email.split('@')[-1]:
                raise ValueError('Enter a valid email address.')
            values = (text(data, 'student_number', limit=40), text(data, 'name', limit=100), email,
                      text(data, 'department', limit=100), blood, text(data, 'allergies', optional=True))
            query = 'INSERT INTO students(student_number,name,email,department,blood_group,allergies) VALUES(?,?,?,?,?,?)'
        elif entity == 'doctors':
            values = (text(data, 'name', limit=100), text(data, 'specialty', limit=100), text(data, 'email', limit=254))
            if '@' not in values[2]:
                raise ValueError('Enter a valid email address.')
            query = 'INSERT INTO doctors(name,specialty,email) VALUES(?,?,?)'
        elif entity == 'medicines':
            values = (text(data, 'name', limit=100), integer(data, 'stock', 0), text(data, 'unit', limit=40),
                      integer(data, 'reorder_level', 0), valid_date(text(data, 'expiry_date')))
            query = 'INSERT INTO medicines(name,stock,unit,reorder_level,expiry_date) VALUES(?,?,?,?,?)'
        elif entity == 'appointments':
            student = integer(data, 'student_id')
            doctor = integer(data, 'doctor_id')
            exists('students', student)
            exists('doctors', doctor)
            try:
                when = datetime.fromisoformat(text(data, 'scheduled_at'))
            except ValueError:
                raise ValueError('Enter a valid appointment date and time.')
            if when.tzinfo is not None or when.second or when.microsecond or when.minute % 30:
                raise ValueError('Choose a local appointment time at :00 or :30.')
            if when < datetime.now():
                raise ValueError('New appointments must be in the future.')
            values = (student, doctor, when.isoformat(timespec='minutes'), text(data, 'reason'))
            query = 'INSERT INTO appointments(student_id,doctor_id,scheduled_at,reason) VALUES(?,?,?,?)'
        else:
            return jsonify(error='Unknown resource.'), 404
        if identity is not None:
            columns = ('student_number', 'name', 'email', 'department', 'blood_group', 'allergies') if entity == 'students' else ('name', 'specialty', 'email')
            query = f'UPDATE {entity} SET ' + ','.join(f'{column}=?' for column in columns) + ' WHERE id=?'
            values = (*values, identity)
        with db():
            cursor = db().execute(query, values)
        return jsonify(id=identity or cursor.lastrowid), 200 if identity is not None else 201

    @app.patch('/api/appointments/<int:identity>')
    @require_login
    def update_appointment(identity):
        status = text(payload(), 'status')
        if status not in ('Completed', 'Cancelled'):
            raise ValueError('Choose Completed or Cancelled.')
        with db():
            cursor = db().execute("UPDATE appointments SET status=? WHERE id=? AND status='Scheduled'", (status, identity))
            if cursor.rowcount != 1:
                raise ValueError('Only a scheduled appointment can be updated.')
        return jsonify(ok=True)

    @app.post('/api/medicines/<int:identity>/restock')
    @require_login
    def restock(identity):
        data = payload()
        amount = integer(data, 'quantity')
        medicine = exists('medicines', identity)
        if medicine['expiry_date'] < date.today().isoformat():
            raise ValueError('This stock is expired. Use a separately named batch with a valid expiry date.')
        with db():
            db().execute('UPDATE medicines SET stock=stock+? WHERE id=?', (amount, identity))
        return jsonify(ok=True)

    @app.post('/api/prescriptions')
    @require_login
    def prescribe():
        data = payload()
        appointment_id = integer(data, 'appointment_id')
        diagnosis = text(data, 'diagnosis')
        instructions = text(data, 'instructions')
        items = data.get('items')
        if not isinstance(items, list) or not 1 <= len(items) <= 20:
            raise ValueError('Add between 1 and 20 medicines.')
        validated = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError('Invalid prescription item.')
            validated.append((integer(item, 'medicine_id'), integer(item, 'quantity'), text(item, 'dosage')))
        if len({i[0] for i in validated}) != len(validated):
            raise ValueError('Add each medicine only once.')
        with db():
            db().execute('BEGIN IMMEDIATE')
            appointment = exists('appointments', appointment_id)
            if appointment['status'] == 'Cancelled':
                raise ValueError('A cancelled appointment cannot have a prescription.')
            cursor = db().execute('INSERT INTO prescriptions(appointment_id,diagnosis,instructions) VALUES(?,?,?)',
                                  (appointment_id, diagnosis, instructions))
            prescription_id = cursor.lastrowid
            for medicine_id, quantity, dosage in validated:
                medicine = exists('medicines', medicine_id)
                if medicine['expiry_date'] < date.today().isoformat():
                    raise ValueError(f'{medicine["name"]} has expired.')
                changed = db().execute('UPDATE medicines SET stock=stock-? WHERE id=? AND stock>=?', (quantity, medicine_id, quantity))
                if changed.rowcount != 1:
                    raise ValueError(f'Insufficient stock for {medicine["name"]}.')
                db().execute('INSERT INTO prescription_items(prescription_id,medicine_id,quantity,dosage) VALUES(?,?,?,?)',
                             (prescription_id, medicine_id, quantity, dosage))
            db().execute("UPDATE appointments SET status='Completed' WHERE id=?", (appointment_id,))
        return jsonify(id=prescription_id), 201

    @app.get('/api/records')
    @require_login
    def get_records():
        student_id = request.args.get('student_id')
        if student_id is not None:
            student_id = integer({'student_id': student_id}, 'student_id')
        return jsonify(app.extensions['documents'].list(student_id))

    @app.post('/api/records')
    @require_login
    def add_record():
        data = payload()
        student_id = integer(data, 'student_id')
        exists('students', student_id)
        tags = data.get('tags', [])
        if not isinstance(tags, list) or len(tags) > 15 or any(not isinstance(t, str) or len(t) > 50 for t in tags):
            raise ValueError('Use up to 15 short text tags.')
        record = {'student_id': student_id, 'title': text(data, 'title', limit=150),
                  'notes': text(data, 'notes', limit=10000), 'tags': sorted(set(t.strip().lower() for t in tags if t.strip())),
                  'author': session['username']}
        return jsonify(app.extensions['documents'].add(record)), 201

    @app.get('/api/analytics')
    @require_login
    def analytics():
        today = date.today().isoformat()
        totals = rows('''SELECT (SELECT COUNT(*) FROM students) students,
            (SELECT COUNT(*) FROM appointments WHERE substr(scheduled_at,1,10)=? AND status!='Cancelled') today,
            (SELECT COUNT(*) FROM appointments WHERE status='Scheduled') scheduled,
            (SELECT COUNT(*) FROM medicines WHERE stock<=reorder_level OR expiry_date<?) alerts''', (today, today))[0]
        departments = rows('''SELECT s.department,COUNT(DISTINCT s.id) students,COUNT(a.id) visits
            FROM students s LEFT JOIN appointments a ON a.student_id=s.id AND a.status!='Cancelled'
            GROUP BY s.department ORDER BY visits DESC''')
        doctors = rows('''WITH workload AS (SELECT d.name,COUNT(a.id) appointments,
            SUM(CASE WHEN a.status='Completed' THEN 1 ELSE 0 END) completed
            FROM doctors d LEFT JOIN appointments a ON a.doctor_id=d.id AND a.status!='Cancelled' GROUP BY d.id)
            SELECT *,DENSE_RANK() OVER(ORDER BY appointments DESC) rank FROM workload ORDER BY rank,name''')
        trend = rows('''SELECT substr(scheduled_at,1,7) month,COUNT(*) visits FROM appointments
            WHERE status!='Cancelled' GROUP BY month ORDER BY month''')
        medicine_usage = rows('''SELECT m.name,COALESCE(SUM(i.quantity),0) dispensed FROM medicines m
            LEFT JOIN prescription_items i ON i.medicine_id=m.id GROUP BY m.id ORDER BY dispensed DESC,m.name''')
        return jsonify(totals=totals, departments=departments, doctors=doctors, trend=trend,
                       medicine_usage=medicine_usage, tags=app.extensions['documents'].tag_counts(),
                       document_store=app.extensions['documents'].mode)

    with app.app_context():
        db().executescript((ROOT / 'schema.sql').read_text(encoding='utf-8'))
        if not db().execute('SELECT 1 FROM users').fetchone():
            with db():
                db().execute('INSERT INTO users(username,password_hash) VALUES(?,?)',
                             ('admin', generate_password_hash(os.getenv('ADMIN_PASSWORD', 'CampusCare123!'))))
        if app.config.get('SEED_DEMO', True) and not db().execute('SELECT 1 FROM students').fetchone():
            seed(db(), app.extensions['documents'])
    return app


def seed(connection, documents):
    """Fictional records; dates are relative to first launch."""
    with connection:
        connection.executemany('INSERT INTO students(student_number,name,email,department,blood_group,allergies) VALUES(?,?,?,?,?,?)', [
            ('ST-2026-001', 'Aarav Sharma', 'aarav@example.test', 'Computer Science', 'O+', 'Penicillin'),
            ('ST-2026-002', 'Priya Thapa', 'priya@example.test', 'Business Studies', 'B+', ''),
            ('ST-2026-003', 'Rohan Gurung', 'rohan@example.test', 'Engineering', 'A+', ''),
            ('ST-2026-004', 'Anisha Rai', 'anisha@example.test', 'Computer Science', 'AB+', 'Peanuts'),
            ('ST-2026-005', 'Suman Karki', 'suman@example.test', 'Engineering', 'O-', ''),
            ('ST-2026-006', 'Nisha Poudel', 'nisha@example.test', 'Business Studies', 'B-', '')])
        connection.executemany('INSERT INTO doctors(name,specialty,email) VALUES(?,?,?)', [
            ('Dr. Maya Joshi', 'General physician', 'maya@example.test'),
            ('Dr. Bikash Shrestha', 'Family medicine', 'bikash@example.test'),
            ('Dr. Sita Adhikari', 'Student wellness', 'sita@example.test')])
        expiry = (date.today() + timedelta(days=365)).isoformat()
        connection.executemany('INSERT INTO medicines(name,stock,unit,reorder_level,expiry_date) VALUES(?,?,?,?,?)', [
            ('Paracetamol 500 mg', 120, 'tablets', 30, expiry), ('Oral rehydration salts', 8, 'sachets', 15, expiry),
            ('Cetirizine 10 mg', 45, 'tablets', 20, expiry), ('Antiseptic solution', 6, 'bottles', 10, expiry)])
        for i in range(18):
            day = date.today() + timedelta(days=(i - 14) * 3 if i < 14 else i - 14)
            when = f'{day.isoformat()}T{9+i%7:02d}:00'
            connection.execute('INSERT INTO appointments(student_id,doctor_id,scheduled_at,reason,status) VALUES(?,?,?,?,?)',
                               (i % 6 + 1, i % 3 + 1, when, ['Routine health check', 'Seasonal allergy review', 'Wellness consultation'][i % 3],
                                'Completed' if i < 14 else 'Scheduled'))
    if not documents.list():
        documents.add({'student_id': 1, 'title': 'Initial health assessment', 'notes': 'Fictional demonstration record. Student-reported allergy recorded; follow-up planned.',
                       'tags': ['assessment', 'follow-up'], 'author': 'admin'})
        documents.add({'student_id': 4, 'title': 'Wellness check-in', 'notes': 'Fictional demonstration record. Discussed sleep routine and campus wellbeing resources.',
                       'tags': ['wellness'], 'author': 'admin'})


# WSGI entry point imported by Vercel and other application servers.
app = create_app()


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', '5000')), debug=False)
