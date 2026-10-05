# Coding Test Platform - Implementation Roadmap

**Status:** Foundation Complete → Backend Implementation Phase
**Last Updated:** 2026-08-19

---

## 🎯 Project Overview

Building a production-ready coding test platform for **175 teams** with:
- Unique 25-question sets per team (10 easy, 10 medium, 5 hard)
- Auto-grading via Piston API (NO Docker)
- Live leaderboard with score DESC, time ASC tiebreaker
- CSV provisioning, JWT auth, admin controls

**Max Score:** 250 marks per team
**Test Duration:** 120 minutes (configurable)
**Scale Challenge:** 4,375 submissions potentially queued at timer expiry

---

## ✅ Phase 1: Foundation (COMPLETE)

### Database Schema ✅
- 12 tables with proper relationships
- Enums for type safety (DifficultyLevel, TestStatus, Language)
- Indexes optimized for query performance
- Audit logging support

**File:** `backend/app/models.py`

### Authentication ✅
- JWT tokens (2-hour expiry)
- Bcrypt password + phone hashing
- Rate limiting (5 attempts → 15 min lockout)
- Admin and team authentication flows

**Files:**
- `backend/app/auth.py`
- `backend/app/routes/auth.py`

### Core Services ✅
- CSV import with validation
- Question assignment with collision detection
- Database connection pooling
- Configuration management

**Files:**
- `backend/app/csv_import.py`
- `backend/app/question_assignment.py`
- `backend/app/database.py`
- `backend/app/config.py`

### API Framework ✅
- FastAPI with CORS
- Health check endpoint
- Global exception handler
- Lifespan events (startup/shutdown)

**File:** `backend/app/main.py`

---

## 🔄 Phase 2: Backend Core (IN PROGRESS)

### Critical Path: Grading Infrastructure

```
┌────────────────────────────────────────────────┐
│  Task 1: Grading Queue & Worker               │
│  - Redis/DB queue with FIFO ordering          │
│  - Rate limiter (10 req/sec to Piston)        │
│  - Background worker process                   │
│  - Retry logic with exponential backoff        │
│  - Idempotency guarantees                      │
│  Priority: CRITICAL                            │
│  Estimated: 1-2 days                           │
└────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────┐
│  Task 6: Grading Service                       │
│  - Piston API integration                      │
│  - Test case execution                         │
│  - Score calculation                           │
│  - Error handling (compilation, runtime)       │
│  Priority: CRITICAL                            │
│  Estimated: 1 day                              │
└────────────────────────────────────────────────┘
```

### Admin Routes

```
┌────────────────────────────────────────────────┐
│  Task 2: CSV Upload & Questions                │
│  - POST /admin/teams/upload-csv                │
│  - POST /admin/questions                       │
│  - PATCH /admin/questions/:id                  │
│  - GET /admin/questions                        │
│  Priority: CRITICAL                            │
│  Estimated: 1 day                              │
└────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────┐
│  Task 3: Test Config & Overrides               │
│  - POST /admin/test/configure                  │
│  - POST /admin/grading/:id/override            │
│  - GET /admin/leaderboard                      │
│  Priority: HIGH                                │
│  Estimated: 1 day                              │
└────────────────────────────────────────────────┘
```

### Team Routes

```
┌────────────────────────────────────────────────┐
│  Task 4: Test Session Management               │
│  - POST /teams/test/start                      │
│  - GET /teams/questions                        │
│  - GET /teams/test/status                      │
│  Priority: CRITICAL                            │
│  Estimated: 1 day                              │
└────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────┐
│  Task 5: Submissions & Autosave                │
│  - POST /teams/submissions/:id/autosave        │
│  - POST /teams/submissions/:id/submit          │
│  - GET /teams/submissions/:id/status           │
│  Priority: CRITICAL                            │
│  Estimated: 1 day                              │
└────────────────────────────────────────────────┘
```

