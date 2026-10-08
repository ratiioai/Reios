"""
Exam engine: attempt lifecycle, scoring, code execution and similarity checks.
"""
import difflib
import hashlib
import random
import re
import secrets
import sys
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.reios.models import (
    Attempt, AttemptStatus, CodeAnswer, Exam, ExamItem, ItemType, ProctorEvent,
    SetAssignment, User,
)
from app.reios.security import as_utc, utcnow

# code_compiler_tester.py lives in the backend root
BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
from code_compiler_tester import CodeCompilerTester, compare_outputs  # noqa: E402

MAX_CODE_LENGTH = 50_000
MAX_TESTS_PER_RUN = 50


# ── Exam visibility ───────────────────────────────────────────────────────

def _csv_set(value: Optional[str]) -> set:
    return {v.strip().lower() for v in (value or "").split(",") if v.strip()}


def student_is_eligible(exam: Exam, student: User) -> bool:
    return exam.is_published and matches_audience(exam, student)


def matches_audience(exam: Exam, student: User) -> bool:
    """Branch/batch/section filters only, so sets can be assigned before the exam is published."""
    if exam.college_id != student.college_id:
        return False
    branches, batches, sections = _csv_set(exam.branch_filter), _csv_set(exam.batch_filter), _csv_set(exam.section_filter)
    if branches and (student.branch or "").strip().lower() not in branches:
        return False
    if batches and str(student.batch_year or "").lower() not in batches:
        return False
    if sections and (student.section or "").strip().lower() not in sections:
        return False
    return True


def exam_window(exam: Exam) -> str:
    now = utcnow()
    # end_at is always a hard cap, even if the organizer forced the exam live or paused
    if exam.control_state == "ended" or now >= as_utc(exam.end_at):
        return "ended"
    if exam.control_state == "paused":
        return "paused"
    if exam.control_state == "live":
        return "live"
    if now < as_utc(exam.start_at):
        return "upcoming"
    return "live"


def paper_items(exam: Exam, set_id: Optional[int]) -> List[ExamItem]:
    """Common items plus the given set's items. With no set, the first set stands in (for previews/counts)."""
    if set_id is None and exam.sets:
        set_id = exam.sets[0].id
    return [i for i in exam.items if i.set_id is None or i.set_id == set_id]


def exam_max_score(exam: Exam, set_id: Optional[int] = None) -> float:
    return round(sum(item.effective_marks for item in paper_items(exam, set_id)), 2)


def assigned_set_id(db: Session, exam: Exam, student: User, create: bool = False) -> Optional[int]:
    """
    The set this student sits. Admins assign sets up front; anyone left unassigned gets the
    least-used set when they start, so sets repeat evenly (10 sets, 30 students -> 3 each).
    """
    if not exam.sets:
        return None
    row = db.query(SetAssignment).filter(SetAssignment.exam_id == exam.id,
                                         SetAssignment.student_id == student.id).first()
    valid = {s.id for s in exam.sets}
    if row and row.set_id in valid:
        return row.set_id
    if not create:
        return None
    usage = dict(db.query(SetAssignment.set_id, func.count(SetAssignment.id))
                 .filter(SetAssignment.exam_id == exam.id).group_by(SetAssignment.set_id).all())
    chosen = min(exam.sets, key=lambda s: (usage.get(s.id, 0), s.id)).id
    if row:
        row.set_id = chosen
    else:
        db.add(SetAssignment(exam_id=exam.id, student_id=student.id, set_id=chosen))
    db.flush()
    return chosen


# ── Attempt lifecycle ─────────────────────────────────────────────────────

