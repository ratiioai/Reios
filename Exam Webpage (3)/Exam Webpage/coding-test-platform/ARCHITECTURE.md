# System Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js)                      │
│  ┌────────────────┐              ┌──────────────────┐          │
│  │  Team Portal   │              │  Admin Dashboard │          │
│  │  - Code Editor │              │  - CSV Upload    │          │
│  │  - Timer       │              │  - Question CRUD │          │
│  │  - Questions   │              │  - Leaderboard   │          │
│  └────────┬───────┘              └────────┬─────────┘          │
└───────────┼──────────────────────────────┼────────────────────┘
            │                              │
            │         HTTPS/JWT            │
            │                              │
┌───────────▼──────────────────────────────▼────────────────────┐
│                    API LAYER (FastAPI)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Auth Routes  │  │ Team Routes  │  │ Admin Routes │       │
│  │ - Login      │  │ - Start Test │  │ - Upload CSV │       │
│  │ - JWT Verify │  │ - Submit     │  │ - Override   │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
└─────────┼──────────────────┼──────────────────┼───────────────┘
          │                  │                  │
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼───────────────┐
│                   BUSINESS LOGIC LAYER                        │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │ Auth Service   │  │ Grading Queue  │  │ Leaderboard   │  │
│  │ - Hash Phone   │  │ - FIFO Queue   │  │ - Rank Calc   │  │
│  │ - JWT Tokens   │  │ - Rate Limit   │  │ - Tiebreaker  │  │
│  └────────────────┘  └────────┬───────┘  └───────────────┘  │
│                                │                              │
│  ┌────────────────┐  ┌────────▼───────┐  ┌───────────────┐  │
│  │ CSV Import     │  │ Grading Worker │  │ Export Service│  │
│  │ - Validate     │  │ - Piston API   │  │ - CSV/Excel   │  │
│  │ - Assign Qs    │  │ - Test Cases   │  │ - PDF         │  │
│  └────────────────┘  └────────┬───────┘  └───────────────┘  │
└───────────────────────────────┼──────────────────────────────┘
                                │
                                │
┌───────────────────────────────▼──────────────────────────────┐
│                   DATA PERSISTENCE LAYER                     │
│  ┌────────────────┐              ┌──────────────────┐       │
│  │  PostgreSQL    │              │  Redis (Optional)│       │
│  │  - Teams       │              │  - Grading Queue │       │
│  │  - Questions   │              │  - LB Cache      │       │
│  │  - Submissions │              │                  │       │
│  │  - Results     │              │                  │       │
│  └────────────────┘              └──────────────────┘       │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                   EXTERNAL SERVICES                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Piston API (Code Execution Sandbox)                   │ │
│  │  https://emkc.org/api/v2/piston                        │ │
│  │  - Isolated containers                                  │ │
│  │  - 10 req/sec rate limit                               │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## Submission Flow (Critical Path)

