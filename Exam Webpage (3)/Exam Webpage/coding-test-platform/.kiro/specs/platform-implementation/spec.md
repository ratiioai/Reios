# Spec: Coding Test Platform Implementation

**Status:** in-progress
**Created:** 2026-08-19
**Last Updated:** 2026-08-19

---

## Overview

This spec covers the complete implementation of a production-ready coding test platform for 175 teams with auto-grading, unique question sets, and live leaderboard.

**Foundation Status:** ✅ Complete
- Database models (SQLAlchemy ORM)
- Authentication (JWT + bcrypt)
- CSV import utility
- Question assignment with collision detection
- FastAPI application structure

**Next Phase:** Backend routes, grading infrastructure, and frontend

---

## Key Design Decisions

### 1. Grading Queue with Rate Limiting
**Problem:** 4,375 submissions potentially queued at timer expiry could overwhelm Piston API (10 req/sec limit)

**Solution:**
- Submissions enqueued immediately (202 Accepted response)
- Background worker processes queue at 10 req/sec
- Staggered auto-submit: 25 teams per batch, 5-sec delay
- Redis or database-based queue with FIFO ordering
- Retry logic: 3 attempts with exponential backoff

**Impact:** Grading completes in ~7-10 minutes vs. instant (acceptable trade-off)

---

### 2. Idempotency on All Write Operations
**Problem:** Network timeouts could cause duplicate submissions or double-grading

**Solution:**
- Check `Submission` uniqueness: `team_id + question_id + is_final = true`
- Check `GradingResult.submission_id` UNIQUE constraint before calling Piston
- Test submission idempotent: `WHERE status = IN_PROGRESS` (only updates once)

**Impact:** Safe to retry on timeout without side effects

---

### 3. Partial Submission Recovery
**Problem:** Browser crash mid-test could lose all work

**Solution:**
- Autosave endpoint: `POST /submissions/:id/autosave` (no grading)
- Creates `Submission` row with `is_final = false`
- Frontend polls autosaves on page load
- Autosave frequency: 30 seconds (debounced)

**Impact:** Zero data loss even with browser crashes

---

### 4. Transaction Boundaries
**Critical Atomic Operations:**
1. **CSV Upload:** All 175 teams + question assignments OR rollback
2. **Grade Override:** Update marks + recalculate total score + recalculate ranks
3. **Test Submission:** Update status + mark autosaves as final + calculate time taken

**Impact:** Data consistency guaranteed

---

### 5. All-or-Nothing Grading
**Decision:** Need 100% hidden test pass for full marks (no partial credit)

**Rationale:**
- Simpler to implement and explain
- Prevents gaming (hardcoding edge cases)
- Industry standard (LeetCode, HackerRank use this)

**Alternative:** Can be changed to partial credit in `grading_service.py` if needed

---

## API Structure

### Admin Routes (`/api/admin`)
1. CSV upload with validation
2. Question CRUD (create, read, update, delete)
3. Test configuration (timing, duration)
4. Grade override with audit trail
5. Leaderboard management
6. Results export (CSV, Excel, PDF)

### Team Routes (`/api/teams`)
1. Start test (begin timer)
2. Fetch questions (assigned 25-question set)
3. Autosave code (recovery mechanism)
4. Submit code (enqueue for grading)
5. Poll grading status (with queue position)
6. Submit final test (manual submission)
7. View leaderboard (if published)

### Auth Routes (`/api/auth`)
1. Admin login
2. Team login (team_name + phone hash)
3. Token verification

---

## Files

### Requirements
- [requirements.md](./requirements.md) - Functional and non-functional requirements with acceptance criteria

### Design
- [design.md](./design.md) - Technical architecture, API contracts, data flows, scaling strategies

### Tasks
- [tasks.md](./tasks.md) - 15 implementation tasks with priorities and dependencies

---

## Progress Tracking

### Phase 1: Foundation ✅ Complete
- [x] Database models
- [x] Authentication utilities
- [x] CSV import
- [x] Question assignment
- [x] FastAPI app structure

### Phase 2: Backend Core 🔄 In Progress
- [ ] Task 1: Grading queue & worker infrastructure
- [ ] Task 2: Admin routes - CSV & questions
- [ ] Task 3: Admin routes - test config & overrides
- [ ] Task 4: Team routes - test session
- [ ] Task 5: Team routes - submissions & autosave
- [ ] Task 6: Grading service - Piston integration
- [ ] Task 7: Auto-submit scheduler
- [ ] Task 8: Final test submission
- [ ] Task 9: Leaderboard service
- [ ] Task 10: Export service

### Phase 3: Frontend 🔜 Not Started
- [ ] Task 11: Auth & layout
- [ ] Task 12: Team dashboard
- [ ] Task 13: Admin dashboard

### Phase 4: Launch 🔜 Not Started
- [ ] Task 14: Load testing & optimization
- [ ] Task 15: Deployment & monitoring

---

## Timeline Estimate

**Backend:** 5-7 days (Tasks 1-10)
**Frontend:** 3-4 days (Tasks 11-13)
**Testing & Deploy:** 2-3 days (Tasks 14-15)

**Total:** 10-14 days (single developer, full-time)

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Piston API rate limits | High | Queue with 10 req/sec limiter, retry logic |
| 175 simultaneous starts | Medium | Load test early, optimize DB queries |
| Browser crash data loss | High | Autosave every 30 seconds |
| Grading timeout | Medium | 3 retries with backoff, mark as error if all fail |
| Grade override inconsistency | High | Transaction wraps score + rank recalculation |
| Question set collision | Low | 10 retries, fail CSV upload if exhausted |

---

## Next Steps

1. **Review Design Document** - Validate API contracts and data flows
2. **Start Task 1** - Grading queue (critical path)
3. **Parallel Track** - Frontend can start using API contracts from design doc
4. **Weekly Check-ins** - Review progress, adjust priorities
5. **Load Test Early** - Don't wait until the end

---

## Questions & Decisions

### Confirmed ✅
- Synchronized test start (all teams at global time)
- Database queue (Redis optional)
- All-or-nothing grading (100% test pass = full marks)

### Pending ⏳
- None (all critical decisions made)

---

## References

- Piston API Docs: https://github.com/engineer-man/piston
- FastAPI Docs: https://fastapi.tiangolo.com/
- Next.js Docs: https://nextjs.org/docs

---

**Maintainer:** Development Team
**Stakeholder:** Admin organizing 175-team coding test
