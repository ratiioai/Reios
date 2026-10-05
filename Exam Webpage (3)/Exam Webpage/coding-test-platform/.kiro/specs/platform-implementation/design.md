# Design Document: Coding Test Platform

## Overview

This design document specifies the technical architecture, API contracts, data flows, and scaling strategies for the coding test platform serving 175 teams with auto-grading.

**Key Design Constraints:**
- 175 teams × 25 questions = 4,375 potential submissions
- Synchronized timer expiry = potential simultaneous submission spike
- Piston API rate limits must be respected
- Single attempt per team = no room for data loss
- Score tiebreaker = time taken (requires precise timing)

---

## 1. API Design

### 1.1 Admin Routes

**Base Path:** `/api/admin`

#### POST /admin/teams/upload-csv
Upload 175 teams from CSV with validation and unique question assignment.

**Request:**
```
Content-Type: multipart/form-data
Authorization: Bearer <admin_token>

file: teams.csv
```

**CSV Format:**
```csv
team_name,leader_name,leader_phone,member_2,member_3,member_4,college
Team Alpha,John Doe,9876543210,Jane Smith,Bob Lee,,MIT
```

**Response (200):**
```json
{
  "success": true,
  "teams_created": 175,
  "teams_failed": 0,
  "question_sets_assigned": 175,
  "errors": [],
  "summary": {
    "total_rows": 175,
    "duplicates_skipped": 0,
    "validation_errors": 0
  }
}
```

**Response (400 - Validation Error):**
```json
{
  "success": false,
  "error": "CSV validation failed",
  "details": [
    {"row": 5, "error": "Invalid phone number format"},
    {"row": 12, "error": "Duplicate team name"}
  ]
}
```

**Transaction Boundary:**
- Atomic: All teams + question assignments OR rollback
- If question set collision detected after 10 retries, fail entire batch

---

#### POST /admin/questions
Create a new question with test cases.

**Request:**
```json
{
  "title": "Two Sum",
  "difficulty": "easy",
  "prompt_markdown": "Given an array of integers...",
  "starter_code_python": "def two_sum(nums, target):\n    pass",
  "starter_code_cpp": "vector<int> twoSum(vector<int>& nums, int target) {\n    \n}",
  "starter_code_java": null,
  "starter_code_javascript": null,
  "time_limit_seconds": 5,
  "memory_limit_mb": 256,
  "sample_test_cases": [
    {
      "input_data": "[2,7,11,15]\n9",
      "expected_output": "[0,1]",
      "explanation": "nums[0] + nums[1] = 2 + 7 = 9"
    }
  ],
  "hidden_test_cases": [
    {
      "input_data": "[3,2,4]\n6",
      "expected_output": "[1,2]"
    },
    {
      "input_data": "[3,3]\n6",
      "expected_output": "[0,1]"
    }
  ]
}
```

**Response (201):**
```json
{
  "id": 42,
  "title": "Two Sum",
  "difficulty": "easy",
  "marks": 5,
  "sample_test_cases_count": 1,
  "hidden_test_cases_count": 2,
  "created_at": "2026-08-19T10:30:00Z"
}
```

**Marks Auto-Assignment:**
- `easy` → 5 marks
- `medium` → 10 marks
- `hard` → 20 marks

---

#### PATCH /admin/questions/:id
Update existing question (affects only future assignments).

**Request:**
```json
{
  "title": "Two Sum (Updated)",
  "prompt_markdown": "Updated description...",
  "is_active": true
}
```

**Response (200):**
```json
{
  "id": 42,
  "updated_at": "2026-08-19T11:00:00Z",
  "affected_teams": 0
}
```

**Note:** Existing team assignments are NOT affected. Only new assignments use updated question.

---

#### POST /admin/test/configure
Set test timing and rules.

**Request:**
```json
{
  "test_open_at": "2026-08-20T09:00:00Z",
  "test_close_at": "2026-08-20T21:00:00Z",
  "duration_minutes": 120,
  "synchronized_start": true,
  "global_start_time": "2026-08-20T10:00:00Z",
  "allow_team_view_leaderboard": false
}
```

**Response (200):**
```json
{
  "configuration_updated": true,
  "test_window": {
    "opens": "2026-08-20T09:00:00Z",
    "closes": "2026-08-20T21:00:00Z",
    "duration_minutes": 120
  },
  "synchronized_start": true,
  "global_start_time": "2026-08-20T10:00:00Z"
}
```

---

#### POST /admin/grading/:submission_id/override
Manually override auto-graded score.

