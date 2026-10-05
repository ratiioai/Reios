# Quick Start Guide - Testing Tomorrow

## Prerequisites

- Python 3.11+ installed
- PostgreSQL 15+ installed and running
- Git installed

## Setup (30 minutes)

### 1. Database Setup

```sql
-- Open PostgreSQL (psql or pgAdmin)
CREATE DATABASE coding_test_db;
CREATE USER coding_test_user WITH PASSWORD 'your_password_here';
GRANT ALL PRIVILEGES ON DATABASE coding_test_db TO coding_test_user;
```

### 2. Environment Configuration

```bash
cd backend
copy .env.example .env
```

Edit `.env` file:
```env
DATABASE_URL=postgresql://coding_test_user:your_password_here@localhost:5432/coding_test_db
SECRET_KEY=your_secret_key_minimum_32_characters_long_for_security
ADMIN_PASSWORD=admin123
ADMIN_EMAIL=admin@test.com
PISTON_API_URL=https://emkc.org/api/v2/piston
ENVIRONMENT=development
DEBUG=true
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### 3. Install Dependencies

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Initialize Database

```bash
python -c "from app.database import create_tables; create_tables()"
```

## Running the Platform

### Option 1: Using Batch Scripts (Windows)

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

### Option 2: Manual Commands

**Terminal 1 - API Server:**
```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Grading Worker:**
```bash
cd backend
venv\Scripts\activate
python grading_worker.py
```

## Quick Test Checklist

### 1. API Health Check
```bash
curl http://localhost:8000/api/health
```

Expected: `{"status":"healthy","service":"Coding Test Platform",...}`

### 2. Admin Login

**Request:**
```bash
curl -X POST http://localhost:8000/api/auth/admin/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"admin123\"}"
```

**Expected:** JWT token response
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "role": "admin"
}
```

Save the token for next steps!

### 3. Create Test Questions

```bash
curl -X POST http://localhost:8000/api/admin/questions \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d @- << 'EOF'
{
  "title": "Two Sum",
  "difficulty": "easy",
  "prompt_markdown": "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.",
  "starter_code_python": "def two_sum(nums, target):\n    pass",
  "time_limit_seconds": 5,
  "memory_limit_mb": 256,
  "sample_test_cases": [
    {
      "input_data": "[2,7,11,15]\n9",
      "expected_output": "[0,1]",
      "explanation": "nums[0] + nums[1] = 2 + 7 = 9",
      "order": 0
    }
  ],
  "hidden_test_cases": [
    {
      "input_data": "[3,2,4]\n6",
      "expected_output": "[1,2]",
      "order": 0
    },
    {
      "input_data": "[3,3]\n6",
      "expected_output": "[0,1]",
      "order": 1
    }
  ]
}
EOF
```

**Repeat for at least 175 questions** (10 easy, 10 medium, 5 hard per team × 175 teams = need bank of 175+ unique questions)

### 4. Upload Teams CSV

Create `teams.csv`:
```csv
team_name,leader_name,leader_phone,member_2,member_3,member_4,college
Team Alpha,John Doe,9876543210,Jane Smith,Bob Lee,,MIT
Team Beta,Alice Johnson,9876543211,Charlie Brown,,,Stanford
```

Upload:
```bash
curl -X POST http://localhost:8000/api/admin/teams/upload-csv \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -F "file=@teams.csv"
```

### 5. Configure Test

```bash
curl -X POST http://localhost:8000/api/admin/test/configure \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "test_open_at": "2026-08-20T08:00:00Z",
    "test_close_at": "2026-08-20T20:00:00Z",
    "duration_minutes": 120,
    "synchronized_start": true,
    "global_start_time": "2026-08-20T09:00:00Z",
    "allow_team_view_leaderboard": false
  }'
```

### 6. Test Team Flow

**Team Login:**
```bash
curl -X POST http://localhost:8000/api/auth/team/login \
  -H "Content-Type: application/json" \
  -d '{"team_name":"Team Alpha","leader_phone":"9876543210"}'
```

**Start Test:**
```bash
curl -X POST http://localhost:8000/api/teams/test/start \
  -H "Authorization: Bearer TEAM_TOKEN"
```

**Get Questions:**
```bash
curl http://localhost:8000/api/teams/questions \
  -H "Authorization: Bearer TEAM_TOKEN"
```

**Submit Code:**
```bash
curl -X POST http://localhost:8000/api/teams/submissions/1/submit \
  -H "Authorization: Bearer TEAM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "def two_sum(nums, target):\n    hash_map = {}\n    for i, num in enumerate(nums):\n        complement = target - num\n        if complement in hash_map:\n            return [hash_map[complement], i]\n        hash_map[num] = i",
    "language": "python"
  }'
```

**Check Grading Status:**
```bash
curl http://localhost:8000/api/teams/submissions/SUBMISSION_ID/status \
  -H "Authorization: Bearer TEAM_TOKEN"
```

## Troubleshooting

### Database Connection Error
```
Error: could not connect to server
```
**Fix:** Ensure PostgreSQL is running and credentials in `.env` are correct

### Import Error
```
ModuleNotFoundError: No module named 'app'
```
**Fix:** Make sure you're in the `backend` directory and virtual environment is activated

### Piston API Error
```
Piston API error 429
```
**Fix:** Rate limit exceeded. Wait 10 seconds or check worker is respecting 10 req/sec limit

### No Questions Assigned
```
Error: Not enough questions in bank
```
**Fix:** Create at least 175 questions (combination of easy/medium/hard) before uploading teams

## API Documentation

Once server is running, visit:
- **Swagger UI:** http://localhost:8000/api/docs
- **ReDoc:** http://localhost:8000/api/redoc

## Monitoring

### Check Queue Depth
```bash
curl http://localhost:8000/api/admin/queue/stats \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

### View Leaderboard
```bash
curl http://localhost:8000/api/admin/leaderboard \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

### Check Test Status
```bash
curl http://localhost:8000/api/admin/test/status \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

## Production Checklist

Before going live tomorrow:

- [ ] Database backed up
- [ ] At least 175 questions in bank (with proper distribution)
- [ ] All 175 teams uploaded and assigned questions
- [ ] Test configuration set (start time, duration)
- [ ] Both server and worker running
- [ ] Admin login working
- [ ] Sample team can login and see questions
- [ ] Sample submission grades correctly
- [ ] Leaderboard calculates ranks properly
- [ ] Environment variables secured (strong SECRET_KEY, ADMIN_PASSWORD)

## Emergency Contacts

- **Backend Issues:** Check logs in terminal
- **Database Issues:** Check PostgreSQL logs
- **Grading Issues:** Check worker terminal for errors
- **API Docs:** http://localhost:8000/api/docs

## Performance Notes

- **Concurrent Users:** System tested for 175 teams
- **Grading Speed:** ~10 submissions per second (Piston limit)
- **Auto-Submit:** Staggered over 35 seconds (25 teams per batch)
- **Grading Time:** 4,375 submissions complete in ~7-10 minutes

Good luck with tomorrow's test! 🚀
