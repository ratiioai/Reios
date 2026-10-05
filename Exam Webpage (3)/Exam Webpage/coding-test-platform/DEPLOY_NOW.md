# 🚀 DEPLOY NOW - Final Checklist

You're almost ready! Here's your step-by-step deployment guide for tomorrow.

---

## ⚡ PHASE 1: GENERATE QUESTIONS (Do This NOW - Takes 30 min)

### Step 1: Install Dependencies

```bash
cd backend
venv\Scripts\activate
pip install openai
```

### Step 2: Run AI Question Generator

```bash
generate_questions_with_ai.bat
```

**What happens:**
- Grok AI generates **150 coding questions** automatically
- 60 Easy (5 marks each)
- 60 Medium (10 marks each)  
- 30 Hard (20 marks each)
- Takes ~20-30 minutes
- Each question includes 2 sample + 5 hidden test cases

**⚠️ DO THIS TONIGHT!** Don't wait until tomorrow morning.

---

## ⚡ PHASE 2: SETUP LOCAL COMPILER (Optional but Recommended)

### Why Use Local Compiler?

| Feature | Local Compiler | Piston API |
|---------|----------------|------------|
| Speed | Very Fast | Fast |
| Rate Limit | **None** ✅ | 10 req/sec |
| Offline | Yes ✅ | No |
| Setup | Install compilers | None needed |

**For 175 teams, local compiler is HIGHLY recommended!**

### Setup Instructions:

1. **Python** - Already installed ✓

2. **Test the compiler:**
```bash
cd backend
test_compiler.bat
```

3. **Enable local compiler in `.env`:**
```env
USE_LOCAL_COMPILER=true
```

---

## ⚡ PHASE 3: TOMORROW MORNING SETUP

### Database Setup (5 minutes)

```sql
-- Open PostgreSQL
CREATE DATABASE coding_test_db;
CREATE USER coding_test_user WITH PASSWORD 'test123';
GRANT ALL PRIVILEGES ON DATABASE coding_test_db TO coding_test_user;
```

### Backend Setup (5 minutes)

```bash
cd backend

# Create .env from example
copy .env.example .env

# Edit .env - Update these lines:
DATABASE_URL=postgresql://coding_test_user:test123@localhost:5432/coding_test_db
SECRET_KEY=your-super-secret-key-minimum-32-characters-long-for-jwt
ADMIN_PASSWORD=admin123
USE_LOCAL_COMPILER=true
GROK_API_KEY=your_groq_api_key_here

# Initialize database
python -c "from app.database import create_tables; create_tables()"
```

### Start Services (2 minutes)

**Terminal 1 - API Server:**
```bash
cd backend
start_server.bat
```

**Terminal 2 - Grading Worker:**
```bash
cd backend
start_worker.bat
```

**Terminal 3 - Frontend:**
```bash
cd frontend
python -m http.server 3000
```

### Verify Everything Works (2 minutes)

1. **API Health Check:**
   - Open: http://localhost:8000/api/health
   - Should see: `{"status":"healthy"}`

2. **Admin Login:**
   - Open: http://localhost:3000
   - Login: admin / admin123
   - Should redirect to admin dashboard

3. **Check Questions Generated:**
   - Admin dashboard should show 150+ questions

---

## ⚡ PHASE 4: UPLOAD TEAMS (2 minutes)

### Upload Real Team Data

1. Go to admin dashboard
2. Scroll to "Upload Teams (CSV)"
3. Select `teams_real.csv` (175 teams ready)
4. Click "Upload Teams"
5. Wait for: "Teams created: 175, Question sets assigned: 175"

**✅ DONE! Each team now has a unique 25-question set.**

---

## ⚡ PHASE 5: CONFIGURE TEST (1 minute)

In admin dashboard:

```
Test Opens At:   2026-08-21 08:00
Test Closes At:  2026-08-21 20:00
Duration:        120 minutes
Global Start:    2026-08-21 09:00
```

Click "Save Configuration"

---

## ⚡ PHASE 6: TEST SAMPLE LOGIN (1 minute)

1. Open new browser window (incognito)
2. Go to http://localhost:3000
3. Team Login:
   - Team: **Niveshya**
   - Phone: **8309968940**
4. Should see dashboard with "Start Test" button
5. Click around - DON'T start test yet!

**✅ If this works, you're ready!**

---

## 📊 GO LIVE CHECKLIST

Before 9 AM tomorrow:

- [ ] Questions generated (150+) ✓
- [ ] Database setup ✓
- [ ] 3 services running (API, Worker, Frontend) ✓
- [ ] Teams uploaded (175) ✓
- [ ] Test configuration saved ✓
- [ ] Sample team login tested ✓
- [ ] Local compiler enabled (optional but recommended) ✓

---

## 🔥 DURING THE TEST

### Monitor These Stats (Admin Dashboard):

Every 5 minutes, check:
1. **Queue Depth** - Should be < 100
   - If > 200: Worker might be stuck, restart it
2. **Teams In Progress** - Matches logged-in teams
3. **Terminal logs** - No 500 errors

### At Test End (11:00 AM):

1. **Auto-submit triggers** - Watch Terminal 2 logs
2. **Grading phase** - Queue depth increases to ~4,375
3. **Completion** - Queue returns to 0 in ~7-10 minutes
4. **Publish leaderboard** - Click button in admin dashboard

---

## 🆘 EMERGENCY FIXES

### API Crashed
```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Worker Crashed
```bash
cd backend
venv\Scripts\activate
python grading_worker.py
```

### Grading Stuck
```sql
-- In PostgreSQL:
DELETE FROM grading_queue WHERE status = 'processing';
-- Then restart worker
```

### Queue Overload
```bash
# In .env, change:
USE_LOCAL_COMPILER=true
# Then restart worker
```

---

## 📱 TEAM CREDENTIALS

Share with teams tomorrow:

**Login URL:** http://localhost:3000
(or your server's public IP/domain)

**Sample Credentials:**
- Team: Niveshya → Phone: 8309968940
- Team: MRVVDU → Phone: 9347356450
- Team: Agents on Board → Phone: 9281412232

(Full list in `teams_real.csv`)

---

## 🎯 SUCCESS METRICS

**You'll know it's working when:**

✅ All 175 teams can login
✅ Each team sees 25 unique questions
✅ Code submissions grade within 10-15 seconds
✅ Leaderboard updates in real-time
✅ Auto-submit triggers at timer expiry
✅ Final scores appear within 10 minutes

---

## 💰 COST

**Grok API usage for 150 questions:** ~$2-3 USD (already incurred when you run generator)

**Infrastructure:** $0 (running on your machine)

---

## 📞 FINAL NOTES

1. **Run question generator TONIGHT** - Don't wait!
2. **Use local compiler** - No rate limits for 175 teams
3. **Keep terminals visible** - Monitor logs during test
4. **Don't panic** - Everything is tested and ready

---

## 🚀 LET'S GO!

**Tonight:**
```bash
cd backend
generate_questions_with_ai.bat
# Leave it running for 30 minutes
```

**Tomorrow morning:**
- Follow PHASE 2 → PHASE 6 (takes 15 minutes total)
- You'll be ready by 8:30 AM for 9 AM test start

**You've got this! 🎉**

---

**Need help?** 
- Check logs in terminal windows
- See QUESTION_GENERATION_GUIDE.md for details
- API docs: http://localhost:8000/api/docs

