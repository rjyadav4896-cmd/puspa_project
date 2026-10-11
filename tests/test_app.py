import unittest
from pathlib import Path
from uuid import uuid4
from datetime import date, timedelta

from app import create_app


class CampusCareTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parent.parent / 'data' / 'tests'
        test_root.mkdir(parents=True, exist_ok=True)
        self.folder = test_root / uuid4().hex
        self.folder.mkdir()
        self.app = create_app({'TESTING': True, 'DATA_DIR': str(self.folder), 'SECRET_KEY': 'test-only', 'MONGO_URI': None})
        self.client = self.app.test_client()
        self.token = self.client.get('/api/session').json['csrf']
        response = self.post('login', {'username': 'admin', 'password': 'CampusCare123!'})
        self.token = response.json['csrf']

    def tearDown(self):
        for child in self.folder.iterdir():
            child.unlink()
        self.folder.rmdir()

    def post(self, path, body):
        return self.client.post('/api/' + path, json=body, headers={'X-CSRF-Token': self.token})

    def prescription(self, items, appointment_id=1):
        return self.post('prescriptions', {'appointment_id': appointment_id, 'diagnosis': 'Demo diagnosis',
                                          'instructions': 'Demo directions', 'items': items})

    def test_authentication_and_csrf(self):
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get('/api/students').status_code, 401)
        self.assertEqual(self.client.post('/api/students', json={}).status_code, 403)
        response = self.post('login', {'username': 'admin', 'password': 'wrong'})
        self.assertEqual(response.status_code, 401)

    def test_duplicate_appointment_slot(self):
        body = {'student_id': 1, 'doctor_id': 1, 'scheduled_at': (date.today()+timedelta(days=20)).isoformat()+'T10:00', 'reason': 'Checkup'}
        self.assertEqual(self.post('appointments', body).status_code, 201)
        body['student_id'] = 2
        self.assertEqual(self.post('appointments', body).status_code, 409)
        body['student_id'], body['doctor_id'] = 1, 2
        self.assertEqual(self.post('appointments', body).status_code, 409)

    def test_dispensing_is_atomic(self):
        before = self.client.get('/api/medicines').json
        result = self.prescription([{'medicine_id': 1, 'quantity': 2, 'dosage': 'Demo'},
                                    {'medicine_id': 2, 'quantity': 999999, 'dosage': 'Demo'}])
        self.assertEqual(result.status_code, 400)
        self.assertEqual(self.client.get('/api/medicines').json, before)
        self.assertEqual(self.client.get('/api/prescriptions').json, [])
        result = self.prescription([{'medicine_id': 1, 'quantity': 2, 'dosage': 'Demo'}])
        self.assertEqual(result.status_code, 201)
        after = self.client.get('/api/medicines').json
        self.assertEqual(next(m['stock'] for m in after if m['id']==1), next(m['stock'] for m in before if m['id']==1)-2)
        self.assertEqual(self.prescription([{'medicine_id': 1, 'quantity': 2, 'dosage': 'Demo'}]).status_code, 409)

    def test_expiry_and_cancelled_appointment(self):
        result = self.post('medicines', {'name': 'Expired batch', 'stock': 10, 'unit': 'tablets', 'reorder_level': 2, 'expiry_date': '2000-01-01'})
        medicine_id = result.json['id']
        self.assertEqual(self.prescription([{'medicine_id': medicine_id, 'quantity': 1, 'dosage': 'Demo'}]).status_code, 400)
        self.assertEqual(self.post(f'medicines/{medicine_id}/restock', {'quantity': 5}).status_code, 400)
        self.client.patch('/api/appointments/18', json={'status': 'Cancelled'}, headers={'X-CSRF-Token': self.token})
        self.assertEqual(self.prescription([{'medicine_id': 1, 'quantity': 1, 'dosage': 'Demo'}], 18).status_code, 400)

    def test_document_queries_and_analytics(self):
        response = self.post('records', {'student_id': 2, 'title': 'Follow-up', 'notes': 'Fictional note', 'tags': ['WELLNESS', 'wellness', 'demo']})
        self.assertEqual(response.status_code, 201)
        records = self.client.get('/api/records?student_id=2').json
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['tags'], ['demo', 'wellness'])
        analytics = self.client.get('/api/analytics').json
        self.assertEqual(analytics['totals']['students'], 6)
        self.assertTrue(any(t['tag']=='demo' and t['count']==1 for t in analytics['tags']))
        self.assertEqual(analytics['doctors'][0]['rank'], 1)

    def test_invalid_data(self):
        self.assertEqual(self.post('records', {'student_id': 999, 'title': 'Bad', 'notes': 'Bad'}).status_code, 400)
        self.assertEqual(self.post('medicines', {'name': 'Invalid', 'stock': -1, 'unit': 'tablets', 'reorder_level': 2, 'expiry_date': '2028-01-01'}).status_code, 400)
        self.assertEqual(self.prescription([{'medicine_id': 1, 'quantity': 1.5, 'dosage': 'Demo'}]).status_code, 400)
        self.assertEqual(self.client.get('/api/records?student_id=abc').status_code, 400)

    def test_persistence(self):
        self.post('records', {'student_id': 3, 'title': 'Persistent note', 'notes': 'Fictional', 'tags': []})
        restarted = create_app({'TESTING': True, 'DATA_DIR': str(self.folder), 'SECRET_KEY': 'test-only', 'MONGO_URI': None})
        self.assertTrue(any(r['title']=='Persistent note' for r in restarted.extensions['documents'].list(3)))

    def test_edit_student_and_doctor(self):
        student = self.client.get('/api/students').json[0]
        student['allergies'] = 'Updated demonstration allergy'
        result = self.client.put(f'/api/students/{student["id"]}', json=student, headers={'X-CSRF-Token': self.token})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(next(s for s in self.client.get('/api/students').json if s['id']==student['id'])['allergies'], student['allergies'])
        doctor = self.client.get('/api/doctors').json[0]
        doctor['specialty'] = 'Updated specialty'
        result = self.client.put(f'/api/doctors/{doctor["id"]}', json=doctor, headers={'X-CSRF-Token': self.token})
        self.assertEqual(result.status_code, 200)


if __name__ == '__main__':
    unittest.main()
