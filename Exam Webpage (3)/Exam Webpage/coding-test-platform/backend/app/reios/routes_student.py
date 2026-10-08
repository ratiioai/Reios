"""
Student endpoints: dashboard, taking an exam, results and history.

Every write during an exam must send the X-Exam-Session header received from /start.
Starting the exam again from another tab or device issues a new session and the old one stops working.
"""
import re
import secrets
import time
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.reios import engine
from app.reios.models import (
    LANGUAGES, Announcement, Attempt, AttemptStatus, CodeAnswer, Exam, ExamItem, ItemType, MCQAnswer, User,
)
from app.reios.features import certificate_pdf, has_feature, require_feature
from app.reios.security import as_utc, needs_password_change, require_student, utcnow

router = APIRouter(prefix="/api/reios/student", tags=["Reios Student"])

RUN_COOLDOWN_SECONDS = 3
VIOLATION_DEBOUNCE_SECONDS = 2
# Events that count toward the exam's max_violations; everything else is only logged
COUNTED_VIOLATIONS = {"fullscreen_exit", "tab_switch", "window_blur", "devtools_open", "paste_attempt",
                      "multiple_displays", "screen_share_stopped"}
LOGGED_EVENTS = COUNTED_VIOLATIONS | {"copy_attempt", "right_click", "print_screen", "keyboard_shortcut",
                                      "window_resize", "network_offline", "network_online"}

_last_run: Dict[Tuple[int, int], float] = {}


class MCQAnswerIn(BaseModel):
    selected: List[int] = Field(default_factory=list, max_length=8)
    marked_for_review: bool = False


class CodeIn(BaseModel):
    language: str
    code: str = Field("", max_length=engine.MAX_CODE_LENGTH)


class RunIn(CodeIn):
    custom_input: Optional[str] = Field(None, max_length=100_000)


class ViolationIn(BaseModel):
    type: str = Field(..., max_length=64)
    details: Optional[str] = Field(None, max_length=500)


# ── Helpers ───────────────────────────────────────────────────────────────

def get_own_attempt(db: Session, student: User, attempt_id: int) -> Attempt:
    attempt = db.get(Attempt, attempt_id)
    if not attempt or attempt.student_id != student.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
    return attempt


def get_item(db: Session, attempt: Attempt, item_id: int, item_type: ItemType) -> ExamItem:
    """Only questions in this student's own paper (their set) can be answered."""
    item = db.get(ExamItem, item_id) if item_id in (attempt.item_order or []) else None
    if not item or item.exam_id != attempt.exam_id or item.item_type != item_type:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found in this exam")
    return item


def check_language(exam: Exam, language: str) -> None:
    allowed = exam.allowed_languages or LANGUAGES
    if language not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Language not allowed. Use one of: {', '.join(allowed)}")


def seconds_left(attempt: Attempt) -> int:
    return max(0, int((as_utc(attempt.deadline_at) - utcnow()).total_seconds()))


def build_paper(attempt: Attempt) -> dict:
    exam = attempt.exam
    items = {i.id: i for i in exam.items}
    mcq_answers = {m.item_id: m for m in attempt.mcq_answers}
    code_answers = {c.item_id: c for c in attempt.code_answers}
    option_order = attempt.option_order or {}
    out, sections = [], []
    for number, item_id in enumerate(attempt.item_order, start=1):
        item = items.get(item_id)
        if not item:
            continue
        if item.section not in sections:
            sections.append(item.section)
        entry = {"item_id": item.id, "number": number, "type": item.item_type.value, "section": item.section,
                 "marks": item.effective_marks}
        if item.item_type == ItemType.MCQ:
            q = item.mcq
            perm = option_order.get(str(item.id)) or list(range(len(q.options)))
            ans = mcq_answers.get(item.id)
            entry.update({
                "question_text": q.question_text, "is_multi": q.is_multi,
                "negative_marks": q.negative_marks if exam.negative_marking else 0,
                "options": [{"id": idx, "text": q.options[idx]} for idx in perm if idx < len(q.options)],
                "answer": {"selected": ans.selected if ans else [],
                           "marked_for_review": ans.marked_for_review if ans else False},
            })
        else:
            p = item.problem
            ans = code_answers.get(item.id)
            entry.update({
                "title": p.title, "difficulty": p.difficulty, "statement": p.statement,
                "input_format": p.input_format, "output_format": p.output_format, "constraints": p.constraints,
                "sample_tests": p.sample_tests or [], "starter_code": p.starter_code or {},
                "time_limit_seconds": p.time_limit_seconds, "hidden_test_count": len(p.hidden_tests or []),
                "answer": {"language": ans.language, "code": ans.code, "passed_tests": ans.passed_tests,
                           "total_tests": ans.total_tests,
                           "graded": ans.graded_code_hash == engine.code_hash(ans.code, ans.language)}
                if ans else None,
            })
        out.append(entry)
    return {
        "attempt_id": attempt.id,
        "status": attempt.status.value,
        "exam": {
            "id": exam.id, "title": exam.title, "instructions": exam.instructions,
            "require_fullscreen": exam.require_fullscreen, "block_copy_paste": exam.block_copy_paste,
            "max_violations": exam.max_violations, "negative_marking": exam.negative_marking,
            "allowed_languages": exam.allowed_languages or LANGUAGES, "duration_minutes": exam.duration_minutes,
            "exam_type": exam.exam_type,
        },
        "deadline_at": as_utc(attempt.deadline_at),
        "seconds_left": seconds_left(attempt),
        "violations": attempt.violation_count,
        "sections": sections,
        "items": out,
        "max_score": attempt.max_score,
    }


