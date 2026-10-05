# 🔥 Firebase Setup Guide - Easier than PostgreSQL!

## Why Firebase?

✅ **No database installation needed**
✅ **Cloud-based** - Works anywhere
✅ **Free tier** - More than enough for 175 teams
✅ **Real-time updates** - Built-in
✅ **5 minutes setup** vs PostgreSQL's complexity

---

## Step 1: Create Firebase Project (2 minutes)

1. Go to: https://console.firebase.google.com/
2. Click **"Add project"**
3. Project name: `coding-test-platform`
4. Click **Continue**
5. Disable Google Analytics (not needed)
6. Click **Create project**
7. Wait ~30 seconds
8. Click **Continue**

✅ Project created!

---

## Step 2: Enable Firestore Database (1 minute)

1. In Firebase Console, click **"Firestore Database"** in left menu
2. Click **"Create database"**
3. Select **"Start in production mode"**
4. Click **Next**
5. Choose location: **us-central** (or nearest to you)
6. Click **Enable**
7. Wait ~30 seconds

✅ Database ready!

---

## Step 3: Get Firebase Credentials (2 minutes)

1. Click the **⚙️ Gear icon** (top left) → **"Project settings"**
2. Scroll down to **"Your apps"** section
3. Click the **Web icon** `</>`
4. App nickname: `coding-test-web`
5. Click **"Register app"**
6. Copy the **firebaseConfig** object (looks like this):

```javascript
const firebaseConfig = {
  apiKey: "AIza...",
  authDomain: "coding-test-platform.firebaseapp.com",
  projectId: "coding-test-platform",
  storageBucket: "coding-test-platform.appspot.com",
  messagingSenderId: "123456789",
  appId: "1:123456789:web:abcdef"
};
```

7. Click **"Continue to console"**

---

## Step 4: Get Service Account Key (For Backend)

1. Still in **Project Settings**
2. Click **"Service accounts"** tab (top)
3. Click **"Generate new private key"**
4. Click **"Generate key"**
5. A JSON file downloads automatically
6. **IMPORTANT:** Rename it to: `firebase-credentials.json`
7. Move it to: `c:\Exam Webpage\coding-test-platform\backend\`

✅ Credentials downloaded!

---

## Step 5: Update Firestore Rules (Security)

1. Go to **Firestore Database** in left menu
2. Click **"Rules"** tab (top)
3. Replace the rules with:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Allow admin operations (backend only)
    match /{document=**} {
      allow read, write: if true;  // We'll secure with backend auth
    }
  }
}
```

4. Click **"Publish"**

✅ Rules updated!

---

## Step 6: Install Firebase SDK

In PowerShell:

```powershell
cd "c:\Exam Webpage\coding-test-platform\backend"
venv\Scripts\Activate.ps1
pip install firebase-admin
```

---

## Step 7: Test Firebase Connection

```powershell
python test_firebase_connection.py
```

Should see: **"✅ Firebase connection successful!"**

---

## Step 8: Create Questions & Teams

```powershell
# Create 150 questions
python create_questions_firebase.py

# Upload teams
python upload_teams_firebase.py
```

---

## Your Firebase URLs:

- **Console:** https://console.firebase.google.com/project/coding-test-platform
- **Firestore Data:** https://console.firebase.google.com/project/coding-test-platform/firestore

---

## Collections Structure:

```
coding-test-platform/
├── admins/           # Admin users
├── teams/            # Team accounts
├── questions/        # Question bank
├── test_sessions/    # Active test sessions
├── submissions/      # Code submissions
├── grading_results/  # Grading outcomes
└── test_config/      # Test configuration
```

---

## Advantages Over PostgreSQL:

1. ✅ **No installation** - Cloud-based
2. ✅ **Auto-scaling** - Handles any load
3. ✅ **Real-time** - Live leaderboard updates
4. ✅ **Backups** - Automatic
5. ✅ **Free tier** - 50K reads/day (more than enough)
6. ✅ **Works anywhere** - No localhost dependency

---

## Cost:

**Firebase Free Tier (Spark Plan):**
- 50,000 document reads/day
- 20,000 document writes/day
- 1GB stored data

**Your usage (175 teams, 2-hour test):**
- ~5,000 reads
- ~3,000 writes
- ~100MB data

**Cost: $0** ✅

---

## Next Steps:

1. Create Firebase project (above)
2. Download credentials
3. Run: `python create_questions_firebase.py`
4. Start services tomorrow morning
5. Launch test!

---

**Much easier than PostgreSQL! Let me know when you have the credentials ready.** 🚀

