# 🚀 TOMORROW'S TEST - COMPLETE SETUP GUIDE

**Time Required:** 1-2 hours for full setup
**Goal:** Have 175 teams ready to test with working platform

---

## ⚡ EMERGENCY QUICK START (30 minutes)

### Step 1: Database Setup (5 minutes)

Open PostgreSQL command prompt or pgAdmin:

```sql
CREATE DATABASE coding_test_db;
CREATE USER coding_test_user WITH PASSWORD 'test123';
GRANT ALL PRIVILEGES ON DATABASE coding_test_db TO coding_test_user;
\c coding_test_db
GRANT ALL ON SCHEMA public TO coding_test_user;
```

### Step 2: Backend Setup (10 minutes)

```bash
cd "c:\Exam Webpage\coding-test-platform\backend"

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
copy .env.example .env
```

Edit `.env` and update:
```env
DATABASE_URL=postgresql://coding_test_user:test123@localhost:5432/coding_test_db
SECRET_KEY=your-very-long-secret-key-at-least-32-characters-for-jwt-tokens
ADMIN_PASSWORD=admin123
```

### Step 3: Initialize Database (2 minutes)

```bash
python -c "from app.database import create_tables; create_tables()"
```

### Step 4: Create Sample Questions (10 minutes)

Save this as `create_questions.py` in backend folder:

```python
import requests

API_BASE = "http://localhost:8000"

# Login as admin
response = requests.post(f"{API_BASE}/api/auth/admin/login", json={
    "username": "admin",
    "password": "admin123"
})
token = response.json()["access_token"]

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Sample questions
questions = [
    # Easy questions
    {
        "title": "Sum of Two Numbers",
        "difficulty": "easy",
        "prompt_markdown": "Write a function that takes two numbers and returns their sum.",
        "starter_code_python": "def sum_two(a, b):\n    pass",
        "time_limit_seconds": 5,
        "memory_limit_mb": 256,
        "sample_test_cases": [
            {"input_data": "2\n3", "expected_output": "5", "explanation": "2 + 3 = 5", "order": 0}
        ],
        "hidden_test_cases": [
            {"input_data": "10\n20", "expected_output": "30", "order": 0},
            {"input_data": "-5\n5", "expected_output": "0", "order": 1}
        ]
    },
    {
        "title": "Check Even Number",
        "difficulty": "easy",
        "prompt_markdown": "Write a function that returns True if a number is even, False otherwise.",
        "starter_code_python": "def is_even(n):\n    pass",
        "time_limit_seconds": 5,
        "memory_limit_mb": 256,
        "sample_test_cases": [
            {"input_data": "4", "expected_output": "True", "explanation": "4 is even", "order": 0}
        ],
        "hidden_test_cases": [
            {"input_data": "7", "expected_output": "False", "order": 0},
            {"input_data": "0", "expected_output": "True", "order": 1}
        ]
    },
    # Add 8 more easy, 10 medium, 5 hard questions here...
]

# Create questions
for q in questions:
    response = requests.post(f"{API_BASE}/api/admin/questions", json=q, headers=headers)
    print(f"Created: {q['title']} - {response.status_code}")

print("\n✅ Questions created! You need at least 175 unique questions total.")
print("   For 175 teams with unique sets, create more questions now.")
```

### Step 5: Start Services (3 minutes)

**Terminal 1 - Backend API:**
```bash
cd backend
start_server.bat
```

**Terminal 2 - Grading Worker:**
```bash
cd backend
start_worker.bat
```

**Terminal 3 - Frontend (Simple HTTP Server):**
```bash
cd frontend
python -m http.server 3000
```

### Step 6: Upload Teams CSV (2 minutes)

Create `teams_175.csv`:
```csv
team_name,leader_name,leader_phone,member_2,member_3,member_4,college
Team 001,Leader 001,9876543210,Member A,Member B,Member C,College A
Team 002,Leader 002,9876543211,Member D,Member E,Member F,College B
...
Team 175,Leader 175,9876543384,Member X,Member Y,Member Z,College Z
```

**Quick CSV Generator Script (Python):**
```python
with open('teams_175.csv', 'w') as f:
    f.write('team_name,leader_name,leader_phone,member_2,member_3,member_4,college\n')
    for i in range(1, 176):
        f.write(f'Team {i:03d},Leader {i:03d},{9876543210 + i},Member A,Member B,Member C,College A\n')
```

Upload via admin dashboard at `http://localhost:3000/admin-dashboard.html`

---

## 🧪 TESTING CHECKLIST

### Pre-Test Validation

- [ ] **Backend Health Check**
  ```bash
  curl http://localhost:8000/api/health
  # Should return: {"status":"healthy"}
  ```

- [ ] **Admin Login Works**
  - Go to: `http://localhost:3000`
  - Click "Admin Login"
  - Username: `admin`, Password: `admin123`
  - Should redirect to admin dashboard

- [ ] **Questions Created**
  - Admin dashboard shows questions
  - At least 175 questions required for unique sets
  - Mix of easy (10), medium (10), hard (5) per team

- [ ] **Teams Uploaded**
  - Upload CSV shows success
  - All 175 teams created
  - Question sets assigned: 175

- [ ] **Test Configuration Set**
  - Test opens: Tomorrow 8 AM
  - Test closes: Tomorrow 8 PM
  - Duration: 120 minutes
  - Global start: Tomorrow 9 AM

- [ ] **Sample Team Login**
  - Go to team login
  - Team: `Team 001`, Phone: `9876543211`
  - Should see "Start Test" button

- [ ] **Sample Submission Flow**
  1. Team logs in
  2. Starts test
  3. Sees 25 questions
  4. Submits one question
  5. Grading worker processes it
  6. Score appears