**Request:**
```json
{
  "marks_awarded": 10,
  "reason": "Partial credit for correct algorithm with minor syntax error"
}
```

**Response (200):**
```json
{
  "submission_id": 1234,
  "original_marks": 0,
  "new_marks": 10,
  "overridden_by": "admin_user",
  "overridden_at": "2026-08-19T12:00:00Z",
  "leaderboard_recalculated": true
}
```

**Side Effects:**
1. Update `GradingResult.marks_awarded`
2. Store original marks in `GradingResult.original_marks`
3. Recalculate `TestSession.total_score`
4. Recalculate leaderboard ranks

**Audit Log Entry:**
```json
{
  "action": "grade_override",
  "object_type": "submission",
  "object_id": 1234,
  "old_value": "0",
  "new_value": "10",
  "reason": "Partial credit for correct algorithm with minor syntax error"
}
```

---

#### GET /admin/leaderboard
Fetch full leaderboard with detailed scores.

**Response (200):**
```json
{
  "leaderboard": [
    {
      "rank": 1,
      "team_id": 42,
      "team_name": "Team Alpha",
      "total_score": 245,
      "time_taken_seconds": 5400,
      "time_taken_formatted": "1h 30m",
      "score_breakdown": {
        "easy_score": 50,
        "medium_score": 90,
        "hard_score": 100
      },
      "questions_attempted": 25,
      "questions_solved": 24,
      "submitted_at": "2026-08-20T11:30:00Z"
    }
  ],
  "total_teams": 175,
  "teams_submitted": 168,
  "teams_in_progress": 5,
  "teams_not_started": 2
}
```

---

#### GET /admin/export/results
Export all results as CSV/Excel/PDF.

**Query Params:**
- `format=csv|excel|pdf`

**Response (200):**
```
Content-Type: text/csv
Content-Disposition: attachment; filename="results_2026-08-20.csv"

rank,team_name,total_score,time_taken,easy_score,medium_score,hard_score
1,Team Alpha,245,5400,50,90,100
2,Team Beta,240,5100,50,100,90
```

---

### 1.2 Team Routes

**Base Path:** `/api/teams`

#### POST /teams/test/start
Start the test timer for a team.

**Request:**
```json
{}
```

**Response (200):**
```json
{
  "test_started": true,
  "started_at": "2026-08-20T10:00:00Z",
  "expires_at": "2026-08-20T12:00:00Z",
  "duration_minutes": 120,
  "questions_count": 25,
  "auto_submit_warning": "Test will auto-submit at expiry"
}
```

**Response (400 - Already Started):**
```json
{
  "error": "Test already started",
  "started_at": "2026-08-20T10:00:00Z",
  "time_remaining_seconds": 3600
}
```

**Response (403 - Outside Test Window):**
```json
{
  "error": "Test not available",
  "test_opens_at": "2026-08-20T09:00:00Z",
  "test_closes_at": "2026-08-20T21:00:00Z"
}
```

**Side Effects:**
1. Set `TestSession.test_started_at = NOW()`
2. Set `TestSession.status = IN_PROGRESS`
3. Schedule auto-submit job for `NOW() + 120 minutes`

---

#### GET /teams/questions
Fetch the team's assigned 25 questions.

**Response (200):**
```json
{
  "questions": [
    {
      "position": 1,
      "question_id": 42,
      "title": "Two Sum",
      "difficulty": "easy",
      "marks": 5,
      "prompt_markdown": "Given an array...",
      "starter_code": {
        "python": "def two_sum(nums, target):\n    pass",
        "cpp": "vector<int> twoSum(vector<int>& nums, int target) {\n    \n}",
        "java": null,
        "javascript": null
      },
      "sample_test_cases": [
        {
          "input": "[2,7,11,15]\n9",
          "expected_output": "[0,1]",
          "explanation": "nums[0] + nums[1] = 2 + 7 = 9"
        }
      ],
      "time_limit_seconds": 5,
      "memory_limit_mb": 256,
      "submission_status": null
    }
  ],
  "test_status": {
    "started_at": "2026-08-20T10:00:00Z",
    "time_remaining_seconds": 6000,
    "auto_submit_at": "2026-08-20T12:00:00Z"
  }
}
```

**Business Rules:**
- Hidden test cases are NEVER returned
- Questions ordered by `position` (1-25)
- `submission_status` populated from most recent submission

---

#### POST /teams/submissions/:question_id/autosave
Autosave code without submitting for grading.

**Request:**
```json
{
  "code": "def two_sum(nums, target):\n    return [0, 1]",
  "language": "python"
}
```