def can_view_result(attempt: Attempt) -> bool:
    return attempt.status != AttemptStatus.IN_PROGRESS and attempt.exam.show_results


# ── Dashboard ─────────────────────────────────────────────────────────────

@router.get("/dashboard")
def dashboard(student: User = Depends(require_student), db: Session = Depends(get_db)):
    exams = db.query(Exam).filter(Exam.college_id == student.college_id, Exam.is_published.is_(True)) \
        .order_by(Exam.start_at).all()
    attempts = {a.exam_id: a for a in db.query(Attempt).filter(Attempt.student_id == student.id).all()}
    for attempt in attempts.values():
        engine.finalize_if_expired(db, attempt)

    rows = []
    for exam in exams:
        attempt = attempts.get(exam.id)
        if not engine.student_is_eligible(exam, student) and not attempt:
            continue
        window = engine.exam_window(exam)
        set_id = attempt.set_id if attempt else engine.assigned_set_id(db, exam, student)
        paper = engine.paper_items(exam, set_id)
        if attempt and attempt.status == AttemptStatus.IN_PROGRESS:
            state = "in_progress"
        elif attempt:
            state = "completed"
        elif window == "ended":
            state = "missed"
        else:
            state = window  # upcoming | live
        rows.append({
            "id": exam.id, "title": exam.title, "description": exam.description,
            "start_at": as_utc(exam.start_at), "end_at": as_utc(exam.end_at),
            "duration_minutes": exam.duration_minutes, "question_count": len(paper),
            "max_score": attempt.max_score if attempt else engine.exam_max_score(exam, set_id), "state": state,
            "sections": sorted({i.section for i in paper}), "exam_type": exam.exam_type,
            "leaderboard_available": bool(attempt and attempt.status != AttemptStatus.IN_PROGRESS
                                          and exam.show_leaderboard),
            "attempt_id": attempt.id if attempt else None,
            "score": attempt.total_score if attempt and can_view_result(attempt) else None,
            "result_available": bool(attempt and can_view_result(attempt)),
        })

    finished = [a for a in attempts.values() if a.status != AttemptStatus.IN_PROGRESS and a.max_score]
    announcements = db.query(Announcement).filter(
        or_(Announcement.college_id == student.college_id, Announcement.college_id.is_(None))
    ).order_by(Announcement.created_at.desc()).limit(10).all()
    return {
        "exams": rows,
        "stats": {
            "completed": len(finished),
            "average_percentage": round(sum(a.total_score / a.max_score * 100 for a in finished) / len(finished), 1)
            if finished else None,
            "upcoming": sum(1 for r in rows if r["state"] in ("upcoming", "live", "paused")),
        },
        "announcements": [{"id": a.id, "title": a.title, "body": a.body, "created_at": a.created_at}
                          for a in announcements],
        "server_time": utcnow(),
    }


# ── Taking the exam ───────────────────────────────────────────────────────

