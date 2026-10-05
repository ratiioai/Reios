"""
Firebase Firestore adapter for the backend
Provides a compatibility layer that mimics SQLAlchemy patterns
"""
import hashlib
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# Initialize Firebase
BASE_DIR = Path(__file__).resolve().parent.parent
cred_path = BASE_DIR / "firebase-credentials.json"

if not firebase_admin._apps:
    cred = credentials.Certificate(str(cred_path))
    firebase_admin.initialize_app(cred)

db = firestore.client()


# Collections
TEAMS_COLLECTION = "teams"
QUESTIONS_COLLECTION = "questions"
ADMINS_COLLECTION = "admins"
SESSIONS_COLLECTION = "test_sessions"
SUBMISSIONS_COLLECTION = "submissions"
GRADING_RESULTS_COLLECTION = "grading_results"
ASSIGNMENTS_COLLECTION = "team_question_assignments"
CONFIG_COLLECTION = "test_configuration"


class FirebaseSession:
    """Mock session object that mimics SQLAlchemy session"""
    
    def __init__(self):
        self.db = db
    
    def query(self, model_class):
        """Return a query builder for the model"""
        return FirebaseQuery(model_class, self.db)
    
    def add(self, obj):
        """Add object to Firestore"""
        collection = obj.__collection__
        data = obj.to_dict()
        
        if hasattr(obj, 'id') and obj.id:
            # Update existing
            self.db.collection(collection).document(obj.id).set(data)
        else:
            # Create new
            doc_ref = self.db.collection(collection).document()
            obj.id = doc_ref.id
            doc_ref.set(data)
    
    def commit(self):
        """Firestore auto-commits, so this is a no-op"""
        pass
    
    def close(self):
        """Close session (no-op for Firestore)"""
        pass
    
    def refresh(self, obj):
        """Refresh object from Firestore"""
        collection = obj.__collection__
        doc = self.db.collection(collection).document(obj.id).get()
        if doc.exists:
            obj.from_dict(doc.to_dict())
    
    def delete(self, obj):
        """Delete object from Firestore"""
        collection = obj.__collection__
        self.db.collection(collection).document(obj.id).delete()


class FirebaseQuery:
    """Query builder that mimics SQLAlchemy query"""
    
    def __init__(self, model_class, db):
        self.model_class = model_class
        self.db = db
        self.filters = []
        self._limit = None
        self._order_by_field = None
        self._order_direction = 'ASCENDING'
    
    def filter(self, *conditions):
        """Add filter conditions"""
        self.filters.extend(conditions)
        return self
    
    def filter_by(self, **kwargs):
        """Add equality filters"""
        for key, value in kwargs.items():
            self.filters.append((key, '==', value))
        return self
    
    def limit(self, n):
        """Limit results"""
        self._limit = n
        return self
    
    def order_by(self, field):
        """Order results"""
        self._order_by_field = field
        return self
    
    def first(self):
        """Get first result"""
        results = self.all()
        return results[0] if results else None
    
    def all(self):
        """Get all results"""
        collection = self.model_class.__collection__
        query = self.db.collection(collection)
        
        # Apply filters
        for f in self.filters:
            if isinstance(f, tuple):
                field, op, value = f
                query = query.where(filter=FieldFilter(field, op, value))
        
        # Apply ordering
        if self._order_by_field:
            query = query.order_by(self._order_by_field, direction=self._order_direction)
        
        # Apply limit
        if self._limit:
            query = query.limit(self._limit)
        
        # Execute query
        docs = query.stream()
        
        # Convert to model objects
        results = []
        for doc in docs:
            obj = self.model_class.from_firestore(doc)
            results.append(obj)
        
        return results
    
    def count(self):
        """Count results"""
        return len(self.all())


# Mock models for Firebase
class FirebaseModel:
    """Base model for Firebase documents"""
    __collection__ = None
    
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self):
        """Convert to dictionary for Firestore"""
        data = {}
        for key, value in self.__dict__.items():
            if key == 'id':
                continue
            if isinstance(value, datetime):
                data[key] = value
            else:
                data[key] = value
        return data
    
    @classmethod
    def from_firestore(cls, doc):
        """Create instance from Firestore document"""
        data = doc.to_dict()
        data['id'] = doc.id
        return cls(**data)


