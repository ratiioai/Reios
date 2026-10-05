"""
Question sets, document import, paper preview and leaderboards for college admins.

A set is one uploaded paper variant. Every student sits the exam's common questions plus exactly
one set; the admin decides who gets which (or lets Reios rotate them evenly).
"""
import csv
import io
import re
from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.reios import engine
from app.reios.models import (
    LANGUAGES, Attempt, AttemptStatus, Exam, ExamItem, ItemType, MCQQuestion, QuestionSet, Role, SetAssignment, User,
)
from app.reios.parsers import ParseError, file_kind, parse_question_file, student_rows, table_rows
from app.reios.routes_admin import MCQIn, get_exam, mcq_payload
from app.reios.security import bank_scope, require_admin, scoped_college_id

router = APIRouter(prefix="/api/reios/admin", tags=["Reios Sets & Leaderboard"])


# ── Document import (shared by the MCQ bank and sets) ─────────────────────

@router.post("/questions/parse")
def parse_questions(
    file: UploadFile = File(...), default_section: str = Form("General"),
    marks: float = Form(1.0), negative_marks: float = Form(0.0),
    _: User = Depends(require_admin),
):
    """Read a Word / PDF / CSV / Excel file into questions for review. Nothing is saved."""
    try:
        questions, warnings = parse_question_file(
            file.file.read(), file.filename or "", (default_section or "General").strip()[:64],
            max(marks, 0.25), max(negative_marks, 0.0))
    except ParseError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return {"filename": file.filename, "questions": questions, "warnings": warnings,
            "ready": sum(1 for q in questions if not q["problems"])}


class QuestionsIn(BaseModel):
    questions: List[MCQIn] = Field(..., min_length=1, max_length=1000)


@router.post("/mcqs/bulk", status_code=status.HTTP_201_CREATED)
def save_questions_to_bank(body: QuestionsIn, scope: Optional[int] = Depends(bank_scope),
                           user: User = Depends(require_admin), db: Session = Depends(get_db)):
    for q in body.questions:
        data = q.model_dump()
        data["is_multi"] = len(data["correct_options"]) > 1
        db.add(MCQQuestion(college_id=scope, created_by=user.id, **data))
    db.commit()
    return {"created": len(body.questions)}


# ── Sets ──────────────────────────────────────────────────────────────────

def _locked(db: Session, exam: Exam) -> bool:
    return db.query(Attempt).filter(Attempt.exam_id == exam.id).first() is not None


def _set_summary(db: Session, exam: Exam) -> List[dict]:
    assigned = defaultdict(int)
    for (set_id,) in db.query(SetAssignment.set_id).filter(SetAssignment.exam_id == exam.id).all():
        assigned[set_id] += 1
    out = []
    for qs in exam.sets:
        items = [i for i in exam.items if i.set_id == qs.id]
        out.append({"id": qs.id, "name": qs.name, "source_filename": qs.source_filename,
                    "question_count": len(items),
                    "marks": round(sum(i.effective_marks for i in items), 2),
                    "sections": sorted({i.section for i in items}), "assigned": assigned[qs.id]})
    return out


