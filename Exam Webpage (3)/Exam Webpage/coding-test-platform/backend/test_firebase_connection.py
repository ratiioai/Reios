"""
Test Firebase connection
"""
import firebase_admin
from firebase_admin import credentials, firestore
import sys
from pathlib import Path

print("=" * 60)
print("TESTING FIREBASE CONNECTION")
print("=" * 60)
print()

try:
    # Initialize Firebase
    cred_path = Path(__file__).parent / "firebase-credentials.json"
    
    if not cred_path.exists():
        print("❌ firebase-credentials.json not found!")
        print()
        print("Please:")
        print("1. Go to Firebase Console")
        print("2. Project Settings → Service Accounts")
        print("3. Generate new private key")
        print("4. Save as 'firebase-credentials.json' in backend folder")
        print()
        print("See FIREBASE_SETUP.md for detailed instructions")
        sys.exit(1)
    
    cred = credentials.Certificate(str(cred_path))
    firebase_admin.initialize_app(cred)
    
    # Test connection
    db = firestore.client()
    
    # Try to write and read a test document
    test_ref = db.collection('_test').document('connection_test')
    test_ref.set({
        'timestamp': firestore.SERVER_TIMESTAMP,
        'message': 'Connection successful'
    })
    
    # Read it back
    doc = test_ref.get()
    
    if doc.exists:
        # Clean up test document
        test_ref.delete()
        
        print("✅ Firebase connection successful!")
        print()
        print(f"Project ID: {firebase_admin.get_app().project_id}")
        print()
        print("=" * 60)
        print("CONNECTION TEST PASSED!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Create questions: python create_questions_firebase.py")
        print("2. Upload teams: python upload_teams_firebase.py")
        print("3. Start services tomorrow morning")
        print()
    else:
        print("❌ Could not write to Firestore")
        sys.exit(1)

except Exception as e:
    print("=" * 60)
    print("❌ FIREBASE CONNECTION FAILED")
    print("=" * 60)
    print()
    print(f"Error: {e}")
    print()
    print("Possible solutions:")
    print("1. Make sure firebase-credentials.json exists in backend folder")
    print("2. Check the JSON file is valid (not corrupted)")
    print("3. Verify Firestore is enabled in Firebase Console")
    print("4. See FIREBASE_SETUP.md for setup instructions")
    print()
    sys.exit(1)