@router.get("/exams/{exam_id}")
def exam_info(exam_id: int, student: User = Depends(require_student), db: Session = Depends(get_db)):
    """Pre-start screen: rules and instructions, without any questions."""
    exam = db.get(Exam, exam_id)
    if not exam or not engine.student_is_eligible(exam, student):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exam not found")
    attempt = db.query(Attempt).filter(Attempt.exam_id == exam.id, Attempt.student_id == student.id).first()
    if attempt:
        engine.finalize_if_expired(db, attempt)
    set_id = attempt.set_id if attempt else engine.assigned_set_id(db, exam, student)
    paper = engine.paper_items(exam, set_id)
    sections: Dict[str, dict] = {}
    for item in paper:
        sec = sections.setdefault(item.section, {"section": item.section, "questions": 0, "marks": 0.0})
        sec["questions"] += 1
        sec["marks"] = round(sec["marks"] + item.effective_marks, 2)
    return {
        "id": exam.id, "title": exam.title, "description": exam.description, "instructions": exam.instructions,
        "start_at": as_utc(exam.start_at), "end_at": as_utc(exam.end_at), "duration_minutes": exam.duration_minutes,
        "window": engine.exam_window(exam), "max_score": round(sum(i.effective_marks for i in paper), 2),
        "exam_type": exam.exam_type, "has_coding": any(i.item_type == ItemType.CODING for i in paper),
        "sections": list(sections.values()), "negative_marking": exam.negative_marking,
        "require_fullscreen": exam.require_fullscreen, "block_copy_paste": exam.block_copy_paste,
        "max_violations": exam.max_violations, "allowed_languages": exam.allowed_languages or LANGUAGES,
        "attempt": {"id": attempt.id, "status": attempt.status.value, "seconds_left": seconds_left(attempt)}
        if attempt else None,
        "must_change_password": needs_password_change(student),
        "leaderboard_enabled": exam.show_leaderboard,
    }


@router.post("/exams/{exam_id}/start")
def start_exam(exam_id: int, request: Request, student: User = Depends(require_student),
                     db: Session = Depends(get_db)):
    exam = db.get(Exam, exam_id)
    if not exam or not engine.student_is_eligible(exam, student):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exam not found")
    if needs_password_change(student):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Please change your password before starting an exam")

    attempt = db.query(Attempt).filter(Attempt.exam_id == exam.id, Attempt.student_id == student.id).first()
    ip = request.client.host if request.client else None
    if attempt:
        engine.finalize_if_expired(db, attempt)
        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise HTTPException(status.HTTP_409_CONFLICT, "You have already submitted this exam")
        # Resume: take over the session (any other open tab stops working)
        attempt.session_nonce = secrets.token_urlsafe(24)
        engine.record_event(db, attempt, "session_resumed", f"IP {ip}")
        attempt.last_heartbeat_at = utcnow()
        db.commit()
    else:
        window = engine.exam_window(exam)
        if window == "upcoming":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "This exam has not started yet")
        if window == "ended":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "This exam has ended")
        attempt = engine.create_attempt(db, exam, student, ip, request.headers.get("user-agent"))
        engine.record_event(db, attempt, "started", f"IP {ip}")
        db.commit()
    return {**build_paper(attempt), "session": attempt.session_nonce}


@router.get("/attempts/{attempt_id}/paper")
def get_paper(attempt_id: int, x_exam_session: Optional[str] = Header(None),
                    student: User = Depends(require_student), db: Session = Depends(get_db)):
    attempt = get_own_attempt(db, student, attempt_id)
    engine.require_active_attempt(db, attempt, x_exam_session)
    return build_paper(attempt)


@router.put("/attempts/{attempt_id}/mcq/{item_id}")
def answer_mcq(attempt_id: int, item_id: int, body: MCQAnswerIn, x_exam_session: Optional[str] = Header(None),
                     student: User = Depends(require_student), db: Session = Depends(get_db)):
    attempt = get_own_attempt(db, student, attempt_id)
    engine.require_active_attempt(db, attempt, x_exam_session)
    item = get_item(db, attempt, item_id, ItemType.MCQ)
    selected = sorted(set(body.selected))
    if any(i < 0 or i >= len(item.mcq.options) for i in selected):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid option")
    if not item.mcq.is_multi and len(selected) > 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only one option can be selected")
    answer = db.query(MCQAnswer).filter(MCQAnswer.attempt_id == attempt.id, MCQAnswer.item_id == item.id).first()
    if not answer:
        answer = MCQAnswer(attempt_id=attempt.id, item_id=item.id, marks_awarded=0.0)
        db.add(answer)
    answer.selected = selected
    answer.marked_for_review = body.marked_for_review
    answer.is_correct, answer.marks_awarded = engine.score_mcq(item, selected, attempt.exam.negative_marking)
    db.commit()
    return {"saved": True, "selected": selected, "marked_for_review": answer.marked_for_review}