**Response (200):**
```json
{
  "autosaved": true,
  "saved_at": "2026-08-20T10:15:30Z",
  "recoverable": true
}
```

**Side Effects:**
1. Insert `Submission` with `is_final = false`
2. NO grading triggered
3. Used for recovery if browser crashes

**Idempotency:** Multiple autosaves create new rows (timestamped snapshots)

---

#### POST /teams/submissions/:question_id/submit
Submit code for final grading.

**Request:**
```json
{
  "code": "def two_sum(nums, target):\n    hash_map = {}\n    for i, num in enumerate(nums):\n        complement = target - num\n        if complement in hash_map:\n            return [hash_map[complement], i]\n        hash_map[num] = i",
  "language": "python"
}
```

**Response (202 Accepted):**
```json
{
  "submission_id": 5678,
  "status": "queued",
  "message": "Submission queued for grading",
  "estimated_grading_time_seconds": 15,
  "check_status_url": "/api/teams/submissions/5678/status"
}
```

**Side Effects:**
1. Insert `Submission` with `is_final = true`
2. Add to grading queue (NOT immediate Piston call)
3. Async worker picks up and grades

**Idempotency:**
- If duplicate `submit` called, return existing submission
- Check: `team_id + question_id + is_final = true` already exists

---

#### GET /teams/submissions/:submission_id/status
Check grading status of a submission.

**Response (200 - Grading Complete):**
```json
{
  "submission_id": 5678,
  "status": "graded",
  "grading_result": {
    "marks_awarded": 5,
    "passed_tests": 3,
    "total_tests": 3,
    "execution_time_ms": 45,
    "memory_used_mb": 12.5,
    "test_results": [
      {
        "test_case": 1,
        "passed": true,
        "execution_time_ms": 15
      },
      {
        "test_case": 2,
        "passed": true,
        "execution_time_ms": 14
      },
      {
        "test_case": 3,
        "passed": true,
        "execution_time_ms": 16
      }
    ]
  }
}
```

**Response (200 - Still Grading):**
```json
{
  "submission_id": 5678,
  "status": "grading",
  "queue_position": 23,
  "estimated_time_remaining_seconds": 45
}
```

**Response (200 - Grading Failed):**
```json
{
  "submission_id": 5678,
  "status": "error",
  "error": "Compilation error",
  "error_output": "SyntaxError: invalid syntax on line 3",
  "marks_awarded": 0
}
```

---

#### POST /teams/test/submit-final
Submit entire test (all 25 questions).

**Request:**
```json
{}
```

**Response (200):**
```json
{
  "test_submitted": true,
  "submitted_at": "2026-08-20T11:45:00Z",
  "time_taken_seconds": 6300,
  "time_taken_formatted": "1h 45m",
  "questions_submitted": 23,
  "questions_pending_grade": 2,
  "preliminary_score": 180,
  "message": "Test submitted successfully. Final scores will be available once all submissions are graded."
}
```

**Side Effects:**
1. Set `TestSession.submitted_at = NOW()`
2. Set `TestSession.status = SUBMITTED`
3. Calculate `time_taken_seconds = submitted_at - test_started_at`
4. Trigger final score calculation once all grading complete

**Idempotency:** If already submitted, return existing submission data

---

#### GET /teams/leaderboard
View leaderboard (if admin allows).

**Response (200):**
```json
{
  "leaderboard_published": true,
  "your_rank": 15,
  "your_score": 200,
  "top_10": [
    {
      "rank": 1,
      "team_name": "Team Alpha",
      "total_score": 245,
      "time_taken_formatted": "1h 30m"
    }
  ]
}
```

**Response (403 - Not Published):**
```json
{
  "error": "Leaderboard not yet published by admin"
}
```

---

## 2. Data Flow Pipelines

