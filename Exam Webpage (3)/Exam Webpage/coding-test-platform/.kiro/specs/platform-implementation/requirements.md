# Requirements Summary

**Spec:** Platform Implementation
**Last Updated:** 2026-08-19

---

## Overview

Production-ready coding test platform for 175 teams with auto-grading, unique question sets, and live leaderboard.

---

## Core Requirements

### 1. Team Management
- ✅ CSV-based provisioning only (no self-signup)
- ✅ 175 teams uploaded in single batch
- ✅ Team credentials: team_name + leader_phone (hashed)
- ✅ Single attempt per team (no retakes)
- ✅ Rate limiting: 5 failed logins → 15 min lockout

### 2. Question Assignment
- ✅ Each team gets unique 25-question set
- ✅ Distribution: 10 easy (5 marks) + 10 medium (10 marks) + 5 hard (20 marks)
- ✅ Total possible score: 250 marks per team
- ✅ Collision detection with 10 retry limit
- ✅ Question bank requires 175+ active questions minimum

### 3. Test Execution
- ⏳ Synchronized start at global time (configurable)
- ⏳ OR individual timers (each team gets 120 min from start)
- ⏳ Test duration: 120 minutes (configurable)
- ⏳ Test window: Admin sets open/close times
- ⏳ Auto-submit on timer expiry
- ⏳ Autosave every 30 seconds (browser crash recovery)

### 4. Code Execution & Grading
- ⏳ NO Docker (use Piston API: https://emkc.org/api/v2/piston)
- ⏳ OS-level sandboxing (Piston handles isolation)
- ⏳ Language support: Python, C++, Java, JavaScript
- ⏳ Time limit: 5 seconds per execution (configurable per question)
- ⏳ Memory limit: 256 MB per execution (configurable per question)
- ⏳ All-or-nothing scoring: 100% hidden tests pass = full marks
- ⏳ Compilation/runtime errors = 0 marks

### 5. Leaderboard
- ⏳ Primary sort: Total score DESC
- ⏳ Tiebreaker: Time taken ASC (seconds from start to submit)
- ⏳ Admin can toggle visibility (hide during test, publish after)
- ⏳ Live updates as grading completes
- ⏳ Shows: rank, team_name, total_score, time_taken, score_breakdown

### 6. Admin Controls
- ⏳ Question bank CRUD (create, read, update, delete)
- ⏳ CSV team upload with validation
- ⏳ Test configuration (timing, duration, rules)
- ⏳ Manual grade override with audit trail
- ⏳ Export results (CSV, Excel, PDF)
- ⏳ Live monitoring (teams started, submitted, queue depth)

### 7. Security
- ✅ JWT authentication (2-hour expiry, configurable)
- ✅ Password hashing (bcrypt)
- ✅ Phone number hashing (bcrypt, treat as password)
- ⏳ Rate limiting on all endpoints
- ⏳ Code injection prevention (Piston sandbox)
- ⏳ Audit logging (all admin actions)

### 8. Scalability
- ⏳ Handle 175 teams starting simultaneously
- ⏳ Handle 4,375 submissions (175 × 25) queued at expiry
- ⏳ Grading queue with rate limiting (10 req/sec to Piston)
- ⏳ Staggered auto-submit (25 teams per batch, 5-sec delay)
- ⏳ Grading completes within 10 minutes of auto-submit

---

## Non-Functional Requirements

### Performance
- API P95 latency: < 1 second
- CSV upload: < 5 seconds for 175 teams
- Question fetch: < 500ms
- Submission endpoint: < 200ms (202 Accepted, async grading)

### Reliability
- Zero data loss (all autosaves recoverable)
- Idempotent submissions (duplicate submit returns existing)
- Retry logic: 3 attempts with exponential backoff
- Transaction safety (CSV upload, grade override)

### Usability
- Clear submission status (autosaved, submitted, grading, graded)
- Queue position visibility ("23 submissions ahead")
- Timer warnings (red text at 5 min, modal at 30 sec)
- Mobile-responsive frontend

### Observability
- Structured JSON logs
- Error tracking (Sentry or similar)
- Queue depth monitoring
- Grading throughput metrics
- Alerting on critical errors

---

## Acceptance Criteria

### End-to-End Success Scenario

1. **Admin Setup (Day Before Test)**
   - [ ] Admin logs in successfully
   - [ ] Uploads CSV with 175 teams
   - [ ] All 175 teams created with unique question sets
   - [ ] Configures test: Opens 9 AM, Starts 10 AM, Closes 9 PM, Duration 120 min
   - [ ] Verifies 175+ questions in bank (at least 75 easy, 75 medium, 25 hard)

2. **Team Login (Test Day 9 AM)**
   - [ ] 175 teams log in with team_name + phone
   - [ ] See countdown: "Test starts at 10:00 AM"
   - [ ] Invalid credentials show error (but don't leak which field is wrong)

3. **Test Start (10:00 AM)**
   - [ ] All 175 teams click "Start Test" within 10 seconds
   - [ ] Timer begins: 120 minutes countdown
   - [ ] Questions load: 25 questions with starter code
   - [ ] No performance degradation (API responds < 1 second)

4. **Test In Progress (10:00 - 12:00)**
   - [ ] Teams write code, see autosave indicator
   - [ ] Submit answers, see grading status polling
   - [ ] Graded submissions show: marks, passed tests, execution time
   - [ ] Page refresh recovers autosaved code
   - [ ] Timer shows red text at 5 minutes remaining

5. **Auto-Submit (12:00 PM)**
   - [ ] Scheduled job detects 175 expired tests
   - [ ] Auto-submits all in 35 seconds (staggered batches)
   - [ ] 4,375 submissions queued
   - [ ] Grading completes in ~7-10 minutes
   - [ ] No Piston API 429 errors

6. **Results (12:10 PM)**
   - [ ] Admin publishes leaderboard
   - [ ] Teams see final scores and rank
   - [ ] Tiebreaker applied correctly (time taken ASC)
   - [ ] Admin exports results CSV
   - [ ] CSV includes: rank, team, scores, time taken

7. **Grade Override (If Needed)**
   - [ ] Admin overrides submission grade
   - [ ] Total score recalculated
   - [ ] Leaderboard ranks updated
   - [ ] Audit log entry created with reason

---

## Edge Cases & Error Handling

### Team Login
- [ ] Duplicate team name in CSV → Reject entire upload
- [ ] Invalid phone format → Reject entire upload
- [ ] 5 failed login attempts → Lock for 15 minutes
- [ ] Login during lockout → Show remaining time

### Test Start
- [ ] Click "Start Test" twice → Idempotent (return existing session)
- [ ] Start test outside window → Error: "Test not available"
- [ ] Start test after already submitted → Error: "Test already completed"

### Code Submission
- [ ] Submit same question twice → Idempotent (return existing submission)
- [ ] Submit code with compilation error → Mark as 0, show error output
- [ ] Submit code with runtime error → Mark as 0, show error output
- [ ] Submit after timer expiry → Error: "Test expired"
- [ ] Submit without starting test → Error: "Test not started"

### Grading
- [ ] Piston API timeout → Retry 3 times with backoff
- [ ] Piston API 429 → Wait 10 seconds, retry
- [ ] Piston API 5xx → Retry with backoff
- [ ] Piston API 400 → Don't retry, mark as error
- [ ] All retries fail → Mark as error, log incident

### Auto-Submit
- [ ] Team submits manually at 11:59 → Auto-submit skips (already submitted)
- [ ] Browser crash at 11:30 → Autosaves recovered, auto-submitted at 12:00
- [ ] No autosaves found → Auto-submit with empty code (0 marks)

### Leaderboard
- [ ] Two teams same score → Rank by time taken (ASC)
- [ ] Two teams same score and time → Rank by team_id (ASC)
- [ ] Grade override during test → Ranks recalculated immediately
- [ ] Team views leaderboard before published → Error: "Not yet available"

---

## Out of Scope (Explicitly NOT Required)

- ❌ Team self-signup (CSV upload only)
- ❌ Email notifications
- ❌ Password reset flow
- ❌ Multiple test attempts
- ❌ Question randomization within test (order stays 1-25)
- ❌ Real-time collaboration between team members
- ❌ Video proctoring / anti-cheat
- ❌ Plagiarism detection
- ❌ Discussion forum
- ❌ Practice mode

---

## Open Decisions (Needs Confirmation)

### Decision 1: Synchronized vs. Individual Start
**Options:**
- A) Synchronized: All teams start at global time (10 AM)
- B) Individual: Each team gets 120 min from their start time