def _upsert_code(db: Session, attempt: Attempt, item: ExamItem, body: CodeIn) -> CodeAnswer:
    check_language(attempt.exam, body.language)
    answer = db.query(CodeAnswer).filter(CodeAnswer.attempt_id == attempt.id, CodeAnswer.item_id == item.id).first()
    if not answer:
        answer = CodeAnswer(attempt_id=attempt.id, item_id=item.id, language=body.language, code=body.code,
                            passed_tests=0, total_tests=0, marks_awarded=0.0, run_count=0)
        db.add(answer)
    answer.language = body.language
    answer.code = body.code
    if answer.graded_code_hash and answer.graded_code_hash != engine.code_hash(body.code, body.language):
        # Code changed since last grading: marks no longer apply until it is submitted again
        answer.marks_awarded = 0.0
        answer.passed_tests = 0
    return answer


@router.put("/attempts/{attempt_id}/code/{item_id}")
def save_code(attempt_id: int, item_id: int, body: CodeIn, x_exam_session: Optional[str] = Header(None),
                    student: User = Depends(require_student), db: Session = Depends(get_db)):
    attempt = get_own_attempt(db, student, attempt_id)
    engine.require_active_attempt(db, attempt, x_exam_session)
    item = get_item(db, attempt, item_id, ItemType.CODING)
    _upsert_code(db, attempt, item, body)
    db.commit()
    return {"saved": True}


def _check_cooldown(attempt_id: int, item_id: int) -> None:
    key = (attempt_id, item_id)
    now = time.monotonic()
    last = _last_run.get(key)
    if last and now - last < RUN_COOLDOWN_SECONDS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Please wait a few seconds before running again")
    _last_run[key] = now
    if len(_last_run) > 50_000:
        _last_run.clear()


@router.post("/attempts/{attempt_id}/code/{item_id}/run")
def run_code(attempt_id: int, item_id: int, body: RunIn, x_exam_session: Optional[str] = Header(None),
                   student: User = Depends(require_student), db: Session = Depends(get_db)):
    """Run against the sample tests, or against custom input when given. Never affects the score."""
    attempt = get_own_attempt(db, student, attempt_id)
    engine.require_active_attempt(db, attempt, x_exam_session)
    item = get_item(db, attempt, item_id, ItemType.CODING)
    if not body.code.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Write some code first")
    _check_cooldown(attempt.id, item.id)
    answer = _upsert_code(db, attempt, item, body)
    answer.run_count += 1
    db.commit()

    problem = item.problem
    if body.custom_input is not None:
        result = engine.run_custom(body.code, body.language, body.custom_input, problem.time_limit_seconds)
        return {"mode": "custom", **result}
    samples = problem.sample_tests or []
    results = engine.run_tests(body.code, body.language, samples, problem.time_limit_seconds)
    return {
        "mode": "samples",
        "passed": sum(r["passed"] for r in results), "total": len(results),
        "results": [{"input": t.get("input", ""), "expected": t.get("output", ""), "actual": r["stdout"],
                     "stderr": r["stderr"][:4000], "passed": r["passed"], "time_ms": r["time_ms"]}
                    for t, r in zip(samples, results)],
    }


@router.post("/attempts/{attempt_id}/code/{item_id}/submit")
def submit_code(attempt_id: int, item_id: int, body: CodeIn, x_exam_session: Optional[str] = Header(None),
                      student: User = Depends(require_student), db: Session = Depends(get_db)):
    """Grade against the hidden tests. Only pass counts are revealed, never the test data."""
    attempt = get_own_attempt(db, student, attempt_id)
    engine.require_active_attempt(db, attempt, x_exam_session)
    item = get_item(db, attempt, item_id, ItemType.CODING)
    if not body.code.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Write some code first")
    _check_cooldown(attempt.id, item.id)
    answer = _upsert_code(db, attempt, item, body)
    engine.grade_code_answer(answer, item)
    db.commit()
    return {"passed_tests": answer.passed_tests, "total_tests": answer.total_tests,
            "all_passed": answer.total_tests > 0 and answer.passed_tests == answer.total_tests}


