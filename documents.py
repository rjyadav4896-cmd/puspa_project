"""Document persistence: MongoDB in database mode, JSON for a zero-service demo."""
import json
import os
from pathlib import Path
from threading import RLock
from uuid import uuid4
from datetime import datetime, timezone


class DocumentStore:
    def __init__(self, folder, mongo_uri=None):
        self.path = Path(folder) / 'health_records.json'
        self.lock = RLock()
        self.collection = None
        self.mode = 'Local JSON (demo)'
        if mongo_uri:
            from pymongo import MongoClient
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=4000)
            self.client.admin.command('ping')
            self.collection = self.client.campuscare.health_records
            self.collection.create_index([('student_id', 1), ('created_at', -1)])
            self.collection.create_index('tags')
            self.mode = 'MongoDB'

    def list(self, student_id=None):
        if self.collection is not None:
            query = {} if student_id is None else {'student_id': student_id}
            return list(self.collection.find(query, {'_id': 0}).sort('created_at', -1))
        with self.lock:
            rows = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else []
        return sorted([r for r in rows if student_id is None or r['student_id'] == student_id], key=lambda r: r['created_at'], reverse=True)

    def add(self, record):
        record = {**record, 'id': uuid4().hex, 'created_at': datetime.now(timezone.utc).isoformat()}
        if self.collection is not None:
            self.collection.insert_one(dict(record))
        else:
            with self.lock:
                rows = self.list()
                rows.append(record)
                temporary = self.path.with_suffix('.tmp')
                temporary.write_text(json.dumps(rows, indent=2), encoding='utf-8')
                os.replace(temporary, self.path)
        return record

    def tag_counts(self):
        if self.collection is not None:
            return list(self.collection.aggregate([
                {'$unwind': '$tags'}, {'$group': {'_id': '$tags', 'count': {'$sum': 1}}},
                {'$sort': {'count': -1, '_id': 1}}, {'$project': {'_id': 0, 'tag': '$_id', 'count': 1}}
            ]))
        counts = {}
        for record in self.list():
            for tag in record['tags']:
                counts[tag] = counts.get(tag, 0) + 1
        return [{'tag': tag, 'count': count} for tag, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]