### 2.1 Submission → Grading → Leaderboard Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  TEAM SUBMITS CODE                                          │
│  POST /teams/submissions/:question_id/submit                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  SUBMISSION HANDLER                                         │
│  1. Validate: Test in progress? Question assigned?         │
│  2. Check idempotency: Already submitted?                  │
│  3. Insert Submission (is_final=true)                      │
│  4. Enqueue to GradingQueue (Redis/DB)                     │
│  5. Return 202 Accepted                                    │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  GRADING QUEUE (Redis Sorted Set or DB Table)              │
│  - Priority: timestamp ASC (FIFO)                          │
│  - Deduplication: submission_id unique                     │
│  - Retry: exponential backoff on failure                   │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  GRADING WORKER (Background Process)                       │
│  - Consumes queue at rate limit (10 req/sec to Piston)    │
│  - Retry logic: 3 attempts with backoff                   │
│  - Timeout: 30 seconds per Piston call                    │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  PISTON API CALL                                            │
│  POST https://emkc.org/api/v2/piston/execute              │
│  {                                                          │
│    "language": "python",                                    │
│    "version": "3.11",                                       │
│    "files": [{"content": "<user_code>"}],                  │
│    "stdin": "<test_input>",                                 │
│    "args": [],                                              │
│    "compile_timeout": 10000,                                │
│    "run_timeout": 5000,                                     │
│    "compile_memory_limit": 256000000,                       │
│    "run_memory_limit": 256000000                            │
│  }                                                          │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  PISTON RESPONSE PARSER                                     │
│  {                                                          │
│    "run": {                                                 │
│      "stdout": "output",                                    │
│      "stderr": "",                                          │
│      "code": 0,                                             │
│      "signal": null,                                        │
│      "output": "output"                                     │
│    }                                                        │
│  }                                                          │
│  - Compare stdout with expected_output (strip whitespace)  │
│  - Mark test as passed/failed                              │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  GRADING RESULT CALCULATION                                 │
│  - Run all hidden test cases                               │
│  - Calculate: (passed / total) × marks                     │
│  - All-or-nothing: Need 100% pass for full marks           │
│  - Insert GradingResult with detailed test_results JSON    │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  SCORE AGGREGATION                                          │
│  - Update TestSession.total_score                          │
│  - Update TestSession.easy_score / medium_score / hard     │
│  - Trigger leaderboard rank recalculation                  │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  LEADERBOARD RECALCULATION                                  │
│  ORDER BY total_score DESC, time_taken_seconds ASC         │
│  - Update TestSession.rank for all teams                   │
│  - Cache top 100 in Redis for fast reads                   │
└─────────────────────────────────────────────────────────────┘
```

---

### 2.2 Auto-Submit at Timer Expiry

**Problem:** 175 teams × 25 questions = 4,375 submissions potentially queued at 12:00:00 PM

**Solution: Staggered Auto-Submit**

```
┌─────────────────────────────────────────────────────────────┐
│  TIMER EXPIRY DETECTION (Scheduled Job every 10 seconds)   │
│  - Query: TestSession.status = IN_PROGRESS                 │
│           AND test_started_at + duration < NOW()           │
│  - Found: 175 teams need auto-submit                       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  BATCH AUTO-SUBMIT (Process in chunks)                     │
│  - Chunk size: 25 teams per batch                          │
│  - Delay between batches: 5 seconds                        │
│  - Total time: 175 / 25 × 5s = 35 seconds                  │
│                                                             │
│  For each team in batch:                                   │
│    1. Fetch all autosaved submissions (is_final=false)    │
│    2. Mark them as is_final=true (if no final submit yet) │
│    3. Set TestSession.status = AUTO_SUBMITTED              │
│    4. Set TestSession.submitted_at = test_expired_at       │
│    5. Enqueue all 25 submissions to grading queue          │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  GRADING QUEUE (Now has 4,375 submissions)                 │
│  - Worker processes at 10 req/sec (Piston rate limit)     │
│  - Time to complete: 4,375 / 10 = ~7.3 minutes            │
│  - Teams see "Grading in progress" status                  │
└─────────────────────────────────────────────────────────────┘
```

**Key Design Decision:**
- Auto-submit does NOT mean instant grading
- Teams marked as "AUTO_SUBMITTED" immediately
- Grading happens asynchronously over ~7-10 minutes
- Leaderboard updates incrementally as grading completes

---

### 2.3 Partial Submission Recovery

**Scenario:** Team's browser crashes at 11:30 AM (30 minutes into test)

**Recovery Mechanism:**

```
┌─────────────────────────────────────────────────────────────┐
│  TEAM LOGS BACK IN                                          │
│  - JWT token still valid (2 hour expiry)                   │
│  - TestSession.status = IN_PROGRESS                        │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  GET /teams/questions (Frontend loads)                      │
│  - Returns all 25 questions                                 │
│  - submission_status field populated from DB                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND RECOVERY LOGIC                                    │
│  For each question:                                         │
│    - Query: Latest submission (is_final=false) for Q       │
│    - If found: Load code into editor                        │
│    - If not found: Show starter code                        │
│                                                             │
│  Result: Team recovers all autosaved work                   │
└─────────────────────────────────────────────────────────────┘
```

**Autosave Strategy:**
- Frequency: Every 30 seconds when code changes
- Endpoint: `POST /teams/submissions/:question_id/autosave`
- Storage: New `Submission` row with `is_final = false`
- No grading triggered (saves API calls)

**Edge Case:**
- If team manually submits Q5 (is_final=true), autosaves for Q5 are ignored

---

## 3. Rate Limiting & Queue Management

### 3.1 Piston API Rate Limits

**Observed Limits (from Piston docs):**
- Free tier: 10 requests/second
- Burst: Up to 20 req/sec for 10 seconds

**Our Strategy:**
- Conservative: 10 req/sec sustained
- No bursting (to avoid 429 errors)

**Implementation:**

```python
# grading_worker.py
import asyncio
import httpx
from datetime import datetime, timedelta

