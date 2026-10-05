# Implementation Tasks

**Spec:** Platform Implementation
**Status:** not-started

---

## Task 1: Implement Grading Queue & Worker Infrastructure
**Status:** not-started
**Assigned To:** unassigned
**Priority:** critical

### Description
Build the core grading infrastructure that will process 4,375 submissions at scale without overwhelming Piston API.

### Acceptance Criteria
- [ ] Redis-based grading queue with FIFO ordering (OR database fallback if Redis unavailable)
- [ ] Rate limiter that enforces 10 req/sec to Piston API with no bursting
- [ ] Background worker process that consumes queue and calls Piston
- [ ] Retry logic: 3 attempts with exponential backoff for timeouts/500s
- [ ] Idempotency: Prevent double-grading of same submission
- [ ] Queue depth monitoring endpoint: `GET /api/admin/queue/stats`

### Implementation Notes
- Use Redis ZADD/ZPOPMIN for atomic queue operations
- Worker runs as separate process: `python grading_worker.py`
- Retry only on: timeout, 429, 5xx (NOT on 400 or execution errors)
- Check `GradingResult.submission_id` UNIQUE constraint before calling Piston

### Files to Create/Modify
- `backend/app/grading_queue.py` (new)
- `backend/app/grading_worker.py` (new)
- `backend/app/piston_client.py` (new)

### Dependencies
- None (foundational)

---

## Task 2: Implement Admin Routes - CSV Upload & Question Management
**Status:** not-started
**Assigned To:** unassigned
**Priority:** critical

### Description
Build admin endpoints for uploading 175 teams and managing question bank.

