# ✅ SPEC INDUSTRY HACK - PLATFORM READY!

## 🎯 STATUS: READY TO USE

The platform is now live and ready for your hackathon!

---

## 🌐 Access URLs

- **Frontend (Login)**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## 🔐 Login Credentials

### Admin Login
- **Username**: `admin`
- **Password**: `admin123`
- **Access**: Full control panel, leaderboard, team management

### Team Login (175 Teams Ready)
- **Username**: Team Name (e.g., "Niveshya", "MRVVDU", "Agents on Board")
- **Password**: Leader's 10-digit phone number (e.g., "8309968940", "9347356450")
- **Access**: Test dashboard, 25 unique questions, code editor

---

## 📊 Platform Features

✅ **Database**: SQLite (150 questions created)
✅ **Questions**: 60 Easy (5 marks) + 60 Medium (10 marks) + 30 Hard (20 marks)
✅ **Teams**: 175 teams from `teams_real.csv` (ready to import)
✅ **Grading**: Local compiler enabled (Python, C++, Java, JavaScript)
✅ **Test Duration**: 2 hours (120 minutes)
✅ **Auto-Submit**: Enabled when time expires
✅ **Leaderboard**: Real-time rankings
✅ **UI**: Professional branding - "SPEC Industry Hack - Round 1"

---

## 🚀 Quick Start Steps

### 1. Upload Teams (Do This First!)
1. Go to http://localhost:3000
2. Login as admin (`admin` / `admin123`)
3. Click "Upload Teams (CSV)"
4. Select file: `backend/teams_real.csv`
5. Click "Upload Teams"
6. Confirm: 175 teams created

### 2. Verify Questions
- Questions already created: 150 total
- Each team will get 25 unique questions (10 easy + 10 medium + 5 hard)
- Questions auto-assigned when teams are imported

### 3. Configure Test Timing (Optional)
- Set test open/close times
- Configure global start time
- Or leave open for teams to start anytime

### 4. Test Login
- Open http://localhost:3000 in another browser/incognito
- Try team login: `Niveshya` / `8309968940`
- Verify test dashboard loads

---

## 📁 Important Files

### Teams Data
- **Location**: `backend/teams_real.csv`
- **Teams**: 175 registered teams with actual data
- **Format**: team_name | leader_name | leader_phone | members | college

### Backend
- **Main API**: `backend/app/main.py`
- **Database**: `backend/coding_test.db` (SQLite)
- **Config**: `backend/.env`
- **Questions**: Already in database (150 questions)

### Frontend
- **Login Page**: `frontend/index.html`
- **Team Dashboard**: `frontend/team-dashboard.html`
- **Admin Panel**: `frontend/admin-dashboard.html`

---

## 🔧 If You Need to Restart

### Stop Services
Close the two command windows that opened (Backend Server and Frontend Server)

### Restart Platform
```bat
cd "c:\Exam Webpage\coding-test-platform"
.\START_PLATFORM.bat
```

Or manually:
```bat
# Terminal 1 - Backend
cd backend
venv\Scripts\activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend
cd frontend
python -m http.server 3000

# Terminal 3 - Grading Worker (optional, for background grading)
cd backend
venv\Scripts\activate
python grading_worker.py
```

---

## 🎓 Team Instructions (Share This)

### For Participants:

1. **Go to**: http://localhost:3000
2. **Login with**:
   - Username: Your Team Name (exactly as registered)
   - Password: Team Leader's phone number (10 digits)
3. **Click**: "Start Test"
4. **Solve**: 25 questions (2 hours)
5. **Submit**: Click "Submit Test" when done (or auto-submits at timer expiry)

### Test Rules:
- ⏰ **Time**: 120 minutes (2 hours)
- 📝 **Questions**: 25 unique per team (10 easy, 10 medium, 5 hard)
- 💻 **Languages**: Python, C++, Java, JavaScript
- ✅ **Grading**: All test cases must pass for full marks
- 🔒 **Autosave**: Code saves automatically
- 🚫 **No Resubmit**: Once submitted, cannot change answers

---

## 📈 Admin Features

### Dashboard (http://localhost:3000 → Admin Login)
- View real-time stats (teams submitted, in progress, not started)
- Monitor grading queue depth
- Upload team CSV
- Configure test timing
- View full leaderboard
- Export results (future feature)

### During Contest:
- Monitor live submissions
- Track grading queue
- View team progress
- Check leaderboard rankings

### After Contest:
- Publish leaderboard to teams
- Review individual submissions
- Override grades if needed
- Export final results

---

## ⚠️ Important Notes

### Before Launch:
- ✅ Upload teams CSV
- ✅ Verify questions (already done - 150 questions)
- ✅ Test login with sample team
- ✅ Configure test timing
- ⚠️ Start grading worker if using background grading

### During Contest:
- Keep backend and frontend servers running
- Don't close command windows
- Monitor admin dashboard for issues
- Grading happens automatically (local compiler is fast!)

### Security:
- This is local/LAN setup (localhost)
- For external access, need proper deployment
- Default admin password is simple - change if exposed to network

---

## 🐛 Troubleshooting

### Teams can't login?
- Verify CSV was uploaded successfully
- Check admin dashboard shows correct team count
- Ensure username matches team_name exactly (case-sensitive)
- Password must be 10-digit phone number

### Questions not showing?
- Verify 150 questions exist: Run `backend/verify_questions.py`
- Check questions are assigned: View admin dashboard stats

### Server not starting?
- Check ports 3000 and 8000 are not in use
- Verify virtual environment is activated
- Check backend/.env file exists

### Grading stuck?
- Local compiler should be instant
- Check USE_LOCAL_COMPILER=true in .env
- Restart backend server if needed

---

## 📞 Support Commands

### Check Database Status
```bat
cd backend
venv\Scripts\python.exe -c "from app.database import SessionLocal; from app.models import Question, Team; db = SessionLocal(); print(f'Questions: {db.query(Question).count()}'); print(f'Teams: {db.query(Team).count()}'); db.close()"
```

### Verify Questions
```bat
cd backend
venv\Scripts\python.exe verify_questions.py
```

### Create More Questions (if needed)
```bat
cd backend
venv\Scripts\python.exe create_sample_questions_fast.py
```

---

## 🎉 You're All Set!

The platform is production-ready for your hackathon. All core features are working:
- ✅ 175 teams ready to import
- ✅ 150 diverse coding questions
- ✅ Professional UI with branding
- ✅ Real-time grading
- ✅ Leaderboard system
- ✅ Auto-submit on timer expiry
- ✅ Multiple programming languages

**Next Step**: Upload `teams_real.csv` via admin dashboard and you're ready to launch!

Good luck with SPEC Industry Hack Round 1! 🚀