class PistonRateLimiter:
    def __init__(self, rate_limit=10):
        self.rate_limit = rate_limit  # req/sec
        self.min_interval = 1.0 / rate_limit  # 0.1 seconds
        self.last_request_time = None
    
    async def acquire(self):
        """Wait if necessary to respect rate limit"""
        if self.last_request_time:
            elapsed = (datetime.utcnow() - self.last_request_time).total_seconds()
            wait_time = self.min_interval - elapsed
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        
        self.last_request_time = datetime.utcnow()

rate_limiter = PistonRateLimiter(rate_limit=10)

async def grade_submission(submission_id):
    await rate_limiter.acquire()
    # Make Piston API call
    ...
```

---

### 3.2 Grading Queue Design

**Option A: Redis Sorted Set (Recommended)**

```python
# Queue: Redis ZADD with timestamp as score
redis_client.zadd("grading_queue", {submission_id: timestamp})

# Dequeue: ZPOPMIN (atomic pop lowest score)
submission_id = redis_client.zpopmin("grading_queue", count=1)

# Queue position
position = redis_client.zrank("grading_queue", submission_id)
```

**Benefits:**
- Atomic operations (no race conditions)
- FIFO ordering by timestamp
- Fast queue position lookup
- Persistent (survives worker crashes)

**Option B: Database Table (Fallback if no Redis)**

```sql
CREATE TABLE grading_queue (
    submission_id INTEGER PRIMARY KEY,
    enqueued_at TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, failed
    retry_count INTEGER DEFAULT 0,
    next_retry_at TIMESTAMP,
    INDEX idx_status_enqueued (status, enqueued_at)
);

-- Dequeue with pessimistic locking
BEGIN;
SELECT submission_id 
FROM grading_queue 
WHERE status = 'pending' 
ORDER BY enqueued_at ASC 
LIMIT 1 
FOR UPDATE SKIP LOCKED;

UPDATE grading_queue SET status = 'processing' WHERE submission_id = ?;
COMMIT;
```

**Benefits:**
- No Redis dependency
- Transactional safety
- `SKIP LOCKED` prevents race conditions

---

### 3.3 Retry Logic

**When to Retry:**
- Network timeout (30 sec)
- Piston 429 (rate limit exceeded)
- Piston 5xx (server error)

**When NOT to Retry:**
- Piston 400 (invalid request)
- Code execution error (compilation error, runtime error)

**Retry Strategy:**

```python
import asyncio
from httpx import HTTPStatusError, TimeoutException