### Acceptance Criteria
- [ ] `POST /api/admin/teams/upload-csv` - Upload 175 teams with validation
- [ ] Transaction: All 175 teams + question assignments OR rollback
- [ ] CSV validation: phone format, duplicate team names, required fields
- [ ] Question assignment with collision detection (10 retry limit)
- [ ] `POST /api/admin/questions` - Create question with test cases
- [ ] `PATCH /api/admin/questions/:id` - Update question (doesn't affect existing assignments)
- [ ] `DELETE /api/admin/questions/:id` - Soft delete (set is_active=false)
- [ ] `GET /api/admin/questions` - List all questions with filters (difficulty, active status)
- [ ] Auto-assign marks: easy=5, medium=10, hard=20

### Implementation Notes
- Use `db.bulk_insert_mappings()` for performance
- Return detailed error report with row numbers on failure
- Validate: At least 175 questions active (175 unique sets requirement)

### Files to Create/Modify
- `backend/app/routes/admin.py` (new)
- `backend/app/schemas.py` (new - Pydantic models)
- Update `backend/app/main.py` to include router

### Dependencies
- CSV import utility (already exists in `csv_import.py`)
- Question assignment utility (already exists in `question_assignment.py`)

---

## Task 3: Implement Admin Routes - Test Configuration & Overrides
**Status:** not-started
**Assigned To:** unassigned
**Priority:** high

### Description
Build admin controls for test timing, grade overrides, and leaderboard management.

### Acceptance Criteria
- [ ] `POST /api/admin/test/configure` - Set test window and duration
- [ ] `GET /api/admin/test/status` - View test status (teams started, submitted, in progress)
- [ ] `POST /api/admin/grading/:submission_id/override` - Manual grade override
- [ ] Grade override recalculates: total_score, rank (all teams)
- [ ] Audit log entry created for every override
- [ ] `POST /api/admin/leaderboard/publish` - Make leaderboard visible to teams
- [ ] `GET /api/admin/leaderboard` - Full leaderboard with detailed scores
- [ ] Transaction ensures score and rank consistency

### Implementation Notes
- Test configuration stored in `test_configuration` table (singleton row)
- Override triggers full rank recalculation: `ORDER BY total_score DESC, time_taken_seconds ASC`
- Audit log includes: old_value, new_value, reason, IP address

### Files to Create/Modify
- `backend/app/routes/admin.py` (extend)
- `backend/app/audit.py` (new - audit logging utility)

### Dependencies
- Task 2 (admin routes foundation)

---

## Task 4: Implement Team Routes - Test Session Management
**Status:** not-started
**Assigned To:** unassigned
**Priority:** critical

### Description
Build team endpoints for starting test, fetching questions, and tracking time.

### Acceptance Criteria
- [ ] `POST /api/teams/test/start` - Start test timer (idempotent)
- [ ] Validates: Test window open, team hasn't started yet
- [ ] Sets `TestSession.test_started_at = NOW()`, `status = IN_PROGRESS`
- [ ] `GET /api/teams/questions` - Fetch assigned 25 questions
- [ ] Questions ordered by position (1-25)
- [ ] Hidden test cases NEVER returned
- [ ] Includes starter code for all 4 languages
- [ ] Includes submission status (autosaved, submitted, graded)
- [ ] `GET /api/teams/test/status` - Time remaining, auto-submit warning
- [ ] Returns time_remaining_seconds, expires_at timestamp

### Implementation Notes
- Start test is idempotent: If already started, return existing session
- Question fetch joins on `TeamQuestionAssignment` to get assigned set
- Calculate time remaining: `(test_started_at + duration) - NOW()`

### Files to Create/Modify
- `backend/app/routes/teams.py` (new)
- Update `backend/app/main.py` to include router

### Dependencies
- Task 1 (grading queue - needed for submission endpoints)

---

## Task 5: Implement Team Routes - Code Submission & Autosave
**Status:** not-started
**Assigned To:** unassigned
**Priority:** critical

### Description
Build submission endpoints with autosave for browser crash recovery.

### Acceptance Criteria
- [ ] `POST /api/teams/submissions/:question_id/autosave` - Save code without grading
- [ ] Autosave creates `Submission` with `is_final = false`
- [ ] Autosave does NOT trigger grading (no queue enqueue)
- [ ] `POST /api/teams/submissions/:question_id/submit` - Submit for grading
- [ ] Submit creates `Submission` with `is_final = true`
- [ ] Submit enqueues to grading queue (returns 202 Accepted)
- [ ] Idempotent: Duplicate submit returns existing submission
- [ ] `GET /api/teams/submissions/:submission_id/status` - Poll grading status
- [ ] Status returns: queued, grading, graded, error
- [ ] Shows queue position if still queued
- [ ] Rate limit: 25 submits per team per test (enforced at DB level)

### Implementation Notes
- Idempotency check: `SELECT ... WHERE team_id=? AND question_id=? AND is_final=true`
- Queue position: `redis.zrank("grading_queue", submission_id)`
- Autosave rate limit: 1 per 10 seconds (prevent spam)

### Files to Create/Modify
- `backend/app/routes/teams.py` (extend)
- `backend/app/rate_limiter.py` (new - optional, or use slowapi)

### Dependencies
- Task 1 (grading queue)
- Task 4 (test session management)

---

## Task 6: Implement Grading Service - Piston Integration
**Status:** not-started
**Assigned To:** unassigned
**Priority:** critical

### Description
Build the core grading logic that executes code via Piston API and calculates scores.

### Acceptance Criteria
- [ ] Worker fetches submission from queue
- [ ] Loads question's hidden test cases from database
- [ ] For each test case: Call Piston API with input, compare output
- [ ] Output comparison: Strip whitespace, case-sensitive
- [ ] Calculate marks: (passed_tests / total_tests) × question.marks
- [ ] Store `GradingResult` with detailed test_results JSON
- [ ] Handle compilation errors: marks=0, store error_output
- [ ] Handle runtime errors: marks=0, store error_output
- [ ] Handle timeouts: Retry up to 3 times, then mark as error
- [ ] Update `TestSession.total_score` incrementally

### Implementation Notes
- Piston request format:
  ```json
  {
    "language": "python",
    "version": "3.11",
    "files": [{"content": "<code>"}],
    "stdin": "<test_input>",
    "compile_timeout": 10000,
    "run_timeout": 5000,
    "run_memory_limit": 268435456
  }
  ```
- All-or-nothing scoring: Need 100% pass for full marks (configurable)

### Files to Create/Modify
- `backend/app/grading_service.py` (new)
- `backend/app/piston_client.py` (extend from Task 1)

### Dependencies
- Task 1 (grading queue infrastructure)

---

## Task 7: Implement Auto-Submit at Timer Expiry
**Status:** not-started
**Assigned To:** unassigned
**Priority:** critical

### Description
Build scheduled job that auto-submits tests when timer expires, with staggered processing.

### Acceptance Criteria
- [ ] Scheduled job runs every 10 seconds
- [ ] Query: `TestSession.status = IN_PROGRESS AND test_started_at + duration < NOW()`
- [ ] Process in batches of 25 teams with 5-second delay between batches
- [ ] For each team: Fetch all autosaves, mark as `is_final = true`
- [ ] Set `TestSession.status = AUTO_SUBMITTED`, `submitted_at = expired_at`
- [ ] Enqueue all 25 submissions to grading queue
- [ ] Log: "Auto-submitted 175 teams in 35 seconds"

### Implementation Notes
- Use APScheduler or Celery Beat for scheduling
- Staggering prevents 4,375 submissions queued instantly
- Expired time = `test_started_at + duration_minutes * 60`

### Files to Create/Modify
- `backend/app/scheduler.py` (new)
- `backend/app/auto_submit.py` (new)
- Update `backend/app/main.py` to start scheduler

### Dependencies
- Task 5 (submission endpoints)

---

## Task 8: Implement Final Test Submission
**Status:** not-started
**Assigned To:** unassigned
**Priority:** high

### Description
Build endpoint for teams to manually submit entire test before timer expires.

### Acceptance Criteria
- [ ] `POST /api/teams/test/submit-final` - Submit entire test
- [ ] Transaction: Update `TestSession.status = SUBMITTED`, `submitted_at = NOW()`
- [ ] Calculate `time_taken_seconds = submitted_at - test_started_at`
- [ ] Mark all pending autosaves as `is_final = true` (if not already submitted)
- [ ] Enqueue pending submissions to grading queue
- [ ] Idempotent: If already submitted, return existing data
- [ ] Returns: questions_submitted, questions_pending_grade, preliminary_score

### Implementation Notes
- Idempotency check: `WHERE status IN ('SUBMITTED', 'AUTO_SUBMITTED')`
- Preliminary score = sum of already-graded submissions

### Files to Create/Modify
- `backend/app/routes/teams.py` (extend)

### Dependencies
- Task 5 (submission endpoints)
- Task 6 (grading service for preliminary score)

---

## Task 9: Implement Leaderboard Service
**Status:** not-started
**Assigned To:** unassigned
**Priority:** high

### Description
Build leaderboard ranking logic with tiebreaker (time taken ASC).

### Acceptance Criteria
- [ ] `GET /api/teams/leaderboard` - Team view (if published by admin)
- [ ] `GET /api/admin/leaderboard` - Full admin view
- [ ] Ranking SQL: `ORDER BY total_score DESC, time_taken_seconds ASC`
- [ ] Update all `TestSession.rank` on every score change
- [ ] Cache top 100 teams in Redis (optional optimization)
- [ ] Leaderboard includes: rank, team_name, total_score, time_taken, score_breakdown
- [ ] Admin can toggle visibility: `TestConfiguration.leaderboard_published`

### Implementation Notes
- Rank calculation uses SQL window function:
  ```sql
  WITH ranked AS (
    SELECT id, ROW_NUMBER() OVER (
      ORDER BY total_score DESC, time_taken_seconds ASC
    ) as new_rank
    FROM test_sessions
    WHERE status IN ('SUBMITTED', 'AUTO_SUBMITTED')
  )
  UPDATE test_sessions ts SET rank = ranked.new_rank FROM ranked WHERE ts.id = ranked.id;
  ```

### Files to Create/Modify
- `backend/app/routes/leaderboard.py` (new)
- `backend/app/leaderboard_service.py` (new)

### Dependencies
- Task 6 (grading service - scores must be available)

---

## Task 10: Implement Export Service
**Status:** not-started
**Assigned To:** unassigned
**Priority:** medium

### Description
Build result export in CSV/Excel/PDF formats for admin.

### Acceptance Criteria
- [ ] `GET /api/admin/export/results?format=csv` - Export as CSV
- [ ] `GET /api/admin/export/results?format=excel` - Export as Excel
- [ ] `GET /api/admin/export/results?format=pdf` - Export as PDF
- [ ] CSV includes: rank, team_name, total_score, time_taken, easy/medium/hard scores
- [ ] Excel includes: Multiple sheets (summary, per-question breakdown)
- [ ] PDF includes: Formatted table with header/footer
- [ ] Filename: `results_YYYY-MM-DD.csv`

### Implementation Notes
- CSV: Use Python csv module
- Excel: Use openpyxl library
- PDF: Use reportlab or weasyprint
- Stream large files to avoid memory issues

### Files to Create/Modify
- `backend/app/routes/admin.py` (extend)
- `backend/app/export_service.py` (new)

### Dependencies
- Task 9 (leaderboard - need final rankings)

---

## Task 11: Build Frontend - Authentication & Layout
**Status:** not-started
**Assigned To:** unassigned
**Priority:** high

### Description
Build Next.js frontend foundation with auth and routing.

### Acceptance Criteria
- [ ] Next.js 14 with App Router
- [ ] TypeScript + Tailwind CSS
- [ ] Login page for admin: `/admin/login`
- [ ] Login page for teams: `/login`
- [ ] JWT token storage in localStorage
- [ ] Protected routes with middleware
- [ ] Layout with header (timer, team name, logout)
- [ ] Responsive design (mobile + desktop)

### Implementation Notes
- Use Next.js middleware for auth checks
- API client: axios with interceptor for token
- Dark mode optional

### Files to Create
- `frontend/app/layout.tsx`
- `frontend/app/login/page.tsx`
- `frontend/app/admin/login/page.tsx`
- `frontend/lib/auth.ts`
- `frontend/middleware.ts`

### Dependencies
- None (can work in parallel with backend)

---

## Task 12: Build Frontend - Team Dashboard
**Status:** not-started
**Assigned To:** unassigned
**Priority:** high

### Description
Build team interface for taking test.

### Acceptance Criteria
- [ ] Landing page with "Start Test" button
- [ ] Countdown timer (persistent across page refreshes)
- [ ] Question list (1-25) with status indicators (not attempted, saved, submitted)
- [ ] Code editor with syntax highlighting (Monaco or CodeMirror)
- [ ] Language selector (Python, C++, Java, JavaScript)
- [ ] Sample test cases displayed below editor
- [ ] "Autosave" indicator (last saved timestamp)
- [ ] "Submit Answer" button (confirms before submit)
- [ ] "Submit Test" button (confirms before final submit)
- [ ] Grading status polling (shows spinner and queue position)

### Implementation Notes
- Use Monaco Editor (same as VS Code)
- Autosave: Debounce 30 seconds
- Timer: Red text when < 5 minutes remaining
- Auto-submit warning modal at 30 seconds

### Files to Create
- `frontend/app/dashboard/page.tsx`
- `frontend/components/CodeEditor.tsx`
- `frontend/components/Timer.tsx`
- `frontend/components/QuestionList.tsx`

### Dependencies
- Task 11 (auth foundation)
- Task 4, 5 (backend endpoints)

---

## Task 13: Build Frontend - Admin Dashboard
**Status:** not-started
**Assigned To:** unassigned
**Priority:** medium

### Description
Build admin interface for managing test.

### Acceptance Criteria
- [ ] CSV upload page with drag-and-drop
- [ ] Upload progress indicator
- [ ] Error report display (with row numbers)
- [ ] Question bank page (list, create, edit, delete)
- [ ] Rich text editor for question prompts (Markdown)
- [ ] Test configuration page (timing, duration, synchronized start)
- [ ] Live test monitoring dashboard (teams started, submitted, in progress)
- [ ] Grading queue stats (depth, throughput, errors)
- [ ] Leaderboard view with export buttons
- [ ] Grade override modal (with reason field)

### Implementation Notes
- CSV upload: react-dropzone
- Markdown editor: react-simplemde-editor
- Charts: recharts or chart.js
- Real-time updates: Poll every 5 seconds

### Files to Create
- `frontend/app/admin/dashboard/page.tsx`
- `frontend/app/admin/teams/upload/page.tsx`
- `frontend/app/admin/questions/page.tsx`
- `frontend/app/admin/leaderboard/page.tsx`
- `frontend/app/admin/config/page.tsx`

### Dependencies
- Task 11 (auth foundation)
- Task 2, 3, 9, 10 (backend endpoints)

---

## Task 14: Load Testing & Performance Optimization
**Status:** not-started
**Assigned To:** unassigned
**Priority:** high

### Description
Test system under load and optimize bottlenecks.

### Acceptance Criteria
- [ ] Load test: 175 concurrent team logins
- [ ] Load test: 175 simultaneous test starts
- [ ] Load test: 4,375 submissions over 2 hours
- [ ] Measure: API P95 latency < 1 second
- [ ] Measure: Grading queue never exceeds 500 depth
- [ ] Measure: Zero data loss (all autosaves recoverable)
- [ ] Database query optimization (add indexes if needed)
- [ ] Connection pooling tuned (max 20 connections)

### Implementation Notes
- Use Locust for load testing
- Monitor: CPU, memory, database connections, queue depth
- Optimize: Add indexes on frequently queried columns
- Scale: Consider horizontal scaling if needed

### Tools
- Locust (load testing)
- Postgres EXPLAIN ANALYZE (query optimization)
- Railway metrics (CPU/memory monitoring)

### Dependencies
- Task 1-13 (all features complete)

---

## Task 15: Deployment & Production Hardening
**Status:** not-started
**Assigned To:** unassigned
**Priority:** high

### Description
Deploy to production with monitoring and error handling.

### Acceptance Criteria
- [ ] Backend deployed to Railway/Render
- [ ] Frontend deployed to Vercel
- [ ] PostgreSQL managed database provisioned
- [ ] Redis provisioned (if using Redis queue)
- [ ] Environment variables configured
- [ ] HTTPS enabled with valid certificate
- [ ] Error tracking: Sentry or similar
- [ ] Logging: Structured JSON logs
- [ ] Monitoring: Queue depth, API errors, grading throughput
- [ ] Alerting: Slack/email on critical errors
- [ ] Backup strategy: Daily database backups

### Implementation Notes
- Railway: Free tier supports 2 services (web + worker)
- Vercel: Hobby plan supports Next.js deployment
- Use Railway's built-in PostgreSQL and Redis
- Sentry: Free tier supports 5,000 events/month

### Files to Create
- `backend/Dockerfile` (if needed)
- `frontend/.env.production`
- `backend/.env.production.example`
- `DEPLOYMENT.md` (deployment guide)

### Dependencies
- Task 1-13 (all features complete)
- Task 14 (load testing passed)

---

## Summary

**Total Tasks:** 15
**Critical Priority:** 8 tasks
**High Priority:** 5 tasks
**Medium Priority:** 2 tasks

**Estimated Timeline:**
- Backend (Tasks 1-10): 5-7 days
- Frontend (Tasks 11-13): 3-4 days
- Testing & Deployment (Tasks 14-15): 2-3 days
- **Total: 10-14 days** (single developer)

**Parallel Track Opportunities:**
- Backend tasks 1-10 can proceed independently
- Frontend tasks 11-13 can start once API contracts are defined (already in design doc)
- Testing task 14 can start once individual features are complete

**Risk Mitigation:**
- Task 1 (grading queue) is critical path - start first
- Task 7 (auto-submit) needs careful testing - schedule QA time
- Task 14 (load testing) may reveal scale issues - buffer time for optimization
