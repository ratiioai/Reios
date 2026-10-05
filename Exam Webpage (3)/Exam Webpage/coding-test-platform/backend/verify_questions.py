"""
Verify questions in Firebase
"""
import firebase_admin
from firebase_admin import credentials, firestore

print("=" * 60)
print("VERIFYING FIREBASE QUESTIONS")
print("=" * 60)
print()

try:
    cred = credentials.Certificate('firebase-credentials.json')
    firebase_admin.initialize_app(cred)
except:
    pass  # Already initialized

db = firestore.client()

print("Counting questions...")
questions = list(db.collection('questions').stream())

easy = [q for q in questions if q.to_dict().get('difficulty') == 'easy']
medium = [q for q in questions if q.to_dict().get('difficulty') == 'medium']
hard = [q for q in questions if q.to_dict().get('difficulty') == 'hard']

print()
print(f"✅ Total questions: {len(questions)}")
print(f"   - Easy: {len(easy)}")
print(f"   - Medium: {len(medium)}")
print(f"   - Hard: {len(hard)}")
print()

if len(questions) >= 150:
    print("=" * 60)
    print("🎉 SUCCESS! Questions are ready!")
    print("=" * 60)
    print()
    print("Sample questions:")
    for i, q in enumerate(questions[:3]):
        data = q.to_dict()
        print(f"{i+1}. {data.get('title')} ({data.get('difficulty')})")
    print()
    print("You're all set for tomorrow!")
else:
    print("⚠️  Less than 150 questions found")
    print("Run: python create_questions_fast_firebase.py")

print()