async def execute_with_retry(submission_id, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = await call_piston_api(submission_id)
            return result
        
        except TimeoutException:
            if attempt < max_retries - 1:
                backoff = 2 ** attempt  # 1s, 2s, 4s
                await asyncio.sleep(backoff)
            else:
                # Final failure: Mark as error
                mark_grading_failed(submission_id, "Timeout after 3 retries")
        
        except HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited: Wait longer
                await asyncio.sleep(10)
            elif e.response.status_code >= 500:
                # Server error: Retry with backoff
                backoff = 2 ** attempt
                await asyncio.sleep(backoff)
            else:
                # Client error: Don't retry
                mark_grading_failed(submission_id, f"Client error: {e}")
                break
```

---

### 3.4 Idempotency Guarantees

**Problem:** If Piston call times out, did it execute or not?

**Solution: Submission ID as Idempotency Key**

```python
# Before calling Piston
grading_result = db.query(GradingResult).filter(
    GradingResult.submission_id == submission_id
).first()

if grading_result:
    # Already graded (duplicate or retry)
    return grading_result

# Proceed with grading
result = await call_piston_api(submission_id)

# Store result atomically
db.add(GradingResult(submission_id=submission_id, ...))
db.commit()
```

**Key Insight:**
- `GradingResult.submission_id` is UNIQUE constraint
- Second attempt to insert will fail (database enforces idempotency)
- Check before calling Piston to save API quota

---

## 4. Transaction Boundaries

### 4.1 CSV Upload Transaction

**Scope:**
```
BEGIN TRANSACTION;
  INSERT INTO teams (175 rows);
  INSERT INTO test_sessions (175 rows);
  INSERT INTO team_question_assignments (175 × 25 = 4,375 rows);
  INSERT INTO used_question_sets (175 rows);
COMMIT;
```

**Failure Handling:**
- Any failure → ROLLBACK entire batch
- No partial teams created
- Admin sees error report with failing row numbers
- Can fix CSV and retry

**Performance:**
- Batch insert for speed: `db.bulk_insert_mappings()`
- Expected time: ~5 seconds for 175 teams

---

### 4.2 Grade Override Transaction

**Scope:**
```
BEGIN TRANSACTION;
  UPDATE grading_results SET marks_awarded = ? WHERE submission_id = ?;
  
  -- Recalculate team total score
  UPDATE test_sessions 
  SET total_score = (
    SELECT COALESCE(SUM(gr.marks_awarded), 0)
    FROM submissions s
    JOIN grading_results gr ON s.id = gr.submission_id
    WHERE s.team_id = ? AND s.is_final = true
  )
  WHERE team_id = ?;
  
  -- Recalculate ranks (all teams)
  WITH ranked AS (
    SELECT id, ROW_NUMBER() OVER (
      ORDER BY total_score DESC, time_taken_seconds ASC
    ) as new_rank
    FROM test_sessions
    WHERE status IN ('SUBMITTED', 'AUTO_SUBMITTED')
  )
  UPDATE test_sessions ts
  SET rank = ranked.new_rank
  FROM ranked
  WHERE ts.id = ranked.id;
  
  INSERT INTO audit_logs (...);
COMMIT;
```

**Why Atomic:**
- Score and rank must be consistent
- Leaderboard readers must never see stale ranks

**Performance:**
- Rank recalculation is O(n log n) with 175 teams
- Fast enough for synchronous execution (<100ms)

---

### 4.3 Test Submission Transaction

**Scope:**
```
BEGIN TRANSACTION;
  UPDATE test_sessions 
  SET 
    submitted_at = NOW(),
    status = 'SUBMITTED',
    time_taken_seconds = EXTRACT(EPOCH FROM (NOW() - test_started_at))
  WHERE team_id = ? AND status = 'IN_PROGRESS';
  
  -- Mark all pending autosaves as final (if not already submitted)
  UPDATE submissions
  SET is_final = true
  WHERE team_id = ? 
    AND is_final = false
    AND question_id NOT IN (
      SELECT question_id FROM submissions 
      WHERE team_id = ? AND is_final = true
    );
COMMIT;
```

**Why Atomic:**
- Test submission is a one-time event
- Prevents race condition if team clicks "Submit" twice

**Idempotency:**
- `WHERE status = 'IN_PROGRESS'` ensures single execution
- Second submit attempt is no-op

---

## 5. Frontend Considerations

### 5.1 Autosave Implementation

**React/Next.js Pattern:**

```typescript
// useAutosave.ts
import { useEffect, useRef } from 'react';
import { debounce } from 'lodash';

export function useAutosave(
  questionId: number,
  code: string,
  language: string
) {
  const autosaveTimer = useRef<NodeJS.Timeout>();
  
  const saveCode = debounce(async () => {
    await fetch(`/api/teams/submissions/${questionId}/autosave`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, language })
    });
  }, 30000); // 30 seconds
  
  useEffect(() => {
    if (code) {
      saveCode();
    }
    return () => saveCode.cancel();
  }, [code, language]);
}
```

**Key Points:**
- Debounce: Wait 30 seconds of inactivity
- Cancel on unmount (prevent stale saves)
- Visual indicator: "Saved 2 minutes ago"

---

### 5.2 Submission Polling

**After submitting code, poll for grading result:**

```typescript
async function pollGradingStatus(submissionId: number) {
  const maxAttempts = 60; // 1 minute max
  const interval = 1000; // 1 second
  
  for (let i = 0; i < maxAttempts; i++) {
    const response = await fetch(`/api/teams/submissions/${submissionId}/status`);
    const data = await response.json();
    
    if (data.status === 'graded' || data.status === 'error') {
      return data;
    }
    
    // Show queue position
    console.log(`Queue position: ${data.queue_position}`);
    
    await sleep(interval);
  }
  
  throw new Error('Grading timeout');
}
```

**UX:**
- Show spinner: "Grading in progress..."
- Show queue position: "23 submissions ahead"
- Timeout after 60 seconds: "Grading taking longer than expected. Check back soon."

---

### 5.3 Timer Display

**Synchronized countdown:**

```typescript
function TestTimer({ expiresAt }: { expiresAt: Date }) {
  const [timeLeft, setTimeLeft] = useState(calculateTimeLeft(expiresAt));
  
  useEffect(() => {
    const timer = setInterval(() => {
      const left = calculateTimeLeft(expiresAt);
      setTimeLeft(left);
      
      if (left <= 0) {
        // Auto-submit warning
        alert('Time expired! Submitting test...');
        submitTest();
      }
    }, 1000);
    
    return () => clearInterval(timer);
  }, [expiresAt]);
  
  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;
  
  return (
    <div className={minutes < 5 ? 'text-red-600' : 'text-gray-700'}>
      {minutes}:{seconds.toString().padStart(2, '0')}
    </div>
  );
}
```

**Visual Warnings:**
- Red text when < 5 minutes remaining
- Flashing border when < 1 minute
- Modal warning at 30 seconds

---

## 6. Monitoring & Observability

### 6.1 Key Metrics to Track

**Queue Health:**
- Grading queue depth (target: < 100)
- Average time in queue (target: < 30 seconds)
- Worker throughput (target: 10 req/sec)

**API Performance:**
- Piston API latency (P50, P95, P99)
- Piston error rate (target: < 1%)
- Submission endpoint latency (target: < 200ms)

**Business Metrics:**
- Teams logged in
- Tests started
- Tests submitted
- Average score
- Questions with highest failure rate

### 6.2 Alerts

**Critical:**
- Grading queue > 500 submissions
- Piston API error rate > 5%
- Worker crashed (no grading for 5 minutes)

**Warning:**
- Grading queue > 200 submissions
- Piston API latency P95 > 10 seconds

---

## 7. Deployment Architecture

### 7.1 Production Setup

```
┌─────────────────────────────────────────────────────────────┐
│  Load Balancer (Railway/Render/Nginx)                      │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI Web Server (Uvicorn)                              │
│  - Handles HTTP requests                                    │
│  - JWT validation                                           │
│  - Enqueues submissions                                     │
│  - 2 instances (horizontal scale)                           │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL Database                                        │
│  - Single primary instance                                  │
│  - Connection pooling (max 20 connections)                 │
│  - Managed service (Railway/Render)                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Redis (Optional, for queue)                                │
│  - Grading queue storage                                    │
│  - Leaderboard cache                                        │
│  - Managed service (Railway Redis)                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Grading Worker (Separate Process)                         │
│  - python grading_worker.py                                 │
│  - Consumes grading queue                                   │
│  - Calls Piston API (rate limited)                          │
│  - 1 instance (serial processing by design)                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Scheduled Tasks (APScheduler or Celery Beat)               │
│  - Auto-submit expired tests (every 10 seconds)            │
│  - Recalculate leaderboard ranks (every 1 minute)          │
└─────────────────────────────────────────────────────────────┘
```

---

### 7.2 Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Redis (optional)
REDIS_URL=redis://host:6379/0

# Authentication
SECRET_KEY=<64-char-random-string>
ADMIN_PASSWORD=<secure-password>

# Piston API
PISTON_API_URL=https://emkc.org/api/v2/piston
PISTON_RATE_LIMIT=10

# Test Configuration
DEFAULT_TEST_DURATION_MINUTES=120
ACCESS_TOKEN_EXPIRE_MINUTES=180

# CORS
CORS_ORIGINS=https://your-frontend.vercel.app
```

