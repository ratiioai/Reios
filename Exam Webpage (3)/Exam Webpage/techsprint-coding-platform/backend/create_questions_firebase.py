"""
Create 150 questions in Firebase
"""
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import sys
from pathlib import Path

# Initialize Firebase
cred_path = Path(__file__).parent / "firebase-credentials.json"
cred = credentials.Certificate(str(cred_path))

try:
    firebase_admin.initialize_app(cred)
except:
    pass  # Already initialized

db = firestore.client()

# Question templates (same as before)
EASY_TEMPLATES = [
    {
        "title": "Sum of Two Numbers",
        "prompt": "Write a program that takes two integers and returns their sum.\n\nInput: Two integers separated by space\nOutput: Their sum",
        "sample_tests": [
            {"input": "5 3", "output": "8", "explanation": "5 + 3 = 8"},
            {"input": "10 20", "output": "30", "explanation": "10 + 20 = 30"}
        ],
        "hidden_tests": [
            {"input": "0 0", "output": "0"},
            {"input": "-5 5", "output": "0"},
            {"input": "100 200", "output": "300"},
            {"input": "-10 -20", "output": "-30"},
            {"input": "999 1", "output": "1000"}
        ],
        "starter": "a, b = map(int, input().split())\n# Write your code here\nprint(result)"
    },
    {
        "title": "Check Even or Odd",
        "prompt": "Determine if a number is even or odd.\n\nInput: Integer n\nOutput: 'Even' or 'Odd'",
        "sample_tests": [
            {"input": "4", "output": "Even", "explanation": "4 is divisible by 2"},
            {"input": "7", "output": "Odd", "explanation": "7 is not divisible by 2"}
        ],
        "hidden_tests": [
            {"input": "0", "output": "Even"},
            {"input": "1", "output": "Odd"},
            {"input": "100", "output": "Even"},
            {"input": "999", "output": "Odd"},
            {"input": "-6", "output": "Even"}
        ],
        "starter": "n = int(input())\n# Write your code here\nprint(result)"
    },
    # Add more templates as needed
]

print("=" * 80)
print("CREATING 150 QUESTIONS IN FIREBASE")
print("=" * 80)
print()

confirm = input("Create questions now? (yes/no): ")
if confirm.lower() != "yes":
    print("Cancelled.")
    sys.exit()

try:
    questions_ref = db.collection('questions')
    count = 0
    
    # Create 60 easy questions
    print("\nCreating EASY questions...")
    for i in range(12):  # 5 templates × 12 = 60
        for template in EASY_TEMPLATES[:5]:  # Limit to 5 templates
            question_id = f"easy_{count+1}"
            questions_ref.document(question_id).set({
                'title': f"{template['title']} {i+1}" if i > 0 else template['title'],
                'difficulty': 'easy',
                'prompt': template['prompt'],
                'starter_code_python': template['starter'],
                'sample_test_cases': template['sample_tests'],
                'hidden_test_cases': template['hidden_tests'],
                'time_limit_seconds': 5,
                'memory_limit_mb': 256,
                'marks': 5,
                'is_active': True,
                'created_at': firestore.SERVER_TIMESTAMP
            })
            count += 1
            if count >= 60:
                break
        if count >= 60:
            break
    
    print(f"   Created {count} easy questions")
    
    # Create 60 medium questions (simplified for speed)
    print("\nCreating MEDIUM questions...")
    for i in range(60):
        question_id = f"medium_{i+1}"
        questions_ref.document(question_id).set({
            'title': f"Medium Problem {i+1}",
            'difficulty': 'medium',
            'prompt': "Solve this medium-level coding problem.",
            'starter_code_python': "# Write your solution here\n",
            'sample_test_cases': [
                {"input": "test", "output": "result", "explanation": "Sample test"}
            ],
            'hidden_test_cases': [
                {"input": "1", "output": "1"},
                {"input": "2", "output": "2"}
            ],
            'time_limit_seconds': 5,
            'memory_limit_mb': 256,
            'marks': 10,
            'is_active': True,
            'created_at': firestore.SERVER_TIMESTAMP
        })
        count += 1
    
    print(f"   Created 60 medium questions")
    
    # Create 30 hard questions
    print("\nCreating HARD questions...")
    for i in range(30):
        question_id = f"hard_{i+1}"
        questions_ref.document(question_id).set({
            'title': f"Hard Problem {i+1}",
            'difficulty': 'hard',
            'prompt': "Solve this hard-level coding problem.",
            'starter_code_python': "# Write your solution here\n",
            'sample_test_cases': [
                {"input": "test", "output": "result", "explanation": "Sample test"}
            ],
            'hidden_test_cases': [
                {"input": "1", "output": "1"},
                {"input": "2", "output": "2"}
            ],
            'time_limit_seconds': 10,
            'memory_limit_mb': 256,
            'marks': 20,
            'is_active': True,
            'created_at': firestore.SERVER_TIMESTAMP
        })
        count += 1
    
    print(f"   Created 30 hard questions")
    
    print()
    print("=" * 80)
    print(f"✨ SUCCESS! Created {count} questions in Firebase")
    print("=" * 80)
    print()
    print("Next step: python upload_teams_firebase.py")
    print()

except Exception as e:
    print(f"\n❌ Error: {e}")
    sys.exit(1)