def create_attempt(db: Session, exam: Exam, student: User, ip: Optional[str], ua: Optional[str]) -> Attempt:
    set_id = assigned_set_id(db, exam, student, create=True)
    items = paper_items(exam, set_id)
    if not items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This exam has no questions yet")

    rng = random.Random(secrets.randbits(64))
    # Keep sections together, shuffle within each section
    sections: Dict[str, List[ExamItem]] = {}
    for item in items:
        sections.setdefault(item.section, []).append(item)
    order: List[int] = []
    for section_items in sections.values():
        if exam.shuffle_questions:
            rng.shuffle(section_items)
        order.extend(i.id for i in section_items)

    option_order = {}
    for item in items:
        if item.item_type == ItemType.MCQ and item.mcq:
            perm = list(range(len(item.mcq.options)))
            if exam.shuffle_options:
                rng.shuffle(perm)
            option_order[str(item.id)] = perm

    now = utcnow()
    deadline = min(now + timedelta(minutes=exam.duration_minutes), as_utc(exam.end_at))
    attempt = Attempt(
        exam_id=exam.id, student_id=student.id, status=AttemptStatus.IN_PROGRESS, set_id=set_id,
        started_at=now, deadline_at=deadline, item_order=order, option_order=option_order,
        session_nonce=secrets.token_urlsafe(24), max_score=round(sum(i.effective_marks for i in items), 2),
        last_heartbeat_at=now, ip_address=ip, user_agent=(ua or "")[:500],
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


# The exam page locks at 0:00 and submits, but on a busy server answers clicked in the last seconds can
# still be in transit. Accept them for this long after the deadline before auto-submitting.
DEADLINE_GRACE = timedelta(seconds=90)


def is_expired(attempt: Attempt) -> bool:
    return utcnow() >= as_utc(attempt.deadline_at) + DEADLINE_GRACE


def finalize_if_expired(db: Session, attempt: Attempt) -> bool:
    """Auto-submit an in-progress attempt whose time is up. Returns True if it was finalized."""
    if attempt.status == AttemptStatus.IN_PROGRESS and is_expired(attempt):
        finalize_attempt(db, attempt, AttemptStatus.AUTO_SUBMITTED, "time_up")
        return True
    return False


def require_active_attempt(db: Session, attempt: Attempt, nonce: Optional[str]) -> None:
    """Guard for every student write during an exam."""
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise HTTPException(status.HTTP_409_CONFLICT, "This exam has already been submitted")
    if finalize_if_expired(db, attempt):
        raise HTTPException(status.HTTP_409_CONFLICT, "Time is up. Your exam was submitted automatically")
    if attempt.exam.control_state == "paused":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This exam is paused by the organizers. Please wait — your progress is safe")
    if not nonce or not secrets.compare_digest(nonce, attempt.session_nonce):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This exam is open in another window or device. Only one session is allowed")


def record_event(db: Session, attempt: Attempt, event_type: str, details: Optional[str] = None,
                 counted: bool = False) -> ProctorEvent:
    event = ProctorEvent(attempt_id=attempt.id, event_type=event_type[:64],
                         details=(details or "")[:500] or None, counted=counted)
    db.add(event)
    return event


def resume_from_pause(db: Session, exam: Exam) -> None:
    """Push every in-progress attempt's deadline out by however long the exam was paused, so
    nobody loses exam time while the organizers had it on hold."""
    if not exam.paused_at:
        return
    elapsed = utcnow() - as_utc(exam.paused_at)
    if elapsed.total_seconds() > 0:
        attempts = db.query(Attempt).filter(Attempt.exam_id == exam.id,
                                            Attempt.status == AttemptStatus.IN_PROGRESS).all()
        for attempt in attempts:
            attempt.deadline_at = as_utc(attempt.deadline_at) + elapsed
    exam.paused_at = None


def force_submit_in_progress(db: Session, exam_id: int, reason: str) -> int:
    """End every attempt still writing this exam right now (admin pressed End, or a forced delete). Returns how many."""
    attempts = db.query(Attempt).filter(Attempt.exam_id == exam_id, Attempt.status == AttemptStatus.IN_PROGRESS).all()
    for attempt in attempts:
        finalize_attempt(db, attempt, AttemptStatus.AUTO_SUBMITTED, reason)
    return len(attempts)


def finalize_attempt(db: Session, attempt: Attempt, final_status: AttemptStatus, reason: str) -> Attempt:
    if attempt.status != AttemptStatus.IN_PROGRESS:
        return attempt
    # Grade any code that was written but never explicitly submitted (or changed since)
    items = {i.id: i for i in attempt.exam.items}
    for answer in attempt.code_answers:
        item = items.get(answer.item_id)
        if item and answer.code.strip() and answer.graded_code_hash != code_hash(answer.code, answer.language):
            grade_code_answer(answer, item)

    mcq_score = sum(a.marks_awarded for a in attempt.mcq_answers)
    coding_score = sum(a.marks_awarded for a in attempt.code_answers)
    attempt.mcq_score = round(mcq_score, 2)
    attempt.coding_score = round(coding_score, 2)
    attempt.total_score = round(max(mcq_score + coding_score, 0.0), 2)
    attempt.status = final_status
    attempt.submit_reason = reason
    now = utcnow()
    attempt.submitted_at = min(now, as_utc(attempt.deadline_at)) if reason == "time_up" else now
    record_event(db, attempt, "submitted", reason)
    db.commit()
    return attempt


# ── Ranking ───────────────────────────────────────────────────────────────

def percentage(attempt: Attempt) -> float:
    return round(attempt.total_score / attempt.max_score * 100, 1) if attempt.max_score else 0.0


def time_taken_seconds(attempt: Attempt) -> Optional[int]:
    if not attempt.submitted_at:
        return None
    return int((as_utc(attempt.submitted_at) - as_utc(attempt.started_at)).total_seconds())


def rank_attempts(attempts: List[Attempt]) -> List[Attempt]:
    """Finished attempts, best first. Percentage, not raw score, so different sets compare fairly."""
    finished = [a for a in attempts if a.status != AttemptStatus.IN_PROGRESS]
    return sorted(finished, key=lambda a: (-percentage(a), time_taken_seconds(a) or 0, a.id))


# ── MCQ scoring ───────────────────────────────────────────────────────────

def score_mcq(item: ExamItem, selected: List[int], negative_marking: bool) -> Tuple[Optional[bool], float]:
    if not selected:
        return None, 0.0
    correct = set(item.mcq.correct_options)
    if set(selected) == correct:
        return True, float(item.effective_marks)
    return False, -float(item.mcq.negative_marks) if negative_marking else 0.0


# ── Code execution ────────────────────────────────────────────────────────

def code_hash(code: str, language: str) -> str:
    return hashlib.sha256(f"{language}\n{code}".encode("utf-8")).hexdigest()


def run_tests(code: str, language: str, tests: List[dict], time_limit: int) -> List[dict]:
    """Compile once and run against each test. Returns per-test results."""
    tests = tests[:MAX_TESTS_PER_RUN]
    if not tests:
        return []
    raw = CodeCompilerTester.execute_multi_test_cases(
        code=code, language=language,
        test_inputs=[t.get("input", "") for t in tests],
        timeout_seconds=time_limit,
    )
    results = []
    for test, res in zip(tests, raw):
        stdout = res.get("stdout") or ""
        passed = bool(res.get("success")) and compare_outputs(stdout, test.get("output", ""))
        results.append({
            "passed": passed,
            "stdout": stdout,
            "stderr": res.get("stderr") or res.get("error") or "",
            "time_ms": res.get("execution_time_ms", 0),
        })
    return results


def run_custom(code: str, language: str, stdin: str, time_limit: int) -> dict:
    res = CodeCompilerTester.execute_code(
        code=code, language=language,
        stdin=stdin, timeout_seconds=time_limit,
    )
    return {
        "stdout": res.get("stdout") or "",
        "stderr": res.get("stderr") or res.get("error") or "",
        "time_ms": res.get("execution_time_ms", 0),
        "success": bool(res.get("success")),
    }


def grade_code_answer(answer: CodeAnswer, item: ExamItem) -> CodeAnswer:
    problem = item.problem
    tests = problem.hidden_tests or problem.sample_tests or []
    results = run_tests(answer.code, answer.language, tests, problem.time_limit_seconds)
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    answer.passed_tests = passed
    answer.total_tests = total
    answer.marks_awarded = round(item.effective_marks * passed / total, 2) if total else 0.0
    answer.graded_code_hash = code_hash(answer.code, answer.language)
    answer.graded_at = utcnow()
    return answer


# ── Plagiarism / similarity ───────────────────────────────────────────────

_COMMENT_RE = re.compile(r"(#[^\n]*|//[^\n]*|/\*.*?\*/)", re.S)
_WS_RE = re.compile(r"\s+")


def normalize_code(code: str) -> str:
    return _WS_RE.sub(" ", _COMMENT_RE.sub("", code or "")).strip().lower()


def similarity_report(db: Session, exam: Exam, threshold: float = 0.85) -> List[dict]:
    """Pairs of students whose code for the same problem is suspiciously similar."""
    rows = (
        db.query(CodeAnswer, Attempt, User)
        .join(Attempt, CodeAnswer.attempt_id == Attempt.id)
        .join(User, Attempt.student_id == User.id)
        .filter(Attempt.exam_id == exam.id)
        .all()
    )
    by_item: Dict[int, list] = {}
    for answer, attempt, student in rows:
        norm = normalize_code(answer.code)
        if len(norm) >= 40:  # ignore near-empty answers
            by_item.setdefault(answer.item_id, []).append((norm, student, answer))

    items = {i.id: i for i in exam.items}
    flagged = []
    for item_id, entries in by_item.items():
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                a, b = entries[i], entries[j]
                matcher = difflib.SequenceMatcher(None, a[0], b[0], autojunk=False)
                if matcher.real_quick_ratio() < threshold or matcher.quick_ratio() < threshold:
                    continue
                ratio = matcher.ratio()
                if ratio >= threshold:
                    problem = items[item_id].problem if item_id in items else None
                    flagged.append({
                        "item_id": item_id,
                        "problem": problem.title if problem else f"Item {item_id}",
                        "similarity": round(ratio * 100, 1),
                        "student_a": {"id": a[1].id, "name": a[1].name, "roll_no": a[1].roll_no},
                        "student_b": {"id": b[1].id, "name": b[1].name, "roll_no": b[1].roll_no},
                    })
    flagged.sort(key=lambda f: -f["similarity"])
    return flagged