---

## 8. Testing Strategy

### 8.1 Load Testing

**Scenario: 175 Teams Simultaneous Start**

```bash
# Using Locust or Apache Bench
locust -f load_test.py --users 175 --spawn-rate 25 --host https://api.example.com

# Target endpoints:
# - POST /api/teams/test/start (175 concurrent)
# - GET /api/teams/questions (175 concurrent)
# - POST /api/teams/submissions/:id/submit (4,375 over 2 hours)
```

**Success Criteria:**
- All 175 teams can start within 10 seconds
- No 500 errors
- API P95 latency < 1 second

---

### 8.2 Grading Accuracy Tests

```python
# Create synthetic test data
test_cases = [
    ("def two_sum(nums, target): return [0, 1]", "python", 5),  # Hardcoded
    ("def two_sum(nums, target): return []", "python", 0),      # Wrong
    ("syntax error here", "python", 0),                         # Compile error
]

for code, lang, expected_marks in test_cases:
    submission = submit_code(team_id=1, question_id=1, code=code, language=lang)
    result = poll_grading_status(submission.id)
    assert result.marks_awarded == expected_marks
```

---

## 9. Security Considerations

### 9.1 Code Injection Prevention

**Risk:** Malicious code in submissions

**Mitigation:**
- Piston API runs in isolated containers (out-of-the-box)
- Time limits: 5 seconds per execution
- Memory limits: 256 MB per execution
- No network access from executed code
- No file system write access