```
┌──────────────────────────────────────────────────────────────┐
│ TEAM WRITES CODE IN EDITOR                                   │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ Autosave (every 30 sec)
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ POST /api/teams/submissions/:id/autosave                     │
│ - Store code with is_final = false                          │
│ - NO grading triggered                                       │
│ - Recovery mechanism for crashes                            │
└──────────────────────────────────────────────────────────────┘

                 ┌───────────────┐
                 │ Team clicks   │
                 │ "Submit"      │
                 └───────┬───────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ POST /api/teams/submissions/:id/submit                       │
│ 1. Validate: test in progress? question assigned?           │
│ 2. Check idempotency: already submitted?                    │
│ 3. Insert Submission (is_final = true)                      │
│ 4. Enqueue to grading queue                                 │
│ 5. Return 202 Accepted (with submission_id)                 │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ GRADING QUEUE (Redis Sorted Set or DB Table)                │
│ - FIFO ordering by timestamp                                │
│ - Deduplication by submission_id                            │
│ - Queue depth monitoring                                     │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ Worker polls queue
                 │ (Rate limited: 10/sec)
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ GRADING WORKER                                               │
│ 1. Pop submission from queue (atomic)                       │
│ 2. Load hidden test cases                                   │
│ 3. For each test case:                                      │
│    a. Call Piston API with input                            │
│    b. Compare output (strip whitespace)                     │
│    c. Record pass/fail                                      │
│ 4. Calculate marks: (passed/total) × question.marks         │
│ 5. Store GradingResult                                      │
│ 6. Update TestSession.total_score                           │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ HTTPS POST
                 │ Rate limited: 10 req/sec
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ PISTON API                                                   │
│ POST https://emkc.org/api/v2/piston/execute                 │
│ {                                                            │
│   "language": "python",                                      │
│   "version": "3.11",                                         │
│   "files": [{"content": "<user_code>"}],                    │
│   "stdin": "<test_input>",                                   │
│   "run_timeout": 5000,  // 5 seconds                        │
│   "run_memory_limit": 268435456  // 256 MB                  │
│ }                                                            │
│                                                              │
│ Response:                                                    │
│ {                                                            │
│   "run": {                                                   │
│     "stdout": "output",                                      │
│     "stderr": "",                                            │
│     "code": 0                                                │
│   }                                                          │
│ }                                                            │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ Result returned
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ STORE GRADING RESULT                                         │
│ - marks_awarded                                              │
│ - passed_tests / total_tests                                │
│ - execution_time_ms                                          │
│ - test_results JSON (detailed per-case)                     │
│ - error_output (if any)                                     │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ UPDATE LEADERBOARD                                           │
│ 1. Recalculate TestSession.total_score                      │
│ 2. Recalculate ranks:                                       │
│    ORDER BY total_score DESC, time_taken_seconds ASC        │
│ 3. Cache top 100 in Redis (optional)                        │
└──────────────────────────────────────────────────────────────┘
```

---

## Auto-Submit at Timer Expiry

```
┌──────────────────────────────────────────────────────────────┐
│ SCHEDULED JOB (runs every 10 seconds)                        │
│ Query: TestSession.status = IN_PROGRESS                     │
│        AND test_started_at + duration < NOW()               │
│                                                              │
│ Found: 175 teams with expired timers                         │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGGERED AUTO-SUBMIT                                        │
│                                                              │
│ Batch 1: Teams 1-25    → Process → Wait 5 sec               │
│ Batch 2: Teams 26-50   → Process → Wait 5 sec               │
│ Batch 3: Teams 51-75   → Process → Wait 5 sec               │
│ Batch 4: Teams 76-100  → Process → Wait 5 sec               │
│ Batch 5: Teams 101-125 → Process → Wait 5 sec               │
│ Batch 6: Teams 126-150 → Process → Wait 5 sec               │
│ Batch 7: Teams 151-175 → Process                            │
│                                                              │
│ Total time: 35 seconds (7 batches × 5 sec)                  │
│                                                              │
│ For each team:                                               │
│ 1. Fetch all autosaved submissions (is_final = false)       │
│ 2. Mark as is_final = true (if no final submit exists)      │
│ 3. Set TestSession.status = AUTO_SUBMITTED                  │
│ 4. Set TestSession.submitted_at = expired_at                │
│ 5. Calculate time_taken_seconds                             │
│ 6. Enqueue all 25 submissions to grading queue              │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ GRADING QUEUE (now has 4,375 submissions)                   │
│                                                              │
│ Worker processes at 10 req/sec                              │
│ Time to complete: 4,375 / 10 = 437.5 seconds = ~7.3 min     │
│                                                              │
│ Teams see "Grading in progress..." with queue position      │
└──────────────────────────────────────────────────────────────┘
```

**Why Staggered?**
- Prevents 4,375 submissions hitting queue instantly
- Avoids database write spike
- Spreads load over 35 seconds vs. 1 second

---

## Database Schema Relationships

