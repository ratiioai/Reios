"""
Fast Firebase Question Creator - Batch Upload
Creates 150 questions in seconds using batch operations
"""
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import sys
from pathlib import Path

print("=" * 80)
print("FAST FIREBASE QUESTION CREATOR")
print("=" * 80)
print()

# Initialize Firebase
cred_path = Path(__file__).parent / "firebase-credentials.json"
if not cred_path.exists():
    print("❌ firebase-credentials.json not found!")
    print("Make sure you downloaded it from Firebase Console")
    sys.exit(1)

try:
    cred = credentials.Certificate(str(cred_path))
    firebase_admin.initialize_app(cred)
except:
    pass  # Already initialized

db = firestore.client()

print("Creating 150 questions in Firebase...")
print("Using batch operations for speed...")
print()

try:
    # Use batch for faster writes (up to 500 per batch)
    batch = db.batch()
    count = 0
    
    # Create 60 EASY questions
    for i in range(60):
        ref = db.collection('questions').document(f'easy_{i+1}')
        batch.set(ref, {
            'id': f'easy_{i+1}',
            'title': f'Easy Problem {i+1}',
            'difficulty': 'easy',
            'prompt': f'Solve this easy coding problem. Question {i+1}.',
            'starter_code_python': '# Write your solution\n',
            'sample_test_cases': [
                {'input': 'test', 'output': 'result', 'explanation': 'Sample'}
            ],
            'hidden_test_cases': [
                {'input': '1', 'output': '1'},
                {'input': '2', 'output': '2'},
                {'input': '3', 'output': '3'}
            ],
            'time_limit_seconds': 5,
            'memory_limit_mb': 256,
            'marks': 5,
            'is_active': True,
            'created_at': firestore.SERVER_TIMESTAMP
        })
        count += 1
    
    # Create 60 MEDIUM questions
    for i in range(60):
        ref = db.collection('questions').document(f'medium_{i+1}')
        batch.set(ref, {
            'id': f'medium_{i+1}',
            'title': f'Medium Problem {i+1}',
            'difficulty': 'medium',
            'prompt': f'Solve this medium coding problem. Question {i+1}.',
            'starter_code_python': '# Write your solution\n',
            'sample_test_cases': [
                {'input': 'test', 'output': 'result', 'explanation': 'Sample'}
            ],
            'hidden_test_cases': [
                {'input': '1', 'output': '1'},
                {'input': '2', 'output': '2'},
                {'input': '3', 'output': '3'}
            ],
            'time_limit_seconds': 5,
            'memory_limit_mb': 256,
            'marks': 10,
            'is_active': True,
            'created_at': firestore.SERVER_TIMESTAMP
        })
        count += 1
    
    # Create 30 HARD questions
    for i in range(30):
        ref = db.collection('questions').document(f'hard_{i+1}')
        batch.set(ref, {
            'id': f'hard_{i+1}',
            'title': f'Hard Problem {i+1}',
            'difficulty': 'hard',
            'prompt': f'Solve this hard coding problem. Question {i+1}.',
            'starter_code_python': '# Write your solution\n',
            'sample_test_cases': [
                {'input': 'test', 'output': 'result', 'explanation': 'Sample'}
            ],
            'hidden_test_cases': [
                {'input': '1', 'output': '1'},
                {'input': '2', 'output': '2'},
                {'input': '3', 'output': '3'}
            ],
            'time_limit_seconds': 10,
            'memory_limit_mb': 256,
            'marks': 20,
            'is_active': True,
            'created_at': firestore.SERVER_TIMESTAMP
        })
        count += 1
    
    # Commit batch
    print(f"Committing {count} questions to Firebase...")
    batch.commit()
    
    print()
    print("=" * 80)
    print(f"✨ SUCCESS! Created {count} questions in Firebase")
    print("=" * 80)
    print()
    print("Verify in Firebase Console:")
    print("https://console.firebase.google.com/project/spec-industry-hack-round-1-26/firestore")
    print()
    print("Next steps:")
    print("1. Upload teams tomorrow morning")
    print("2. Start services")
    print("3. Launch test!")
    print()

except Exception as e:
    print()
    print(f"❌ Error: {e}")
    print()
    sys.exit(1)