@router.post("/attempts/{attempt_id}/violation")
def report_violation(attempt_id: int, body: ViolationIn, x_exam_session: Optional[str] = Header(None),
                           student: User = Depends(require_student), db: Session = Depends(get_db)):
    attempt = get_own_attempt(db, student, attempt_id)
    engine.require_active_attempt(db, attempt, x_exam_session)
    event_type = body.type if body.type in LOGGED_EVENTS else "other"
    counted = event_type in COUNTED_VIOLATIONS
    if counted:
        # A single alt-tab fires blur + visibilitychange together; count it once
        last = next((e for e in reversed(attempt.events) if e.counted), None)
        if last and (utcnow() - as_utc(last.created_at)).total_seconds() < VIOLATION_DEBOUNCE_SECONDS:
            counted = False
    engine.record_event(db, attempt, event_type, body.details, counted=counted)
    if counted:
        attempt.violation_count += 1
    db.commit()

    auto_submitted = False
    if attempt.violation_count >= attempt.exam.max_violations:
        engine.finalize_attempt(db, attempt, AttemptStatus.AUTO_SUBMITTED, "max_violations")
        auto_submitted = True
    return {"violations": attempt.violation_count, "max_violations": attempt.exam.max_violations,
            "counted": counted, "auto_submitted": auto_submitted}


@router.post("/attempts/{attempt_id}/heartbeat")
def heartbeat(attempt_id: int, x_exam_session: Optional[str] = Header(None),
                    student: User = Depends(require_student), db: Session = Depends(get_db)):
    """Called every ~20s. Lets the client pick up time extensions, force-submits and session takeovers."""
    attempt = get_own_attempt(db, student, attempt_id)
    engine.finalize_if_expired(db, attempt)
    if attempt.status != AttemptStatus.IN_PROGRESS:
        return {"status": attempt.status.value, "seconds_left": 0, "violations": attempt.violation_count,
                "session_valid": True}
    session_valid = bool(x_exam_session) and x_exam_session == attempt.session_nonce
    if session_valid:
        attempt.last_heartbeat_at = utcnow()
        db.commit()
    return {"status": attempt.status.value, "seconds_left": seconds_left(attempt),
            "deadline_at": as_utc(attempt.deadline_at), "violations": attempt.violation_count,
            "session_valid": session_valid}


@router.post("/attempts/{attempt_id}/submit")
def submit_exam(attempt_id: int, x_exam_session: Optional[str] = Header(None),
                      student: User = Depends(require_student), db: Session = Depends(get_db)):
    attempt = get_own_attempt(db, student, attempt_id)
    engine.require_active_attempt(db, attempt, x_exam_session)
    engine.finalize_attempt(db, attempt, AttemptStatus.SUBMITTED, "student_submitted")
    return {"status": attempt.status.value, "result_available": can_view_result(attempt),
            "leaderboard_available": attempt.exam.show_leaderboard}


# ── Results ───────────────────────────────────────────────────────────────