- [ ] **Grading Worker Running**
  - Terminal 2 shows "Grading queue worker" messages
  - Processes submissions

- [ ] **Leaderboard Works**
  - Admin can view leaderboard
  - Ranks calculated correctly
  - Tiebreaker (time) works

---

## 🔥 CRITICAL ISSUES TO CHECK

### Issue 1: Not Enough Questions

**Symptom:** "Error: Not enough questions in bank"

**Fix:** Create at least 175 questions with proper distribution:
- 1750 easy questions (175 teams × 10 each)
- 1750 medium questions (175 teams × 10 each)
- 875 hard questions (175 teams × 5 each)

OR ensure collision detection allows question reuse (current design allows some overlap).

### Issue 2: Grading Queue Stuck

**Symptom:** Submissions stay "grading" forever

**Fix:**
1. Check worker terminal for errors
2. Restart worker: `Ctrl+C` then `start_worker.bat`
3. Check Piston API is accessible:
   ```bash
   curl https://emkc.org/api/v2/piston/runtimes
   ```

### Issue 3: Database Connection Failed

**Symptom:** "could not connect to server"

**Fix:**
1. Ensure PostgreSQL is running
2. Check DATABASE_URL in .env
3. Test connection:
   ```bash
   psql -U coding_test_user -d coding_test_db -h localhost
   ```

### Issue 4: Token Expired

**Symptom:** "Invalid or expired token"

**Fix:** 
- Tokens last 8 hours (480 minutes)
- Re-login if expired
- Check SECRET_KEY is set in .env

---

## 📊 MONITORING DURING TEST

### Every 5 Minutes Check:

1. **Queue Depth** (should be < 100)
   - Admin dashboard shows current queue
   - If > 200, submissions are backing up

2. **Active Sessions** (should match logged-in teams)
   - Check "Teams In Progress" stat

3. **Worker Status**
   - Terminal 2 should show processing messages
   - "Graded submission X" every few seconds

4. **Error Logs**
   - Terminal 1 (API) - watch for 500 errors
   - Terminal 2 (Worker) - watch for Piston errors

### At Timer Expiry (2 hours after start):

1. **Auto-Submit Triggers**
   - Terminal logs show "Auto-submitted 175 teams"
   - Takes 35 seconds (staggered)

2. **Grading Rush**
   - Queue jumps to ~4,375 submissions
   - Worker processes at 10/sec
   - Completes in ~7-10 minutes

3. **Leaderboard Updates**
   - Ranks recalculate as grading completes
   - Final rankings ready ~10 min after expiry

---

## 🆘 EMERGENCY PROCEDURES

### If Backend Crashes:

```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### If Worker Crashes:

```bash
cd backend
venv\Scripts\activate
python grading_worker.py
```

### If Database Corrupted:

```bash
# DON'T DO THIS IF TEST IS LIVE!
python -c "from app.database import drop_tables, create_tables; drop_tables(); create_tables()"
```

### If Grading Stuck:

```sql
-- Connect to PostgreSQL
DELETE FROM grading_queue WHERE status = 'processing';
-- Then restart worker
```

---

## 📈 PERFORMANCE EXPECTATIONS

| Event | Expected Behavior | Time |
|-------|------------------|------|
| 175 teams login | All succeed | < 1 minute |
| 175 teams start test | All start within window | < 30 seconds |
| Single submission grading | Complete | 5-15 seconds |
| Auto-submit (175 teams) | Staggered batch | 35 seconds |
| Full grading (4,375 subs) | Complete | 7-10 minutes |
| Leaderboard recalculation | Complete | < 1 second |

---

## ✅ FINAL PRE-LAUNCH CHECKLIST

**30 Minutes Before Test:**

- [ ] All 3 terminals running (API, Worker, Frontend)
- [ ] Health check passes
- [ ] Admin login works
- [ ] Sample team login works
- [ ] Database backed up (pg_dump)
- [ ] 175 teams uploaded
- [ ] Questions verified (at least 175 total)
- [ ] Test configuration set
- [ ] Leaderboard NOT published yet
- [ ] Auto-submit time verified

**At Test Start:**

- [ ] Monitor dashboard for logins
- [ ] Check queue depth stays manageable
- [ ] Watch for errors in terminals

**At Test End:**

- [ ] Wait for auto-submit (watch logs)
- [ ] Wait for grading complete (~10 min)
- [ ] Publish leaderboard
- [ ] Export results CSV

---

## 🎯 ACCESS URLS

| Service | URL | Credentials |
|---------|-----|-------------|
| API Health | http://localhost:8000/api/health | - |
| API Docs | http://localhost:8000/api/docs | - |
| Team Login | http://localhost:3000 | team_name + phone |
| Admin Login | http://localhost:3000 | admin / admin123 |
| Team Dashboard | http://localhost:3000/team-dashboard.html | After login |
| Admin Dashboard | http://localhost:3000/admin-dashboard.html | After login |

---

## 📞 SUPPORT CONTACTS

**If something breaks:**

1. Check terminal logs first
2. Check QUICK_START.md troubleshooting section
3. Check API docs: http://localhost:8000/api/docs
4. Restart services in this order: Worker → API → Frontend

---

## 💡 TIPS FOR SUCCESS

1. **Test with 5 sample teams first** before inviting all 175
2. **Keep terminals visible** to catch errors early
3. **Don't refresh during submission** - could lose work
4. **Auto-submit is your friend** - teams don't need to click submit
5. **Queue depth is critical** - if > 500, something's wrong
6. **Piston rate limit is hard** - worker respects 10 req/sec automatically

---

**You're ready! Everything is built and tested. Just follow this guide tomorrow. Good luck! 🚀**

Need help? All APIs are documented at http://localhost:8000/api/docs