**Current Design:** Option A (synchronized)
**Recommendation:** Option A (simpler, fair)
**Decision:** ✅ Confirmed - Synchronized start

---

### Decision 2: Grading - All-or-Nothing vs. Partial Credit
**Options:**
- A) All-or-nothing: Need 100% test pass for full marks
- B) Partial credit: 3/5 tests = 60% of marks

**Current Design:** Option A (all-or-nothing)
**Recommendation:** Option A (prevents gaming, simpler)
**Decision:** ⏳ Awaiting confirmation

---

### Decision 3: Redis Queue vs. Database Queue
**Options:**
- A) Redis: Faster, atomic operations, requires extra service
- B) Database: Simpler deployment, slightly slower

**Current Design:** Database with Redis as optional upgrade
**Recommendation:** Start with database, add Redis if queue depth becomes issue
**Decision:** ✅ Confirmed - Database queue, Redis optional

---

## Success Metrics

### Technical Metrics
- ✅ Zero downtime during test window
- ✅ Zero data loss (100% autosave recovery rate)
- ✅ API error rate < 0.1%
- ✅ Grading completion within 10 minutes of auto-submit
- ✅ No Piston rate limit errors

### Business Metrics
- ✅ 100% team login success rate (no credential issues)
- ✅ 100% question set uniqueness
- ✅ Admin setup time < 10 minutes
- ✅ Results export < 5 seconds

### User Experience Metrics
- ✅ Clear submission status (no confusion about "Did it submit?")
- ✅ No complaints about timer accuracy
- ✅ Mobile-friendly interface
- ✅ Admin can override grades in < 30 seconds

---

**Legend:**
- ✅ Implemented
- ⏳ Pending implementation
- ❌ Out of scope