@router.get("/exams/{exam_id}/sets")
def list_sets(exam_id: int, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    return {"sets": _set_summary(db, exam), "locked": _locked(db, exam),
            "common_count": sum(1 for i in exam.items if i.set_id is None),
            "auto_assign": exam.auto_assign_sets}


class SetIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    source_filename: Optional[str] = Field(None, max_length=255)
    questions: List[MCQIn] = Field(..., min_length=1, max_length=500)


@router.post("/exams/{exam_id}/sets", status_code=status.HTTP_201_CREATED)
def create_set(exam_id: int, body: SetIn, college_id: int = Depends(scoped_college_id),
               user: User = Depends(require_admin), db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    if exam.exam_type == "coding":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sets hold MCQs; this is a coding-only exam")
    if _locked(db, exam):
        raise HTTPException(status.HTTP_409_CONFLICT, "Students have already started this exam")
    name = body.name.strip()
    if any(s.name.lower() == name.lower() for s in exam.sets):
        raise HTTPException(status.HTTP_409_CONFLICT, f'A set called "{name}" already exists')

    qset = QuestionSet(exam_id=exam.id, name=name, source_filename=body.source_filename)
    db.add(qset)
    db.flush()
    start = max((i.order for i in exam.items), default=-1) + 1
    for n, q in enumerate(body.questions):
        data = q.model_dump()
        data["is_multi"] = len(data["correct_options"]) > 1
        data["topic"] = data.get("topic") or name
        # Kept out of the browsable bank; it belongs to this exam's set
        data["is_active"] = False
        mcq = MCQQuestion(college_id=exam.college_id, created_by=user.id, **data)
        db.add(mcq)
        db.flush()
        db.add(ExamItem(exam_id=exam.id, item_type=ItemType.MCQ, mcq_id=mcq.id, section=q.section,
                        order=start + n, set_id=qset.id))
    db.commit()
    db.refresh(exam)
    if exam.auto_assign_sets:
        rotate(db, exam)
        db.commit()
    return {"sets": _set_summary(db, exam)}


@router.get("/exams/{exam_id}/sets/{set_id}")
def get_set(exam_id: int, set_id: int, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    qset = next((s for s in exam.sets if s.id == set_id), None)
    if not qset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Set not found")
    return {"id": qset.id, "name": qset.name, "source_filename": qset.source_filename,
            "questions": [mcq_payload(i.mcq) for i in exam.items if i.set_id == set_id and i.mcq]}


@router.delete("/exams/{exam_id}/sets/{set_id}")
def delete_set(exam_id: int, set_id: int, college_id: int = Depends(scoped_college_id),
               db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    qset = next((s for s in exam.sets if s.id == set_id), None)
    if not qset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Set not found")
    if _locked(db, exam):
        raise HTTPException(status.HTTP_409_CONFLICT, "Students have already started this exam")
    items = [i for i in exam.items if i.set_id == set_id]
    mcq_ids = [i.mcq_id for i in items if i.mcq_id]
    for item in items:
        exam.items.remove(item)
    db.query(SetAssignment).filter(SetAssignment.set_id == set_id).delete()
    db.flush()
    if mcq_ids:
        still_used = {m for (m,) in db.query(ExamItem.mcq_id).filter(ExamItem.mcq_id.in_(mcq_ids)).all()}
        db.query(MCQQuestion).filter(MCQQuestion.id.in_([m for m in mcq_ids if m not in still_used]),
                                     MCQQuestion.is_active.is_(False)).delete(synchronize_session=False)
    exam.sets.remove(qset)
    db.commit()
    db.refresh(exam)
    if exam.auto_assign_sets and exam.sets:
        rotate(db, exam)
        db.commit()
    return {"sets": _set_summary(db, exam)}


# ── Who sits which set ────────────────────────────────────────────────────

def _audience(db: Session, exam: Exam) -> List[User]:
    students = db.query(User).filter(User.college_id == exam.college_id, User.role == Role.STUDENT,
                                     User.is_active.is_(True)).order_by(User.roll_no).all()
    return [s for s in students if engine.matches_audience(exam, s)]


def _started_ids(db: Session, exam: Exam) -> set:
    return {sid for (sid,) in db.query(Attempt.student_id).filter(Attempt.exam_id == exam.id).all()}


def rotate(db: Session, exam: Exam) -> int:
    """
    Students in roll-number order get Set 1, Set 2, … Set N, then Set 1 again: student i gets set i mod N.
    Students who have already started keep the set they're sitting.
    """
    sets = list(exam.sets)
    if not sets:
        return 0
    started = _started_ids(db, exam)
    existing = {a.student_id: a for a in db.query(SetAssignment).filter(SetAssignment.exam_id == exam.id).all()}
    changed = 0
    for i, student in enumerate(_audience(db, exam)):
        if student.id in started:
            continue
        target = sets[i % len(sets)].id
        row = existing.get(student.id)
        if row is None:
            db.add(SetAssignment(exam_id=exam.id, student_id=student.id, set_id=target))
            changed += 1
        elif row.set_id != target:
            row.set_id = target
            changed += 1
    db.flush()
    return changed


class SetOptionsIn(BaseModel):
    auto_assign: bool


@router.put("/exams/{exam_id}/set-options")
def set_options(exam_id: int, body: SetOptionsIn, college_id: int = Depends(scoped_college_id),
                db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    exam.auto_assign_sets = body.auto_assign
    if body.auto_assign:
        rotate(db, exam)
    db.commit()
    return {"auto_assign": exam.auto_assign_sets, **list_assignments(exam_id, college_id, db)}


@router.get("/exams/{exam_id}/set-assignments")
def list_assignments(exam_id: int, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    current = {a.student_id: a.set_id for a in
               db.query(SetAssignment).filter(SetAssignment.exam_id == exam.id).all()}
    started = _started_ids(db, exam)
    students = _audience(db, exam)
    return {
        "sets": [{"id": s.id, "name": s.name} for s in exam.sets],
        "students": [{"student_id": s.id, "roll_no": s.roll_no, "name": s.name, "branch": s.branch,
                      "section": s.section, "set_id": current.get(s.id), "started": s.id in started}
                     for s in students],
        "unassigned": sum(1 for s in students if s.id not in current),
        "auto_assign": exam.auto_assign_sets,
    }


class AutoAssignIn(BaseModel):
    overwrite: bool = False


@router.post("/exams/{exam_id}/set-assignments/auto")
def auto_assign(exam_id: int, body: AutoAssignIn, college_id: int = Depends(scoped_college_id),
                db: Session = Depends(get_db)):
    """Rotate sets across students in roll-number order: Set 1, Set 2, … Set N, Set 1, …"""
    exam = get_exam(db, college_id, exam_id)
    if not exam.sets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Upload at least one set first")
    if body.overwrite:
        changed = rotate(db, exam)
        db.commit()
        return {"assigned": changed, **list_assignments(exam_id, college_id, db)}
    started = _started_ids(db, exam)
    existing = {a.student_id: a for a in db.query(SetAssignment).filter(SetAssignment.exam_id == exam.id).all()}
    usage = defaultdict(int)
    for a in existing.values():
        usage[a.set_id] += 1
    changed = 0
    for student in _audience(db, exam):
        if student.id in existing or student.id in started:
            continue
        chosen = min(exam.sets, key=lambda s: (usage[s.id], s.id))
        usage[chosen.id] += 1
        db.add(SetAssignment(exam_id=exam.id, student_id=student.id, set_id=chosen.id))
        changed += 1
    db.commit()
    return {"assigned": changed, **list_assignments(exam_id, college_id, db)}


class AssignmentIn(BaseModel):
    student_id: int
    set_id: Optional[int] = None  # None clears the assignment


class AssignmentsIn(BaseModel):
    assignments: List[AssignmentIn] = Field(..., max_length=5000)


def _apply(db: Session, exam: Exam, pairs) -> int:
    valid_sets = {s.id for s in exam.sets}
    allowed = {s.id for s in _audience(db, exam)}
    started = _started_ids(db, exam)
    existing = {a.student_id: a for a in db.query(SetAssignment).filter(SetAssignment.exam_id == exam.id).all()}
    changed = 0
    for student_id, set_id in pairs:
        if student_id not in allowed:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Student {student_id} can't take this exam")
        if set_id is not None and set_id not in valid_sets:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Set {set_id} doesn't belong to this exam")
        row = existing.get(student_id)
        if (row.set_id if row else None) == set_id:
            continue
        if student_id in started:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "A student who has already started can't be moved to another set")
        if row and set_id is None:
            db.delete(row)
        elif row:
            row.set_id = set_id
        else:
            db.add(SetAssignment(exam_id=exam.id, student_id=student_id, set_id=set_id))
        changed += 1
    db.commit()
    return changed


@router.put("/exams/{exam_id}/set-assignments")
def set_assignments(exam_id: int, body: AssignmentsIn, college_id: int = Depends(scoped_college_id),
                    db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    changed = _apply(db, exam, [(a.student_id, a.set_id) for a in body.assignments])
    if changed and exam.auto_assign_sets:
        exam.auto_assign_sets = False
        db.commit()
    return {"changed": changed, **list_assignments(exam_id, college_id, db)}


def _match_set(value: str, sets: List[QuestionSet]) -> Optional[QuestionSet]:
    v = (value or "").strip().lower()
    if not v:
        return None
    for s in sets:
        if s.name.strip().lower() == v:
            return s
    m = re.fullmatch(r"(?:set\s*[-#]?\s*)?(\d+)", v)
    if m and 1 <= int(m.group(1)) <= len(sets):
        return sets[int(m.group(1)) - 1]
    m = re.fullmatch(r"(?:set\s*[-#]?\s*)?([a-z])", v)
    if m and ord(m.group(1)) - 97 < len(sets):
        return sets[ord(m.group(1)) - 97]
    return None


@router.post("/exams/{exam_id}/set-assignments/import")
def import_assignments(exam_id: int, file: UploadFile = File(...),
                             college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    """A sheet with a roll number column and a set column ("Set 2", "2", "B" or the set's name)."""
    exam = get_exam(db, college_id, exam_id)
    if not exam.sets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Upload the sets before assigning them")
    data = file.file.read()
    try:
        kind = file_kind(file.filename or "")
        rows = table_rows(data, "csv" if kind == "txt" else kind)
        students = student_rows(data, file.filename or "")
    except ParseError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    set_col = next((c for c in ("set", "set_name", "set_no", "set_number", "question_set", "paper")
                    if rows and c in rows[0]), None)
    if not set_col:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add a 'set' column next to the roll numbers")
    by_roll = {s.roll_no.lower(): s for s in _audience(db, exam)}
    pairs, errors = [], []
    for line, (row, mapped) in enumerate(zip(rows, students), start=2):
        roll = (mapped.get("roll_no") or "").strip()
        student = by_roll.get(roll.lower())
        qset = _match_set(row.get(set_col, ""), exam.sets)
        if not student:
            errors.append({"line": line, "roll_no": roll, "error": "Not a student who can take this exam"})
        elif not qset:
            errors.append({"line": line, "roll_no": roll, "error": f'Unknown set "{row.get(set_col, "")}"'})
        else:
            pairs.append((student.id, qset.id))
    started = _started_ids(db, exam)
    skipped = [p for p in pairs if p[0] in started]
    changed = _apply(db, exam, [p for p in pairs if p[0] not in started])
    if changed and exam.auto_assign_sets:
        exam.auto_assign_sets = False
        db.commit()
    for sid, _ in skipped:
        errors.append({"line": None, "roll_no": db.get(User, sid).roll_no, "error": "Already started; left as is"})
    return {"changed": changed, "errors": errors, **list_assignments(exam_id, college_id, db)}


@router.get("/exams/{exam_id}/set-assignments/export")
def export_assignments(exam_id: int, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    data = list_assignments(exam_id, college_id, db)
    names = {s["id"]: s["name"] for s in data["sets"]}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["roll_no", "name", "branch", "section", "set"])
    for s in data["students"]:
        w.writerow([s["roll_no"], s["name"], s["branch"] or "", s["section"] or "", names.get(s["set_id"], "")])
    filename = re.sub(r"\W+", "_", exam.title) + "_sets.csv"
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ── Preview the paper as a student would see it ───────────────────────────

@router.get("/exams/{exam_id}/preview")
def preview_paper(exam_id: int, set_id: Optional[int] = None, college_id: int = Depends(scoped_college_id),
                  db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    if set_id is not None and set_id not in {s.id for s in exam.sets}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Set not found")
    chosen = set_id if set_id is not None else (exam.sets[0].id if exam.sets else None)
    items, sections = [], []
    for number, item in enumerate(engine.paper_items(exam, chosen), start=1):
        if item.section not in sections:
            sections.append(item.section)
        entry = {"item_id": item.id, "number": number, "type": item.item_type.value, "section": item.section,
                 "marks": item.effective_marks, "set_id": item.set_id}
        if item.item_type == ItemType.MCQ and item.mcq:
            q = item.mcq
            entry.update({"question_text": q.question_text, "is_multi": q.is_multi,
                          "negative_marks": q.negative_marks if exam.negative_marking else 0,
                          "options": [{"id": i, "text": t} for i, t in enumerate(q.options)],
                          "correct_options": q.correct_options, "explanation": q.explanation})
        elif item.problem:
            p = item.problem
            entry.update({"title": p.title, "difficulty": p.difficulty, "statement": p.statement,
                          "input_format": p.input_format, "output_format": p.output_format,
                          "constraints": p.constraints, "sample_tests": p.sample_tests or [],
                          "starter_code": p.starter_code or {}, "time_limit_seconds": p.time_limit_seconds,
                          "hidden_test_count": len(p.hidden_tests or [])})
        items.append(entry)
    return {
        "exam": {"id": exam.id, "title": exam.title, "instructions": exam.instructions,
                 "duration_minutes": exam.duration_minutes, "exam_type": exam.exam_type,
                 "negative_marking": exam.negative_marking, "shuffle_questions": exam.shuffle_questions,
                 "shuffle_options": exam.shuffle_options,
                 "allowed_languages": exam.allowed_languages or LANGUAGES},
        "sets": [{"id": s.id, "name": s.name} for s in exam.sets], "set_id": chosen,
        "sections": sections, "items": items, "max_score": round(sum(i["marks"] for i in items), 2),
    }


# ── Leaderboards ──────────────────────────────────────────────────────────

@router.get("/leaderboard")
def leaderboard(exam_id: Optional[int] = None, branch: Optional[str] = None, limit: int = Query(100, ge=1, le=5000),
                      college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    """One exam's ranking, or (without exam_id) every student ranked by average percentage across exams."""
    exams = db.query(Exam).filter(Exam.college_id == college_id).order_by(Exam.start_at.desc()).all()
    exam_list = [{"id": e.id, "title": e.title} for e in exams]

    def keep(student: User) -> bool:
        return not branch or (student.branch or "").lower() == branch.lower()

    if exam_id is not None:
        exam = get_exam(db, college_id, exam_id)
        for a in db.query(Attempt).filter(Attempt.exam_id == exam.id, Attempt.status == AttemptStatus.IN_PROGRESS).all():
            engine.finalize_if_expired(db, a)
        ranked = [a for a in engine.rank_attempts(db.query(Attempt).filter(Attempt.exam_id == exam.id).all())
                  if keep(a.student)]
        set_names = {s.id: s.name for s in exam.sets}
        rows = [{"rank": i + 1, "student_id": a.student_id, "roll_no": a.student.roll_no, "name": a.student.name,
                 "branch": a.student.branch, "section": a.student.section,
                 "total_score": a.total_score, "max_score": a.max_score, "percentage": engine.percentage(a),
                 "time_taken_seconds": engine.time_taken_seconds(a), "set_name": set_names.get(a.set_id),
                 "passed": engine.percentage(a) >= exam.pass_percentage}
                for i, a in enumerate(ranked[:limit])]
        return {"mode": "exam", "exam": {"id": exam.id, "title": exam.title}, "exams": exam_list,
                "participants": len(ranked), "rows": rows}

    per_student = defaultdict(list)
    exam_ids = [e.id for e in exams]
    attempts = db.query(Attempt).filter(Attempt.exam_id.in_(exam_ids), Attempt.status != AttemptStatus.IN_PROGRESS).all() \
        if exam_ids else []
    for a in attempts:
        if a.max_score and keep(a.student):
            per_student[a.student_id].append(a)
    rows = []
    for sid, items in per_student.items():
        pcts = [engine.percentage(a) for a in items]
        s = items[0].student
        rows.append({"student_id": sid, "roll_no": s.roll_no, "name": s.name, "branch": s.branch,
                     "section": s.section, "exams_taken": len(items),
                     "average_percentage": round(sum(pcts) / len(pcts), 1), "best_percentage": max(pcts),
                     "total_score": round(sum(a.total_score for a in items), 2)})
    rows.sort(key=lambda r: (-r["average_percentage"], -r["exams_taken"], r["roll_no"]))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return {"mode": "overall", "exams": exam_list, "participants": len(rows), "rows": rows[:limit]}