```
┌──────────────┐
│    Admin     │
│──────────────│
│ id           │◄──────────────┐
│ username     │               │
│ email        │               │
│ hashed_pwd   │               │
└──────────────┘               │
                               │
                               │
┌──────────────┐               │
│    Team      │               │
│──────────────│               │
│ id           │◄──────────────┼───────┐
│ team_name    │               │       │
│ leader_phone │               │       │
│ leader_phone │               │       │
│   _hash      │               │       │
│ member_2..4  │               │       │
└──────┬───────┘               │       │
       │                       │       │
       │                       │       │
       ▼                       │       │
┌──────────────┐               │       │
│ TestSession  │               │       │
│──────────────│               │       │
│ id           │               │       │
│ team_id      │───────────────┘       │
│ started_at   │                       │
│ submitted_at │                       │
│ total_score  │                       │
│ rank         │                       │
│ status       │                       │
└──────────────┘                       │
                                       │
┌──────────────┐                       │
│  Question    │                       │
│──────────────│                       │
│ id           │◄──────────┐           │
│ title        │           │           │
│ difficulty   │           │           │
│ prompt_md    │           │           │
│ starter_code │           │           │
│ marks        │           │           │
└──────┬───────┘           │           │
       │                   │           │
       │                   │           │
       ├───────────────────┼───────────┤
       ▼                   ▼           ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ SampleTest   │  │TeamQuestion  │  │ Submission   │
│   Case       │  │ Assignment   │  │──────────────│
│──────────────│  │──────────────│  │ id           │
│ question_id  │  │ team_id      │  │ team_id      │
│ input        │  │ question_id  │  │ question_id  │
│ expected_out │  │ position     │  │ code         │
└──────────────┘  └──────────────┘  │ language     │
                                    │ is_final     │
┌──────────────┐                    └──────┬───────┘
│ HiddenTest   │                           │
│   Case       │                           │
│──────────────│                           ▼
│ question_id  │                    ┌──────────────┐
│ input        │                    │ GradingResult│
│ expected_out │                    │──────────────│
└──────────────┘                    │ submission_id│
                                    │ marks_awarded│
┌──────────────┐                    │ passed_tests │
│  AuditLog    │                    │ total_tests  │
│──────────────│                    │ test_results │
│ id           │                    │ error_output │
│ admin_id     │────────────────────│ overridden   │
│ action       │                    │   _by_admin  │
│ object_type  │                    └──────────────┘
│ object_id    │
│ old_value    │
│ new_value    │
│ reason       │
└──────────────┘
```

---

## Technology Stack

### Backend
- **Framework:** FastAPI 0.110+
- **ORM:** SQLAlchemy 2.0+
- **Database:** PostgreSQL 15+
- **Auth:** python-jose (JWT), passlib (bcrypt)
- **Async:** asyncio, httpx
- **Queue:** Redis (optional) or SQLAlchemy
- **Scheduler:** APScheduler

### Frontend
- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript 5+
- **Styling:** Tailwind CSS 3+
- **Editor:** Monaco Editor (VS Code editor)
- **HTTP Client:** axios
- **State:** React hooks (no Redux needed)