@router.get("/attempts/{attempt_id}/result")
def get_result(attempt_id: int, student: User = Depends(require_student), db: Session = Depends(get_db)):
    attempt = get_own_attempt(db, student, attempt_id)
    engine.finalize_if_expired(db, attempt)
    if not can_view_result(attempt):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Results for this exam are not published")
    exam = attempt.exam
    items = {i.id: i for i in exam.items}
    mcq_answers = {m.item_id: m for m in attempt.mcq_answers}
    code_answers = {c.item_id: c for c in attempt.code_answers}

    sections: Dict[str, dict] = {}
    review = []
    for item_id in attempt.item_order:
        item = items.get(item_id)
        if not item:
            continue
        sec = sections.setdefault(item.section, {"section": item.section, "score": 0.0, "max": 0.0,
                                                 "correct": 0, "wrong": 0, "unanswered": 0})
        sec["max"] += item.effective_marks
        if item.item_type == ItemType.MCQ:
            ans = mcq_answers.get(item.id)
            sec["score"] += ans.marks_awarded if ans else 0
            if not ans or not ans.selected:
                sec["unanswered"] += 1
            elif ans.is_correct:
                sec["correct"] += 1
            else:
                sec["wrong"] += 1
            if exam.show_answers:
                review.append({"type": "mcq", "section": item.section, "question_text": item.mcq.question_text,
                               "options": item.mcq.options, "selected": ans.selected if ans else [],
                               "correct_options": item.mcq.correct_options, "explanation": item.mcq.explanation,
                               "marks_awarded": ans.marks_awarded if ans else 0, "marks": item.effective_marks})
        else:
            ans = code_answers.get(item.id)
            sec["score"] += ans.marks_awarded if ans else 0
            if not ans or not ans.code.strip():
                sec["unanswered"] += 1
            elif ans.total_tests and ans.passed_tests == ans.total_tests:
                sec["correct"] += 1
            else:
                sec["wrong"] += 1
            review.append({"type": "coding", "section": item.section, "title": item.problem.title,
                           "language": ans.language if ans else None, "code": ans.code if ans else "",
                           "passed_tests": ans.passed_tests if ans else 0,
                           "total_tests": ans.total_tests if ans else len(item.problem.hidden_tests or []),
                           "marks_awarded": ans.marks_awarded if ans else 0, "marks": item.effective_marks})

    for sec in sections.values():
        sec["score"] = round(sec["score"], 2)
        sec["max"] = round(sec["max"], 2)

    finished = engine.rank_attempts(db.query(Attempt).filter(Attempt.exam_id == exam.id).all())
    rank = next((i + 1 for i, a in enumerate(finished) if a.id == attempt.id), len(finished))
    pct = round(attempt.total_score / attempt.max_score * 100, 1) if attempt.max_score else 0
    return {
        "attempt_id": attempt.id,
        "exam": {"id": exam.id, "title": exam.title, "pass_percentage": exam.pass_percentage},
        "status": attempt.status.value, "submit_reason": attempt.submit_reason,
        "started_at": as_utc(attempt.started_at), "submitted_at": as_utc(attempt.submitted_at),
        "total_score": attempt.total_score, "max_score": attempt.max_score, "percentage": pct,
        "passed": pct >= exam.pass_percentage, "rank": rank, "participants": len(finished),
        "violations": attempt.violation_count,
        "sections": list(sections.values()), "review": review, "answers_visible": exam.show_answers,
        "leaderboard_available": exam.show_leaderboard,
        "certificate_available": has_feature(exam.college, "certificates") and pct >= exam.pass_percentage,
    }


@router.get("/attempts/{attempt_id}/certificate")
def download_certificate(attempt_id: int, student: User = Depends(require_student), db: Session = Depends(get_db)):
    attempt = get_own_attempt(db, student, attempt_id)
    if not can_view_result(attempt):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Results for this exam are not published")
    require_feature(attempt.exam.college, "certificates")
    pct = engine.percentage(attempt)
    if pct < attempt.exam.pass_percentage:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Certificates are given to students who pass")
    pdf = certificate_pdf(attempt, pct)
    filename = re.sub(r"\W+", "_", f"{attempt.exam.title}_{student.roll_no}") + "_certificate.pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/exams/{exam_id}/leaderboard")
def exam_leaderboard(exam_id: int, student: User = Depends(require_student), db: Session = Depends(get_db)):
    """Top 10 plus the student's own row; only after they've finished and if the college turned it on."""
    exam = db.get(Exam, exam_id)
    own = db.query(Attempt).filter(Attempt.exam_id == exam_id, Attempt.student_id == student.id).first()         if exam and exam.college_id == student.college_id else None
    if not own or own.status == AttemptStatus.IN_PROGRESS or not exam.show_leaderboard:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Leaderboard not available")
    ranked = engine.rank_attempts(db.query(Attempt).filter(Attempt.exam_id == exam.id).all())

    def row(rank: int, a: Attempt) -> dict:
        return {"rank": rank, "name": a.student.name, "branch": a.student.branch, "is_me": a.id == own.id,
                "percentage": engine.percentage(a), "total_score": a.total_score, "max_score": a.max_score,
                "time_taken_seconds": engine.time_taken_seconds(a)}

    rows = [row(i + 1, a) for i, a in enumerate(ranked[:10])]
    my_rank = next((i + 1 for i, a in enumerate(ranked) if a.id == own.id), None)
    return {"exam": {"id": exam.id, "title": exam.title}, "participants": len(ranked), "top": rows,
            "me": row(my_rank, own) if my_rank else None}