**Additional Safeguards:**
- Blacklist dangerous imports (optional):
  ```python
  BANNED_IMPORTS = ["os", "subprocess", "socket", "requests"]
  if any(imp in code for imp in BANNED_IMPORTS):
      return {"error": "Forbidden import detected"}
  ```

---

### 9.2 Rate Limiting (Anti-Abuse)

**Endpoints to Protect:**

| Endpoint | Limit | Window |
|----------|-------|--------|
| POST /api/auth/team/login | 5 attempts | 15 min |
| POST /api/teams/submissions/*/submit | 25 total | test duration |
| POST /api/teams/submissions/*/autosave | 1 req | 10 sec |
| GET /api/teams/questions | 10 req | 1 min |

**Implementation:**

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/submissions/{question_id}/submit")
@limiter.limit("25/day")  # Per IP
async def submit_code(...):
    ...
```

---

## 10. Rollout Plan

### Phase 1: Admin Setup (1 day before)
1. Admin logs in
2. Uploads 175 teams CSV
3. Configures test window (9 AM - 9 PM)
4. Sets synchronized start time (10 AM)
5. Verifies question bank (175+ questions active)

### Phase 2: Team Access (Test day 9 AM)
1. Teams can log in and see countdown
2. "Test starts at 10:00 AM" message

### Phase 3: Test Start (10:00 AM)
1. All teams click "Start Test" button
2. Timer begins (2 hours)
3. Questions loaded
4. Autosave begins

### Phase 4: Test In Progress (10:00 - 12:00)
1. Teams submit answers
2. Grading queue processes submissions
3. Admin monitors queue depth

### Phase 5: Auto-Submit (12:00 PM)
1. Scheduled job detects expired tests
2. Batch auto-submit (175 teams over 35 seconds)
3. 4,375 submissions queued
4. Grading completes over ~7 minutes

### Phase 6: Results (12:10 PM)
1. Admin publishes leaderboard
2. Teams can view final scores
3. Admin exports results CSV

---

## 11. Open Questions & Decisions Needed

### Q1: Synchronized Start vs. Individual Timers?
**Current Design:** Synchronized (all start at 10 AM)

**Alternative:** Individual timers (each team has 120 min from their start time)

**Decision:** Confirm with stakeholders

---

### Q2: Grading: All-or-Nothing vs. Partial Credit?
**Current Design:** All-or-nothing (need 100% test pass for full marks)

**Alternative:** Partial credit (e.g., 3/5 tests passed = 60% marks)

**Recommendation:** All-or-nothing (simpler, avoids gaming)

**Decision:** Confirm with stakeholders

---

### Q3: Redis Required or Optional?
**Current Design:** Optional (fallback to DB-based queue)

**Trade-off:**
- Redis: Faster, more scalable
- DB-only: Simpler deployment, no extra service

**Recommendation:** Start with DB, add Redis if queue depth becomes issue

**Decision:** Start without Redis, add if needed

---

## 12. Success Criteria

### Technical
- ✅ 175 teams can start test within 10 seconds
- ✅ Zero data loss (all autosaves recoverable)
- ✅ Grading completes within 10 minutes of timer expiry
- ✅ Leaderboard accurate (correct tiebreaker logic)
- ✅ Zero code injection incidents

### Business
- ✅ Admin can upload teams in < 5 seconds
- ✅ Admin can override grades with audit trail
- ✅ Teams see clear submission status (grading vs. graded)
- ✅ Export results in CSV/Excel/PDF

---

## 13. Next Steps

1. **Review & Approve Design** (this document)
2. **Implement Admin Routes** (CSV upload, question CRUD)
3. **Implement Team Routes** (start test, submit code)
4. **Implement Grading Worker** (Piston integration)
5. **Implement Leaderboard Service**
6. **Build Frontend** (Next.js + TypeScript)
7. **Load Testing** (175 concurrent users)
8. **Production Deployment** (Railway/Render)

---

**Document Status:** Draft v1.0
**Last Updated:** 2026-08-19
**Author:** Kiro AI
**Next Review:** After stakeholder feedback