### External Services
- **Code Execution:** Piston API (https://emkc.org/api/v2/piston)
- **Monitoring:** Sentry (error tracking)
- **Deployment:**
  - Backend: Railway or Render
  - Frontend: Vercel
  - Database: Railway PostgreSQL

### Development Tools
- **Load Testing:** Locust
- **API Docs:** FastAPI auto-generated (Swagger/ReDoc)
- **Linting:** ESLint (frontend), ruff (backend)
- **Formatting:** Prettier (frontend), black (backend)

---

## Security Architecture

### Authentication Flow

```
┌──────────────────────────────────────────────────────────────┐
│ TEAM LOGIN                                                   │
│ POST /api/auth/team/login                                    │
│ { team_name, leader_phone }                                  │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ 1. Normalize team_name (trim, lowercase)                    │
│ 2. Find team in database                                     │
│ 3. Verify phone: bcrypt.verify(phone, team.leader_phone_hash)│
│ 4. Check lockout: failed_attempts >= 5?                     │
│    → If locked: Return 403 with unlock time                  │
│ 5. On success: Reset failed_attempts to 0                   │
│ 6. On failure: Increment failed_attempts                     │
│    → If now == 5: Set locked_until = NOW() + 15 min         │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ GENERATE JWT TOKEN                                           │
│ Payload: {                                                   │
│   "sub": team_name,                                          │
│   "role": "team",                                            │
│   "team_id": 42,                                             │
│   "exp": NOW() + 2 hours,                                    │
│   "iat": NOW()                                               │
│ }                                                            │
│                                                              │
│ Signed with: SECRET_KEY (HS256 algorithm)                   │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ RETURN TOKEN                                                 │
│ {                                                            │
│   "access_token": "eyJ...",                                  │
│   "token_type": "bearer",                                    │
│   "role": "team",                                            │
│   "user_info": { team_id, team_name, college }              │
│ }                                                            │
└──────────────────────────────────────────────────────────────┘
```

### Authorization Middleware

```
┌──────────────────────────────────────────────────────────────┐
│ PROTECTED ENDPOINT REQUEST                                   │
│ Authorization: Bearer eyJ...                                 │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ MIDDLEWARE: get_current_team()                               │
│ 1. Extract token from Authorization header                  │
│ 2. Decode JWT (verify signature + expiry)                   │
│ 3. Extract team_id from payload                             │
│ 4. Load team from database                                   │
│ 5. Verify team.is_active = true                             │
│ 6. Check team.locked_until < NOW() (not locked)             │
│ 7. Return team object                                        │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│ ENDPOINT HANDLER                                             │
│ async def submit_code(                                       │
│   current_team: Team = Depends(get_current_team)            │
│ ):                                                           │
│   # current_team is authenticated Team object                │
│   ...                                                        │
└──────────────────────────────────────────────────────────────┘
```

### Rate Limiting

| Endpoint | Limit | Window | Enforcement |
|----------|-------|--------|-------------|
| `POST /auth/*/login` | 5 attempts | 15 min | Database (failed_attempts, locked_until) |
| `POST /teams/submissions/*/submit` | 25 total | test duration | Database constraint |
| `POST /teams/submissions/*/autosave` | 1 req | 10 sec | Middleware (slowapi) |
| `GET /teams/questions` | 10 req | 1 min | Middleware (slowapi) |

### Code Injection Prevention

```
User Code
    ↓
Piston API (Isolated Container)
    ↓
┌──────────────────────────────────────┐
│ Security Layers:                     │
│ 1. No network access                 │
│ 2. No file system write              │
│ 3. Memory limit: 256 MB              │
│ 4. Time limit: 5 seconds             │
│ 5. Runs as non-root user             │
│ 6. Ephemeral container (destroyed)   │
└──────────────────────────────────────┘
```

**Additional Backend Safeguards:**
- Input validation (Pydantic models)
- SQL injection: Parameterized queries (SQLAlchemy ORM)
- XSS: Framework handles HTML escaping
- CSRF: Not needed (stateless JWT, no cookies)

---

## Deployment Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                         PRODUCTION                            │
└───────────────────────────────────────────────────────────────┘

┌──────────────────┐
│  Vercel          │  Frontend (Next.js)
│  - Next.js App   │  - Static/SSR pages
│  - Edge CDN      │  - Environment vars in dashboard
│  - Auto HTTPS    │
└────────┬─────────┘
         │
         │ API calls (HTTPS)
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│  Railway / Render                                            │
│  ┌────────────────┐              ┌────────────────┐         │
│  │  Web Service   │              │ Worker Service │         │
│  │  - FastAPI     │              │ - grading_worker│         │
│  │  - Uvicorn     │              │ - scheduler    │         │
│  │  - 2 instances │              │ - 1 instance   │         │
│  └────────┬───────┘              └────────────────┘         │
│           │                                                  │
│           ▼                                                  │
│  ┌────────────────┐              ┌────────────────┐         │
│  │  PostgreSQL    │              │  Redis         │         │
│  │  - Managed DB  │              │  (Optional)    │         │
│  │  - Auto backup │              │  - Queue       │         │
│  │  - 20 conn max │              │  - Cache       │         │
│  └────────────────┘              └────────────────┘         │
└──────────────────────────────────────────────────────────────┘

External:
┌────────────────────────────────────────────────────────────┐
│ Piston API (emkc.org)                                      │
│ - Called from Worker Service only                          │
│ - Rate limited: 10 req/sec                                 │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ Sentry (Error Tracking)                                    │
│ - JavaScript errors (frontend)                             │
│ - Python exceptions (backend)                              │
└────────────────────────────────────────────────────────────┘
```

### Environment Variables

**Backend:**
```bash
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://host:6379/0  # Optional
SECRET_KEY=<64-char-random-string>
ADMIN_PASSWORD=<secure-admin-password>
ADMIN_EMAIL=admin@example.com
PISTON_API_URL=https://emkc.org/api/v2/piston
PISTON_RATE_LIMIT=10
CORS_ORIGINS=https://frontend.vercel.app
ENVIRONMENT=production
```

**Frontend:**
```bash
NEXT_PUBLIC_API_URL=https://api.railway.app
NEXT_PUBLIC_WS_URL=wss://api.railway.app  # If using WebSockets
```

---

## Performance Characteristics

### Expected Latencies
- Team login: 100-200ms
- Start test: 50-100ms
- Fetch questions: 200-400ms (25 questions with joins)
- Submit code: 50ms (enqueue only, 202 Accepted)
- Grading complete: 5-15 seconds (per submission)

### Throughput
- Concurrent logins: 175 teams in 10 seconds = 17.5 req/sec
- Grading: 10 req/sec (Piston limit)
- Queue processing: 4,375 submissions in ~7-10 minutes

### Database Load
- Peak writes: Auto-submit (175 teams × 25 questions = 4,375 rows)
- Peak reads: Leaderboard recalculation (175 teams)
- Connection pool: 20 connections (sufficient for 2 web instances)

### Bottlenecks
1. **Piston API rate limit** (10 req/sec) → Mitigated by queue
2. **Database writes during auto-submit** → Mitigated by staggering
3. **Leaderboard rank calculation** (O(n log n)) → Acceptable with 175 teams

---

## Monitoring & Observability

### Key Metrics

**Application Metrics:**
- Request rate (req/sec per endpoint)
- Error rate (% of 5xx responses)
- Response time (P50, P95, P99)
- Active test sessions
- Queue depth (grading queue)

**Business Metrics:**
- Teams logged in
- Tests started
- Tests submitted
- Submissions graded
- Average score
- Leaderboard updates

**Infrastructure Metrics:**
- CPU usage (%)
- Memory usage (MB)
- Database connections (active/idle)
- Disk I/O

### Alerting Thresholds

| Condition | Severity | Action |
|-----------|----------|--------|
| Queue depth > 500 | Critical | Scale worker or investigate |
| Piston error rate > 5% | Critical | Check Piston status |
| Database connections > 18 | Warning | May need to scale |
| API error rate > 1% | Warning | Review logs |
| Grading stalled (no activity 5 min) | Critical | Restart worker |

---

## Disaster Recovery

### Backup Strategy
- **Database:** Daily automated backups (Railway/Render)
- **Code:** Git repository (GitHub)
- **Configuration:** Environment variables documented

### Failure Scenarios

**1. Web Server Down**
- Impact: Teams can't access platform
- Recovery: Railway auto-restarts, 2 instances provide redundancy
- RTO: 2 minutes

**2. Worker Process Down**
- Impact: Grading stops, queue builds up
- Recovery: Railway auto-restarts, queue resumes
- RTO: 2 minutes
- Data Loss: None (queue persists in DB/Redis)

**3. Database Down**
- Impact: Entire platform unavailable
- Recovery: Railway support, restore from backup
- RTO: 15-30 minutes
- Data Loss: Up to 24 hours (last backup)

**4. Piston API Down**
- Impact: Grading fails, submissions queue
- Recovery: Wait for Piston recovery, retry queue
- RTO: Depends on Piston
- Mitigation: Clear error messages to teams

---

This architecture supports 175 teams with unique question sets, auto-grading at scale, and production-grade reliability. All components are designed for the specific constraints: 10 req/sec Piston limit, 4,375 submissions at expiry, and zero data loss requirements.