### Scheduled Jobs & Services

```
┌────────────────────────────────────────────────┐
│  Task 7: Auto-Submit Scheduler                 │
│  - Runs every 10 seconds                       │
│  - Detects expired tests                       │
│  - Staggered submission (25 teams/batch)       │
│  Priority: CRITICAL                            │
│  Estimated: 0.5 days                           │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│  Task 9: Leaderboard Service                   │
│  - Rank calculation with SQL window functions  │
│  - Tiebreaker: time_taken_seconds ASC          │
│  - Cache optimization (Redis optional)         │
│  Priority: HIGH                                │
│  Estimated: 0.5 days                           │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│  Task 10: Export Service                       │
│  - CSV, Excel, PDF exports                     │
│  - Stream large files                          │
│  Priority: MEDIUM                              │
│  Estimated: 0.5 days                           │
└────────────────────────────────────────────────┘
```

**Phase 2 Total:** 5-7 days

---

## 🎨 Phase 3: Frontend (NOT STARTED)

### Foundation

```
┌────────────────────────────────────────────────┐
│  Task 11: Auth & Layout                        │
│  - Next.js 14 + TypeScript + Tailwind          │
│  - Admin and team login pages                  │
│  - JWT storage & middleware                    │
│  - Protected route handling                    │
│  Priority: HIGH                                │
│  Estimated: 1 day                              │
└────────────────────────────────────────────────┘
```

### Team Interface

```
┌────────────────────────────────────────────────┐
│  Task 12: Team Dashboard                       │
│  - Code editor (Monaco)                        │
│  - Countdown timer with warnings               │
│  - Question list with status                   │
│  - Autosave indicator                          │
│  - Submission polling                          │
│  Priority: HIGH                                │
│  Estimated: 2 days                             │
└────────────────────────────────────────────────┘
```

### Admin Interface

```
┌────────────────────────────────────────────────┐
│  Task 13: Admin Dashboard                      │
│  - CSV upload with drag-and-drop               │
│  - Question bank management                    │
│  - Test configuration UI                       │
│  - Live monitoring dashboard                   │
│  - Leaderboard & export controls               │
│  Priority: MEDIUM                              │
│  Estimated: 2 days                             │
└────────────────────────────────────────────────┘
```

**Phase 3 Total:** 3-4 days

---

## 🚀 Phase 4: Launch (NOT STARTED)

### Testing

```
┌────────────────────────────────────────────────┐
│  Task 14: Load Testing & Optimization          │
│  - 175 concurrent logins                       │
│  - 175 simultaneous starts                     │
│  - 4,375 submissions over 2 hours              │
│  - Database query optimization                 │
│  Priority: HIGH                                │
│  Estimated: 1-2 days                           │
└────────────────────────────────────────────────┘
```

### Deployment

```
┌────────────────────────────────────────────────┐
│  Task 15: Production Deployment                │
│  - Railway/Render (backend + worker)           │
│  - Vercel (frontend)                           │
│  - PostgreSQL + Redis provisioning             │
│  - Monitoring & alerting setup                 │
│  - Error tracking (Sentry)                     │
│  Priority: HIGH                                │
│  Estimated: 1-2 days                           │
└────────────────────────────────────────────────┘
```

**Phase 4 Total:** 2-3 days

---

## 📊 Overall Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1: Foundation | 3 days | ✅ Complete |
| Phase 2: Backend Core | 5-7 days | 🔄 In Progress |
| Phase 3: Frontend | 3-4 days | 🔜 Not Started |
| Phase 4: Launch | 2-3 days | 🔜 Not Started |
| **TOTAL** | **13-17 days** | **23% Complete** |

---

## 🎯 Success Criteria

### Technical
- [ ] 175 teams can start test within 10 seconds
- [ ] Zero data loss (100% autosave recovery)
- [ ] API P95 latency < 1 second
- [ ] Grading completes within 10 minutes of auto-submit
- [ ] No Piston API rate limit errors