class Admin(FirebaseModel):
    __collection__ = ADMINS_COLLECTION
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.username = kwargs.get('username')
        self.email = kwargs.get('email')
        self.hashed_password = kwargs.get('hashed_password')
        self.is_active = kwargs.get('is_active', True)
        self.created_at = kwargs.get('created_at', datetime.now(timezone.utc))


class Team(FirebaseModel):
    __collection__ = TEAMS_COLLECTION
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.team_name = kwargs.get('team_name')
        self.leader_name = kwargs.get('leader_name')
        self.leader_phone_hash = kwargs.get('leader_phone_hash')
        self.member_2 = kwargs.get('member_2')
        self.member_3 = kwargs.get('member_3')
        self.member_4 = kwargs.get('member_4')
        self.college = kwargs.get('college')
        self.is_active = kwargs.get('is_active', True)
        self.failed_login_attempts = kwargs.get('failed_login_attempts', 0)
        self.locked_until = kwargs.get('locked_until')
        self.created_at = kwargs.get('created_at', datetime.now(timezone.utc))


class Question(FirebaseModel):
    __collection__ = QUESTIONS_COLLECTION
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = kwargs.get('title')
        self.difficulty = kwargs.get('difficulty')
        self.prompt_markdown = kwargs.get('prompt_markdown')
        self.starter_code_python = kwargs.get('starter_code_python')
        self.starter_code_cpp = kwargs.get('starter_code_cpp')
        self.starter_code_java = kwargs.get('starter_code_java')
        self.starter_code_javascript = kwargs.get('starter_code_javascript')
        self.time_limit_seconds = kwargs.get('time_limit_seconds', 5)
        self.memory_limit_mb = kwargs.get('memory_limit_mb', 256)
        self.marks = kwargs.get('marks')
        self.is_active = kwargs.get('is_active', True)
        self.sample_test_cases = kwargs.get('sample_test_cases', [])
        self.hidden_test_cases = kwargs.get('hidden_test_cases', [])


class TestSession(FirebaseModel):
    __collection__ = SESSIONS_COLLECTION
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.team_id = kwargs.get('team_id')
        self.test_started_at = kwargs.get('test_started_at')
        self.submitted_at = kwargs.get('submitted_at')
        self.auto_submitted = kwargs.get('auto_submitted', False)
        self.status = kwargs.get('status', 'not_started')
        self.time_taken_seconds = kwargs.get('time_taken_seconds')
        self.total_score = kwargs.get('total_score', 0)
        self.easy_score = kwargs.get('easy_score', 0)
        self.medium_score = kwargs.get('medium_score', 0)
        self.hard_score = kwargs.get('hard_score', 0)
        self.rank = kwargs.get('rank')


class Submission(FirebaseModel):
    __collection__ = SUBMISSIONS_COLLECTION
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.team_id = kwargs.get('team_id')
        self.question_id = kwargs.get('question_id')
        self.code = kwargs.get('code')
        self.language = kwargs.get('language')
        self.submitted_at = kwargs.get('submitted_at', datetime.now(timezone.utc))
        self.is_final = kwargs.get('is_final', False)


class GradingResult(FirebaseModel):
    __collection__ = GRADING_RESULTS_COLLECTION
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.submission_id = kwargs.get('submission_id')
        self.marks_awarded = kwargs.get('marks_awarded', 0)
        self.passed_hidden_tests = kwargs.get('passed_hidden_tests', 0)
        self.total_hidden_tests = kwargs.get('total_hidden_tests', 0)
        self.test_results = kwargs.get('test_results', [])
        self.error_output = kwargs.get('error_output')
        self.execution_time_ms = kwargs.get('execution_time_ms')
        self.auto_graded_at = kwargs.get('auto_graded_at', datetime.now(timezone.utc))


class TeamQuestionAssignment(FirebaseModel):
    __collection__ = ASSIGNMENTS_COLLECTION
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.team_id = kwargs.get('team_id')
        self.question_id = kwargs.get('question_id')
        self.position = kwargs.get('position')
        self.created_at = kwargs.get('created_at', datetime.now(timezone.utc))


def get_db():
    """Get Firebase session (mimics SQLAlchemy get_db)"""
    session = FirebaseSession()
    try:
        yield session
    finally:
        session.close()


def create_tables():
    """No-op for Firebase (collections created automatically)"""
    print("✓ Firebase collections initialized")
    pass