### Business
- [ ] Admin setup time < 10 minutes
- [ ] CSV upload < 5 seconds for 175 teams
- [ ] Results export < 5 seconds
- [ ] Clear submission status (no "Did it submit?" confusion)

---

## 🔑 Key Design Highlights

### 1. Queue-Based Grading (Handles Scale)
```
Submission → Queue (202 Accepted) → Worker (10/sec) → Piston API
```
**Why:** Prevents overwhelming Piston's 10 req/sec limit

### 2. Staggered Auto-Submit (Prevents Spike)
```
175 teams → 7 batches of 25 → 5-sec delay → 35 seconds total
```
**Why:** Avoids 4,375 submissions hitting queue instantly

### 3. Autosave Recovery (Zero Data Loss)
```
Browser crash → Login → Load autosaved code → Continue test
```
**Why:** Guarantees no work lost due to technical issues

### 4. Idempotency Everywhere (Safe Retries)
```
Duplicate submit → Check existing → Return same response
```
**Why:** Network timeouts safe to retry without side effects

---

## 📁 Project Structure

```
coding-test-platform/
├── backend/
│   ├── app/
│   │   ├── models.py              ✅ Complete
│   │   ├── database.py            ✅ Complete
│   │   ├── config.py              ✅ Complete
│   │   ├── auth.py                ✅ Complete
│   │   ├── csv_import.py          ✅ Complete
│   │   ├── question_assignment.py ✅ Complete
│   │   ├── main.py                ✅ Complete
│   │   ├── grading_queue.py       ⏳ Task 1
│   │   ├── grading_worker.py      ⏳ Task 1
│   │   ├── piston_client.py       ⏳ Task 1, 6
│   │   ├── grading_service.py     ⏳ Task 6
│   │   ├── scheduler.py           ⏳ Task 7
│   │   ├── auto_submit.py         ⏳ Task 7
│   │   ├── leaderboard_service.py ⏳ Task 9
│   │   ├── export_service.py      ⏳ Task 10
│   │   ├── schemas.py             ⏳ Task 2
│   │   ├── audit.py               ⏳ Task 3
│   │   └── routes/
│   │       ├── auth.py            ✅ Complete
│   │       ├── admin.py           ⏳ Task 2, 3
│   │       ├── teams.py           ⏳ Task 4, 5, 8
│   │       └── leaderboard.py     ⏳ Task 9
│   ├── requirements.txt           ✅ Complete
│   └── .env.example               ✅ Complete
├── frontend/                      ⏳ Task 11-13
├── .kiro/
│   └── specs/
│       └── platform-implementation/
│           ├── spec.md            ✅ Complete
│           ├── requirements.md    ✅ Complete
│           ├── design.md          ✅ Complete
│           └── tasks.md           ✅ Complete
└── README.md                      ✅ Complete
```

---

## 🚦 Next Immediate Steps

1. **Start Task 1: Grading Queue** (Critical Path)
   - Create `grading_queue.py` with Redis/DB queue
   - Create `piston_client.py` with rate limiter
   - Create `grading_worker.py` background process

2. **Parallel: Start Frontend** (Can work independently)
   - API contracts defined in `design.md`
   - Mock API responses during development

3. **Review Design Document**
   - Validate API shapes match requirements
   - Confirm rate limiting strategy
   - Approve transaction boundaries

4. **Setup Development Environment**
   - PostgreSQL database
   - Redis (optional, for queue)
   - Piston API access (free tier)

---

## 📞 Questions or Blockers?

- **Design Questions:** Review `.kiro/specs/platform-implementation/design.md`
- **API Contracts:** See "API Design" section in design doc
- **Data Flows:** See "Data Flow Pipelines" section in design doc
- **Scale Strategy:** See "Rate Limiting & Queue Management" section

---

**Ready to start implementation! 🚀**
