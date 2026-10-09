"""
College admin endpoints: students, question banks, exams, results and proctoring.
Super admins can use every endpoint here too, passing ?college_id= to pick the college.
"""
import csv
import io
from datetime import datetime
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import get_db
from app.reios import engine
from app.reios.models import (
    DIFFICULTIES, EXAM_TYPES, LANGUAGES, SECTIONS, Announcement, Attempt, AttemptStatus, CodeAnswer,
    CodingProblem, College, Exam, ExamItem, ItemType, MCQAnswer, MCQQuestion, ProctorEvent, QuestionSet,
    Role, SetAssignment, User,
)
from app.reios.features import has_feature, require_feature, send_emails
from app.reios.parsers import ParseError, student_rows
from app.reios.security import (
    as_utc, bank_scope, generate_password, require_admin, scoped_college_id, utcnow,
)

router = APIRouter(prefix="/api/reios/admin", tags=["Reios College Admin"])

MAX_IMPORT_ROWS = 5000


# ══════════════════════════════════════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════════════════════════════════════

class StudentIn(BaseModel):
    roll_no: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=32)
    branch: Optional[str] = Field(None, max_length=64)
    section: Optional[str] = Field(None, max_length=32)
    batch_year: Optional[int] = Field(None, ge=1990, le=2100)
    password: Optional[str] = Field(None, min_length=6, max_length=128)


class StudentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=32)
    branch: Optional[str] = Field(None, max_length=64)
    section: Optional[str] = Field(None, max_length=32)
    batch_year: Optional[int] = Field(None, ge=1990, le=2100)
    is_active: Optional[bool] = None


class BulkIds(BaseModel):
    ids: List[int] = Field(..., min_length=1, max_length=5000)


class MCQIn(BaseModel):
    section: str = Field(..., min_length=1, max_length=64)
    topic: Optional[str] = Field(None, max_length=128)
    difficulty: str = "medium"
    question_text: str = Field(..., min_length=1)
    options: List[str] = Field(..., min_length=2, max_length=8)
    correct_options: List[int] = Field(..., min_length=1)
    is_multi: bool = False
    explanation: Optional[str] = None
    marks: float = Field(1.0, gt=0, le=100)
    negative_marks: float = Field(0.0, ge=0, le=100)
    is_active: bool = True

    @field_validator("difficulty")
    @classmethod
    def check_difficulty(cls, v):
        if v not in DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {DIFFICULTIES}")
        return v

    @model_validator(mode="after")
    def check_options(self):
        self.options = [o.strip() for o in self.options]
        if any(not o for o in self.options):
            raise ValueError("Options cannot be empty")
        self.correct_options = sorted(set(self.correct_options))
        if any(i < 0 or i >= len(self.options) for i in self.correct_options):
            raise ValueError("correct_options must point at existing options (0-based)")
        if not self.is_multi and len(self.correct_options) != 1:
            raise ValueError("Single-answer questions need exactly one correct option")
        return self


class TestCase(BaseModel):
    input: str = ""
    output: str
    explanation: Optional[str] = None


class ProblemIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    difficulty: str = "medium"
    statement: str = Field(..., min_length=1)
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    constraints: Optional[str] = None
    sample_tests: List[TestCase] = Field(..., min_length=1, max_length=10)
    hidden_tests: List[TestCase] = Field(default_factory=list, max_length=50)
    starter_code: Optional[dict] = None
    marks: float = Field(10.0, gt=0, le=1000)
    time_limit_seconds: int = Field(5, ge=1, le=20)
    is_active: bool = True

    @field_validator("difficulty")
    @classmethod
    def check_difficulty(cls, v):
        if v not in DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {DIFFICULTIES}")
        return v

    @field_validator("starter_code")
    @classmethod
    def check_starter(cls, v):
        if v:
            unknown = set(v) - set(LANGUAGES)
            if unknown:
                raise ValueError(f"Unknown languages in starter_code: {sorted(unknown)}")
        return v


class ExamIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    instructions: Optional[str] = None
    start_at: datetime
    end_at: datetime
    duration_minutes: int = Field(60, ge=1, le=600)
    branch_filter: Optional[str] = Field(None, max_length=255)
    batch_filter: Optional[str] = Field(None, max_length=255)
    section_filter: Optional[str] = Field(None, max_length=255)
    shuffle_questions: bool = True
    shuffle_options: bool = True
    negative_marking: bool = False
    allowed_languages: Optional[List[str]] = None
    require_fullscreen: bool = True
    block_copy_paste: bool = True
    max_violations: int = Field(3, ge=1, le=50)
    show_results: bool = True
    show_answers: bool = False
    pass_percentage: float = Field(40.0, ge=0, le=100)
    show_leaderboard: bool = False
    exam_type: str = "mixed"

    @field_validator("exam_type")
    @classmethod
    def check_exam_type(cls, v):
        if v not in EXAM_TYPES:
            raise ValueError(f"exam_type must be one of {EXAM_TYPES}")
        return v

    @field_validator("allowed_languages")
    @classmethod
    def check_languages(cls, v):
        if v:
            unknown = set(v) - set(LANGUAGES)
            if unknown:
                raise ValueError(f"Unknown languages: {sorted(unknown)}")
        return v or None

    @model_validator(mode="after")
    def check_window(self):
        if as_utc(self.end_at) <= as_utc(self.start_at):
            raise ValueError("end_at must be after start_at")
        return self


class ExamUpdate(ExamIn):
    # Same fields as ExamIn; every field is re-sent by the console
    pass


class ExamItemIn(BaseModel):
    item_type: ItemType
    question_id: int
    section: Optional[str] = Field(None, max_length=64)
    marks: Optional[float] = Field(None, gt=0, le=1000)


class ExamItemsIn(BaseModel):
    items: List[ExamItemIn] = Field(..., max_length=500)


class AnnouncementIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=5000)


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════

def student_payload(user: User) -> dict:
    return {
        "id": user.id, "roll_no": user.roll_no, "name": user.name, "email": user.email,
        "phone": user.phone, "branch": user.branch, "section": user.section,
        "batch_year": user.batch_year, "is_active": user.is_active,
        "must_change_password": user.must_change_password, "last_login_at": user.last_login_at,
        "created_at": user.created_at,
    }


def mcq_payload(q: MCQQuestion) -> dict:
    return {
        "id": q.id, "college_id": q.college_id, "is_global": q.college_id is None,
        "section": q.section, "topic": q.topic, "difficulty": q.difficulty,
        "question_text": q.question_text, "options": q.options, "correct_options": q.correct_options,
        "is_multi": q.is_multi, "explanation": q.explanation, "marks": q.marks,
        "negative_marks": q.negative_marks, "is_active": q.is_active, "created_at": q.created_at,
    }


def problem_payload(p: CodingProblem, full: bool = False) -> dict:
    data = {
        "id": p.id, "college_id": p.college_id, "is_global": p.college_id is None,
        "title": p.title, "difficulty": p.difficulty, "marks": p.marks,
        "time_limit_seconds": p.time_limit_seconds, "is_active": p.is_active,
        "sample_count": len(p.sample_tests or []), "hidden_count": len(p.hidden_tests or []),
        "created_at": p.created_at,
    }
    if full:
        data.update({
            "statement": p.statement, "input_format": p.input_format, "output_format": p.output_format,
            "constraints": p.constraints, "sample_tests": p.sample_tests, "hidden_tests": p.hidden_tests,
            "starter_code": p.starter_code or {},
        })
    return data


def exam_payload(exam: Exam, db: Session, with_items: bool = False) -> dict:
    counts = dict(
        db.query(Attempt.status, func.count(Attempt.id)).filter(Attempt.exam_id == exam.id)
        .group_by(Attempt.status).all()
    )
    paper = engine.paper_items(exam, None)
    data = {
        "id": exam.id, "college_id": exam.college_id, "title": exam.title,
        "description": exam.description, "instructions": exam.instructions,
        "start_at": as_utc(exam.start_at), "end_at": as_utc(exam.end_at),
        "duration_minutes": exam.duration_minutes, "is_published": exam.is_published,
        "branch_filter": exam.branch_filter, "batch_filter": exam.batch_filter,
        "section_filter": exam.section_filter, "shuffle_questions": exam.shuffle_questions,
        "shuffle_options": exam.shuffle_options, "negative_marking": exam.negative_marking,
        "allowed_languages": exam.allowed_languages, "require_fullscreen": exam.require_fullscreen,
        "block_copy_paste": exam.block_copy_paste, "max_violations": exam.max_violations,
        "show_results": exam.show_results, "show_answers": exam.show_answers,
        "pass_percentage": exam.pass_percentage, "window": engine.exam_window(exam),
        "control_state": exam.control_state,
        "exam_type": exam.exam_type, "show_leaderboard": exam.show_leaderboard,
        "set_count": len(exam.sets), "auto_assign_sets": exam.auto_assign_sets,
        "question_count": len(paper), "max_score": engine.exam_max_score(exam),
        "mcq_count": sum(1 for i in paper if i.item_type == ItemType.MCQ),
        "coding_count": sum(1 for i in paper if i.item_type == ItemType.CODING),
        "attempts": {
            "in_progress": counts.get(AttemptStatus.IN_PROGRESS, 0),
            "submitted": counts.get(AttemptStatus.SUBMITTED, 0) + counts.get(AttemptStatus.AUTO_SUBMITTED, 0),
        },
        "created_at": exam.created_at,
    }
    if with_items:
        data["items"] = [{
            "id": item.id, "item_type": item.item_type.value, "section": item.section,
            "marks": item.marks, "effective_marks": item.effective_marks, "order": item.order,
            "question_id": item.mcq_id if item.item_type == ItemType.MCQ else item.problem_id,
            "title": (item.mcq.question_text[:140] if item.mcq else "") if item.item_type == ItemType.MCQ
            else (item.problem.title if item.problem else ""),
            "difficulty": (item.mcq or item.problem).difficulty if (item.mcq or item.problem) else None,
        } for item in exam.items if item.set_id is None]
    return data


def get_student(db: Session, college_id: int, student_id: int) -> User:
    student = db.get(User, student_id)
    if not student or student.role != Role.STUDENT or student.college_id != college_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    return student


def check_exam_quota(db: Session, college_id: int) -> None:
    org = db.get(College, college_id)
    if org and org.max_exams is not None:
        used = db.query(Exam).filter(Exam.college_id == college_id).count()
        if used >= org.max_exams:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"Your plan includes {org.max_exams} exams and all are used. "
                                "Delete an unused exam or contact the Reios team to add more")


def get_exam(db: Session, college_id: int, exam_id: int) -> Exam:
    exam = db.get(Exam, exam_id)
    if not exam or exam.college_id != college_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exam not found")
    return exam


def get_attempt(db: Session, college_id: int, attempt_id: int) -> Attempt:
    attempt = db.get(Attempt, attempt_id)
    if not attempt or attempt.exam.college_id != college_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
    return attempt


def bank_query(db: Session, model, scope: Optional[int], include_global: bool = True):
    """Questions visible in a scope: the college's own plus (optionally) the global bank."""
    if scope is None:
        return db.query(model).filter(model.college_id.is_(None))
    if include_global:
        return db.query(model).filter(or_(model.college_id == scope, model.college_id.is_(None)))
    return db.query(model).filter(model.college_id == scope)


def check_bank_write(obj, user: User) -> None:
    """College admins may only edit their own college's questions, not the global bank."""
    if user.role == Role.SUPER_ADMIN:
        return
    if obj.college_id != user.college_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Global bank questions can only be edited by the super admin")


def check_capacity(db: Session, college_id: int, adding: int) -> None:
    college = db.get(College, college_id)
    if college and college.max_students:
        current = db.query(func.count(User.id)).filter(
            User.college_id == college_id, User.role == Role.STUDENT).scalar()
        if current + adding > college.max_students:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"Student limit reached: {current}/{college.max_students}. "
                                "Ask the super admin to raise the limit")


def clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def csv_rows(upload_bytes: bytes) -> List[dict]:
    try:
        text = upload_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = upload_bytes.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "CSV file is empty")
    reader.fieldnames = [(f or "").strip().lower().replace(" ", "_") for f in reader.fieldnames]
    rows = list(reader)
    if len(rows) > MAX_IMPORT_ROWS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"At most {MAX_IMPORT_ROWS} rows per import")
    return rows


def csv_response(filename: str, header: List[str], rows: List[list]) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return StreamingResponse(
        iter([buffer.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ══════════════════════════════════════════════════════════════════════════
# Dashboard
# ══════════════════════════════════════════════════════════════════════════

@router.get("/stats")
def college_stats(college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    college = db.get(College, college_id)
    exams = db.query(Exam).filter(Exam.college_id == college_id).all()
    attempts_q = db.query(Attempt).join(Exam).filter(Exam.college_id == college_id)
    finished = attempts_q.filter(Attempt.status != AttemptStatus.IN_PROGRESS).all()
    avg_pct = round(sum(a.total_score / a.max_score * 100 for a in finished if a.max_score) /
                    len(finished), 1) if finished else None
    return {
        "college": {"id": college.id, "name": college.name, "code": college.code,
                    "max_students": college.max_students, "max_exams": college.max_exams,
                    "access_until": as_utc(college.access_until), "org_type": college.org_type,
                    "organizer": college.organizer, "event_starts_at": as_utc(college.event_starts_at),
                    "features": college.features or []},
        "students": db.query(func.count(User.id)).filter(
            User.college_id == college_id, User.role == Role.STUDENT).scalar(),
        "active_students": db.query(func.count(User.id)).filter(
            User.college_id == college_id, User.role == Role.STUDENT, User.is_active.is_(True)).scalar(),
        "exams": len(exams),
        "live_exams": sum(1 for e in exams if e.is_published and engine.exam_window(e) == "live"),
        "upcoming_exams": sum(1 for e in exams if e.is_published and engine.exam_window(e) == "upcoming"),
        "live_attempts": attempts_q.filter(Attempt.status == AttemptStatus.IN_PROGRESS).count(),
        "completed_attempts": len(finished),
        "average_percentage": avg_pct,
        "mcqs": bank_query(db, MCQQuestion, college_id).filter(MCQQuestion.is_active.is_(True)).count(),
        "problems": bank_query(db, CodingProblem, college_id).filter(CodingProblem.is_active.is_(True)).count(),
        "branches": sorted({b for (b,) in db.query(User.branch).filter(
            User.college_id == college_id, User.role == Role.STUDENT, User.branch.isnot(None)).distinct()}),
    }


@router.get("/meta")
def meta():
    return {"sections": SECTIONS, "difficulties": DIFFICULTIES, "languages": LANGUAGES}


class AdminSettingsUpdate(BaseModel):
    single_login: bool


@router.get("/settings")
def get_admin_settings(college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    college = db.get(College, college_id)
    return {"single_login": college.single_login}


@router.patch("/settings")
def update_admin_settings(body: AdminSettingsUpdate, college_id: int = Depends(scoped_college_id),
                          db: Session = Depends(get_db)):
    """The event/college admin's own security settings, no super admin needed."""
    college = db.get(College, college_id)
    college.single_login = body.single_login
    db.commit()
    return {"single_login": college.single_login}


# ══════════════════════════════════════════════════════════════════════════
# Students
# ══════════════════════════════════════════════════════════════════════════

@router.get("/students")
def list_students(
    q: Optional[str] = None, branch: Optional[str] = None, section: Optional[str] = None,
    batch_year: Optional[int] = None, active: Optional[bool] = None, logged_in: Optional[bool] = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
    college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db),
):
    base = db.query(User).filter(User.college_id == college_id, User.role == Role.STUDENT)
    query = base
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.filter(or_(func.lower(User.name).like(like), func.lower(User.roll_no).like(like),
                                 func.lower(User.email).like(like)))
    if branch:
        query = query.filter(User.branch == branch)
    if section:
        query = query.filter(User.section == section)
    if batch_year:
        query = query.filter(User.batch_year == batch_year)
    if active is not None:
        query = query.filter(User.is_active.is_(active))
    if logged_in is not None:
        query = query.filter(User.last_login_at.isnot(None) if logged_in else User.last_login_at.is_(None))
    total = query.count()
    students = query.order_by(User.roll_no).offset((page - 1) * page_size).limit(page_size).all()
    logged_in_count = base.filter(User.last_login_at.isnot(None)).count()
    return {"total": total, "page": page, "page_size": page_size,
            "logged_in_count": logged_in_count, "not_logged_in_count": base.count() - logged_in_count,
            "items": [student_payload(s) for s in students]}


def _is_event(db: Session, college_id: int) -> bool:
    org = db.get(College, college_id)
    return bool(org and org.org_type == "event")


def _forces_change(db: Session, college_id: int) -> bool:
    """Colleges get generated temporary passwords; an event's organizer shares the passwords itself."""
    return not _is_event(db, college_id)


def _add_student(db: Session, college_id: int, data: StudentIn) -> Tuple[User, str]:
    is_event = _is_event(db, college_id)
    roll = data.roll_no.strip().upper()
    if db.query(User).filter(User.college_id == college_id, func.upper(User.roll_no) == roll).first():
        raise ValueError(f"{'Team code' if is_event else 'Roll number'} {roll} already exists")
    email = clean(data.email)
    if email:
        email = email.lower()
        if db.query(User).filter(func.lower(User.email) == email).first():
            raise ValueError(f"Email {email} is already registered")
    # Events commonly use the team name itself as the password (team code + team name, nothing else to share)
    default_password = data.name.strip() if is_event else generate_password(8)
    password = data.password or default_password
    student = User(
        role=Role.STUDENT, college_id=college_id, roll_no=roll, name=data.name.strip(), email=email,
        phone=clean(data.phone), branch=clean(data.branch) and data.branch.strip().upper(),
        section=clean(data.section) and data.section.strip().upper(), batch_year=data.batch_year,
        hashed_password=hash_password(password), must_change_password=not is_event,
    )
    db.add(student)
    db.flush()
    return student, password


@router.post("/students", status_code=status.HTTP_201_CREATED)
def create_student(body: StudentIn, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    check_capacity(db, college_id, 1)
    try:
        student, password = _add_student(db, college_id, body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    db.commit()
    return {**student_payload(student), "temporary_password": password}


@router.post("/students/import")
def import_students(file: UploadFile = File(...), college_id: int = Depends(scoped_college_id),
                          db: Session = Depends(get_db)):
    """
    CSV columns: roll_no, name, email, phone, branch, section, batch_year, password
    Only roll_no and name are required. Blank passwords get a generated one.
    """
    try:
        rows = student_rows(file.file.read(), file.filename or "students.csv")
    except ParseError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    if len(rows) > MAX_IMPORT_ROWS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"At most {MAX_IMPORT_ROWS} rows per import")
    check_capacity(db, college_id, len(rows))
    created, errors = [], []
    for line, row in enumerate(rows, start=2):
        try:
            batch = clean(row.get("batch_year"))
            data = StudentIn(
                roll_no=clean(row.get("roll_no")) or "", name=clean(row.get("name")) or "",
                email=clean(row.get("email")), phone=clean(row.get("phone")),
                branch=clean(row.get("branch")), section=clean(row.get("section")),
                batch_year=int(batch) if batch else None, password=clean(row.get("password")),
            )
            with db.begin_nested():
                student, password = _add_student(db, college_id, data)
            created.append({"roll_no": student.roll_no, "name": student.name, "password": password})
        except Exception as exc:  # validation or duplicate
            message = str(exc).split("\n")[0] if not hasattr(exc, "errors") else \
                "; ".join(f"{e['loc'][-1]}: {e['msg']}" for e in exc.errors())
            errors.append({"line": line, "roll_no": row.get("roll_no"), "error": message})
    db.commit()
    return {"created": len(created), "failed": len(errors), "credentials": created, "errors": errors}


@router.patch("/students/{student_id}")
def update_student(student_id: int, body: StudentUpdate, college_id: int = Depends(scoped_college_id),
                   db: Session = Depends(get_db)):
    student = get_student(db, college_id, student_id)
    data = body.model_dump(exclude_unset=True)
    if "email" in data and data["email"]:
        email = data["email"].strip().lower()
        clash = db.query(User).filter(func.lower(User.email) == email, User.id != student.id).first()
        if clash:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
        data["email"] = email
    for key in ("branch", "section"):
        if data.get(key):
            data[key] = data[key].strip().upper()
    for field, value in data.items():
        setattr(student, field, value)
    if body.is_active is False:
        student.token_version += 1
    db.commit()
    return student_payload(student)


@router.post("/students/{student_id}/reset-password")
def reset_student_password(student_id: int, college_id: int = Depends(scoped_college_id),
                           db: Session = Depends(get_db)):
    student = get_student(db, college_id, student_id)
    password = generate_password(8)
    student.hashed_password = hash_password(password)
    student.must_change_password = _forces_change(db, college_id)
    student.token_version += 1
    student.locked_until = None
    student.failed_login_attempts = 0
    db.commit()
    return {"id": student.id, "roll_no": student.roll_no, "temporary_password": password}


@router.post("/students/bulk-reset-passwords")
def bulk_reset_passwords(body: BulkIds, college_id: int = Depends(scoped_college_id),
                         db: Session = Depends(get_db)):
    students = db.query(User).filter(User.id.in_(body.ids), User.college_id == college_id,
                                     User.role == Role.STUDENT).all()
    credentials = []
    for student in students:
        password = generate_password(8)
        student.hashed_password = hash_password(password)
        student.must_change_password = _forces_change(db, college_id)
        student.token_version += 1
        credentials.append({"roll_no": student.roll_no, "name": student.name, "password": password})
    db.commit()
    return {"credentials": credentials}


@router.post("/students/bulk-status")
def bulk_status(body: BulkIds, active: bool, college_id: int = Depends(scoped_college_id),
                db: Session = Depends(get_db)):
    students = db.query(User).filter(User.id.in_(body.ids), User.college_id == college_id,
                                     User.role == Role.STUDENT).all()
    for student in students:
        student.is_active = active
        if not active:
            student.token_version += 1
    db.commit()
    return {"updated": len(students)}


def _reset_login(student: User) -> None:
    """Sign a student/team out everywhere right now, and free their single-login slot so they can
    sign back in immediately instead of waiting for it to lapse."""
    student.token_version += 1
    student.active_session_expires_at = None


@router.post("/students/bulk-reset-login")
def bulk_reset_login(body: BulkIds, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    students = db.query(User).filter(User.id.in_(body.ids), User.college_id == college_id,
                                     User.role == Role.STUDENT).all()
    for student in students:
        _reset_login(student)
    db.commit()
    return {"updated": len(students)}


@router.post("/students/reset-login-all")
def reset_login_all(college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    """Force-logout every student/team in this college/event at once."""
    students = db.query(User).filter(User.college_id == college_id, User.role == Role.STUDENT).all()
    for student in students:
        _reset_login(student)
    db.commit()
    return {"updated": len(students)}


@router.delete("/students")
def delete_all_students(confirm: str = Query(..., description="The college/event code, typed to confirm"),
                        force: bool = Query(False, description="Also erase exam attempts and results"),
                        college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    """Wipe every student/team in this college/event in one go (e.g. clearing test data before a real event)."""
    college = db.get(College, college_id)
    if not college or confirm.strip().upper() != college.code.upper():
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Type the {'event' if college and college.org_type == 'event' else 'college'} "
                            f"code ({college.code if college else '?'}) to confirm")
    student_ids = [uid for (uid,) in db.query(User.id).filter(
        User.college_id == college_id, User.role == Role.STUDENT).all()]
    if not student_ids:
        return {"deleted": 0, "attempts_removed": 0}
    attempts = db.query(Attempt).filter(Attempt.student_id.in_(student_ids)).all()
    if attempts and not force:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{len({a.student_id for a in attempts})} of them have exam attempts. Delete again "
                            "to also erase those results, instead of deleting them")
    attempt_ids = [a.id for a in attempts]
    gone = dict(synchronize_session=False)
    for model in (MCQAnswer, CodeAnswer, ProctorEvent):
        db.query(model).filter(model.attempt_id.in_(attempt_ids)).delete(**gone)
    db.query(Attempt).filter(Attempt.id.in_(attempt_ids)).delete(**gone)
    db.query(SetAssignment).filter(SetAssignment.student_id.in_(student_ids)).delete(**gone)
    deleted = db.query(User).filter(User.id.in_(student_ids)).delete(**gone)
    db.commit()
    return {"deleted": deleted, "attempts_removed": len(attempt_ids)}


@router.delete("/students/{student_id}")
def delete_student(student_id: int, force: bool = Query(False, description="Also erase their exam attempts and results"),
                   college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    student = get_student(db, college_id, student_id)
    attempts = db.query(Attempt).filter(Attempt.student_id == student.id).all()
    if attempts and not force:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This student has exam attempts. Deactivate the account, or delete again to "
                            "also erase their results, instead of deleting it")
    db.query(SetAssignment).filter(SetAssignment.student_id == student.id).delete(synchronize_session=False)
    for attempt in attempts:  # loaded as objects so mcq/code answers and proctor events cascade with them
        db.delete(attempt)
    db.delete(student)
    db.commit()
    return {"deleted": student_id, "attempts_removed": len(attempts)}


@router.get("/students/{student_id}/report")
def student_report(student_id: int, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    student = get_student(db, college_id, student_id)
    attempts = db.query(Attempt).filter(Attempt.student_id == student.id).order_by(Attempt.started_at.desc()).all()
    return {
        "student": student_payload(student),
        "attempts": [{
            "attempt_id": a.id, "exam_id": a.exam_id, "exam_title": a.exam.title, "status": a.status.value,
            "started_at": as_utc(a.started_at), "submitted_at": as_utc(a.submitted_at),
            "total_score": a.total_score, "max_score": a.max_score,
            "percentage": round(a.total_score / a.max_score * 100, 1) if a.max_score else 0,
            "violations": a.violation_count,
        } for a in attempts],
    }


# ══════════════════════════════════════════════════════════════════════════
# MCQ bank
# ══════════════════════════════════════════════════════════════════════════

@router.get("/mcqs")
def list_mcqs(
    q: Optional[str] = None, section: Optional[str] = None, difficulty: Optional[str] = None,
    source: str = Query("all", pattern="^(all|own|global)$"), include_inactive: bool = False,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
    scope: Optional[int] = Depends(bank_scope), db: Session = Depends(get_db),
):
    if source == "global":
        query = db.query(MCQQuestion).filter(MCQQuestion.college_id.is_(None))
    else:
        query = bank_query(db, MCQQuestion, scope, include_global=(source == "all"))
    if not include_inactive:
        query = query.filter(MCQQuestion.is_active.is_(True))
    if q:
        query = query.filter(func.lower(MCQQuestion.question_text).like(f"%{q.strip().lower()}%"))
    if section:
        query = query.filter(MCQQuestion.section == section)
    if difficulty:
        query = query.filter(MCQQuestion.difficulty == difficulty)
    total = query.count()
    rows = query.order_by(MCQQuestion.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [mcq_payload(r) for r in rows]}


@router.post("/mcqs", status_code=status.HTTP_201_CREATED)
def create_mcq(body: MCQIn, scope: Optional[int] = Depends(bank_scope), user: User = Depends(require_admin),
               db: Session = Depends(get_db)):
    q = MCQQuestion(college_id=scope, created_by=user.id, **body.model_dump())
    db.add(q)
    db.commit()
    db.refresh(q)
    return mcq_payload(q)


@router.put("/mcqs/{mcq_id}")
def update_mcq(mcq_id: int, body: MCQIn, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    q = db.get(MCQQuestion, mcq_id)
    if not q:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    check_bank_write(q, user)
    for field, value in body.model_dump().items():
        setattr(q, field, value)
    db.commit()
    return mcq_payload(q)


@router.delete("/mcqs/{mcq_id}")
def delete_mcq(mcq_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    q = db.get(MCQQuestion, mcq_id)
    if not q:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    check_bank_write(q, user)
    if db.query(ExamItem).filter(ExamItem.mcq_id == q.id).first():
        q.is_active = False  # keep it so past exams stay intact
        db.commit()
        return {"deactivated": mcq_id}
    db.delete(q)
    db.commit()
    return {"deleted": mcq_id}


LETTERS = "ABCDEFGH"


@router.post("/mcqs/import")
def import_mcqs(file: UploadFile = File(...), scope: Optional[int] = Depends(bank_scope),
                      user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """
    CSV columns: section, topic, difficulty, question, option_a, option_b, option_c, option_d,
    (option_e..option_h optional), correct (e.g. "B" or "A,C"), marks, negative_marks, explanation
    """
    rows = csv_rows(file.file.read())
    created, errors = 0, []
    for line, row in enumerate(rows, start=2):
        try:
            options = []
            for letter in LETTERS.lower():
                value = clean(row.get(f"option_{letter}"))
                if value is None:
                    break
                options.append(value)
            correct_raw = (row.get("correct") or row.get("answer") or "").upper().replace(" ", "")
            correct = [LETTERS.index(c) for c in correct_raw.split(",") if c]
            data = MCQIn(
                section=clean(row.get("section")) or "General", topic=clean(row.get("topic")),
                difficulty=(clean(row.get("difficulty")) or "medium").lower(),
                question_text=clean(row.get("question")) or "", options=options, correct_options=correct,
                is_multi=len(correct) > 1, explanation=clean(row.get("explanation")),
                marks=float(clean(row.get("marks")) or 1), negative_marks=float(clean(row.get("negative_marks")) or 0),
            )
            db.add(MCQQuestion(college_id=scope, created_by=user.id, **data.model_dump()))
            created += 1
        except Exception as exc:
            message = "; ".join(e["msg"] for e in exc.errors()) if hasattr(exc, "errors") else str(exc)
            errors.append({"line": line, "error": message})
    db.commit()
    return {"created": created, "failed": len(errors), "errors": errors}


# ══════════════════════════════════════════════════════════════════════════
# Coding problems
# ══════════════════════════════════════════════════════════════════════════

@router.get("/problems")
def list_problems(
    q: Optional[str] = None, difficulty: Optional[str] = None,
    source: str = Query("all", pattern="^(all|own|global)$"), include_inactive: bool = False,
    scope: Optional[int] = Depends(bank_scope), db: Session = Depends(get_db),
):
    if source == "global":
        query = db.query(CodingProblem).filter(CodingProblem.college_id.is_(None))
    else:
        query = bank_query(db, CodingProblem, scope, include_global=(source == "all"))
    if not include_inactive:
        query = query.filter(CodingProblem.is_active.is_(True))
    if q:
        query = query.filter(func.lower(CodingProblem.title).like(f"%{q.strip().lower()}%"))
    if difficulty:
        query = query.filter(CodingProblem.difficulty == difficulty)
    return [problem_payload(p) for p in query.order_by(CodingProblem.id.desc()).all()]


@router.get("/problems/{problem_id}")
def get_problem(problem_id: int, scope: Optional[int] = Depends(bank_scope), db: Session = Depends(get_db)):
    p = db.get(CodingProblem, problem_id)
    if not p or (p.college_id is not None and p.college_id != scope and scope is not None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem not found")
    return problem_payload(p, full=True)


@router.post("/problems", status_code=status.HTTP_201_CREATED)
def create_problem(body: ProblemIn, scope: Optional[int] = Depends(bank_scope),
                   user: User = Depends(require_admin), db: Session = Depends(get_db)):
    data = body.model_dump()
    p = CodingProblem(college_id=scope, created_by=user.id, **data)
    db.add(p)
    db.commit()
    db.refresh(p)
    return problem_payload(p, full=True)


@router.put("/problems/{problem_id}")
def update_problem(problem_id: int, body: ProblemIn, user: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    p = db.get(CodingProblem, problem_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem not found")
    check_bank_write(p, user)
    for field, value in body.model_dump().items():
        setattr(p, field, value)
    db.commit()
    return problem_payload(p, full=True)


@router.delete("/problems/{problem_id}")
def delete_problem(problem_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.get(CodingProblem, problem_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem not found")
    check_bank_write(p, user)
    if db.query(ExamItem).filter(ExamItem.problem_id == p.id).first():
        p.is_active = False
        db.commit()
        return {"deactivated": problem_id}
    db.delete(p)
    db.commit()
    return {"deleted": problem_id}


class RunReferenceIn(BaseModel):
    language: str
    code: str = Field(..., max_length=engine.MAX_CODE_LENGTH)


@router.post("/problems/{problem_id}/verify")
def verify_problem(problem_id: int, body: RunReferenceIn, scope: Optional[int] = Depends(bank_scope),
                         db: Session = Depends(get_db)):
    """Run a reference solution against every sample and hidden test to check the test data."""
    p = db.get(CodingProblem, problem_id)
    if not p or (p.college_id is not None and scope is not None and p.college_id != scope):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problem not found")
    if body.language not in LANGUAGES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported language")
    tests = [{**t, "kind": "sample"} for t in p.sample_tests or []] + \
            [{**t, "kind": "hidden"} for t in p.hidden_tests or []]
    results = engine.run_tests(body.code, body.language, tests, p.time_limit_seconds)
    return {
        "passed": sum(r["passed"] for r in results), "total": len(results),
        "results": [{"kind": t["kind"], "passed": r["passed"], "expected": t.get("output", ""),
                     "actual": r["stdout"], "stderr": r["stderr"][:2000], "time_ms": r["time_ms"]}
                    for t, r in zip(tests, results)],
    }


# ══════════════════════════════════════════════════════════════════════════
# Exams
# ══════════════════════════════════════════════════════════════════════════

@router.get("/exams")
def list_exams(college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    exams = db.query(Exam).filter(Exam.college_id == college_id).order_by(Exam.start_at.desc()).all()
    return [exam_payload(e, db) for e in exams]


@router.post("/exams", status_code=status.HTTP_201_CREATED)
def create_exam(body: ExamIn, college_id: int = Depends(scoped_college_id), user: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    check_exam_quota(db, college_id)
    exam = Exam(college_id=college_id, created_by=user.id, **body.model_dump())
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam_payload(exam, db, with_items=True)


@router.get("/exams/{exam_id}")
def get_exam_detail(exam_id: int, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    return exam_payload(get_exam(db, college_id, exam_id), db, with_items=True)


@router.put("/exams/{exam_id}")
def update_exam(exam_id: int, body: ExamUpdate, college_id: int = Depends(scoped_college_id),
                db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    check_items_fit_type(body.exam_type, [i.item_type for i in exam.items])
    for field, value in body.model_dump().items():
        setattr(exam, field, value)
    db.commit()
    return exam_payload(exam, db, with_items=True)


@router.put("/exams/{exam_id}/items")
def set_exam_items(exam_id: int, body: ExamItemsIn, college_id: int = Depends(scoped_college_id),
                   db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    if db.query(Attempt).filter(Attempt.exam_id == exam.id).first():
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Students have already started this exam, so its questions can't be changed")
    seen = set()
    new_items = []
    for order, item in enumerate(body.items):
        key = (item.item_type, item.question_id)
        if key in seen:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "The same question was added twice")
        seen.add(key)
        if item.item_type == ItemType.MCQ:
            q = db.get(MCQQuestion, item.question_id)
            if not q or (q.college_id not in (None, college_id)):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"MCQ {item.question_id} not found")
            new_items.append(ExamItem(item_type=ItemType.MCQ, mcq_id=q.id, section=item.section or q.section,
                                      marks=item.marks, order=order))
        else:
            p = db.get(CodingProblem, item.question_id)
            if not p or (p.college_id not in (None, college_id)):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Coding problem {item.question_id} not found")
            new_items.append(ExamItem(item_type=ItemType.CODING, problem_id=p.id, section=item.section or "Coding",
                                      marks=item.marks, order=order))
    check_items_fit_type(exam.exam_type, [i.item_type for i in new_items]
                         + [i.item_type for i in exam.items if i.set_id is not None])
    for old in [i for i in exam.items if i.set_id is None]:
        exam.items.remove(old)
    db.flush()
    exam.items.extend(new_items)
    db.commit()
    db.refresh(exam)
    return exam_payload(exam, db, with_items=True)


def check_items_fit_type(exam_type: str, item_types) -> None:
    kinds = set(item_types)
    if exam_type == "mcq" and ItemType.CODING in kinds:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "This is an MCQ-only exam. Remove the coding questions or change the exam type to Mixed")
    if exam_type == "coding" and ItemType.MCQ in kinds:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "This is a coding-only exam. Remove the MCQs or change the exam type to Mixed")


class AutoPickIn(BaseModel):
    section: str
    count: int = Field(..., ge=1, le=200)
    difficulty: Optional[str] = None


@router.post("/exams/{exam_id}/random-mcqs")
def pick_random_mcqs(exam_id: int, body: AutoPickIn, college_id: int = Depends(scoped_college_id),
                     db: Session = Depends(get_db)):
    """Suggest random MCQ ids from the bank for a section (the console then saves the item list)."""
    get_exam(db, college_id, exam_id)
    query = bank_query(db, MCQQuestion, college_id).filter(MCQQuestion.is_active.is_(True),
                                                            MCQQuestion.section == body.section)
    if body.difficulty:
        query = query.filter(MCQQuestion.difficulty == body.difficulty)
    rows = query.order_by(func.random()).limit(body.count).all()
    return [mcq_payload(r) for r in rows]


@router.post("/exams/{exam_id}/publish")
def publish_exam(exam_id: int, publish: bool = True, college_id: int = Depends(scoped_college_id),
                 db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    if publish and not exam.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add questions before publishing")
    exam.is_published = publish
    db.commit()
    return exam_payload(exam, db)


@router.post("/exams/{exam_id}/control")
def control_exam(exam_id: int, action: str = Query(..., pattern="^(start|pause|resume|end)$"),
                 college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    """Start/pause/resume/end an exam right now, overriding its scheduled start_at/end_at."""
    exam = get_exam(db, college_id, exam_id)
    if action in ("start", "resume") and not exam.is_published:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Publish the exam before starting it")
    if exam.control_state == "ended":
        raise HTTPException(status.HTTP_409_CONFLICT, "This exam has already ended and can't be reopened")
    if action == "resume":
        engine.resume_from_pause(db, exam)
        exam.control_state = "live"
    elif action == "start":
        exam.control_state = "live"
    elif action == "pause":
        exam.control_state = "paused"
        exam.paused_at = utcnow()
    elif action == "end":
        engine.resume_from_pause(db, exam)  # don't leave a dangling paused_at behind
        exam.control_state = "ended"
        engine.force_submit_in_progress(db, exam.id, "ended_by_admin")
    db.commit()
    return exam_payload(exam, db)


@router.delete("/exams/{exam_id}")
def delete_exam(exam_id: int, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    if db.query(Attempt).filter(Attempt.exam_id == exam.id).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Exam has attempts and can't be deleted. Unpublish it instead")
    # Set questions live only inside this exam; bank questions (active) are left alone
    set_mcq_ids = [i.mcq_id for i in exam.items if i.set_id is not None and i.mcq_id]
    db.query(SetAssignment).filter(SetAssignment.exam_id == exam.id).delete()
    db.delete(exam)
    db.flush()
    if set_mcq_ids:
        still_used = {m for (m,) in db.query(ExamItem.mcq_id).filter(ExamItem.mcq_id.in_(set_mcq_ids)).all()}
        db.query(MCQQuestion).filter(MCQQuestion.id.in_([m for m in set_mcq_ids if m not in still_used]),
                                     MCQQuestion.is_active.is_(False)).delete(synchronize_session=False)
    db.commit()
    return {"deleted": exam_id}


@router.post("/exams/{exam_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_exam(exam_id: int, college_id: int = Depends(scoped_college_id), user: User = Depends(require_admin),
                   db: Session = Depends(get_db)):
    src = get_exam(db, college_id, exam_id)
    check_exam_quota(db, college_id)
    copy = Exam(college_id=college_id, created_by=user.id, title=f"{src.title} (copy)", is_published=False,
                **{c: getattr(src, c) for c in (
                    "description", "instructions", "start_at", "end_at", "duration_minutes", "branch_filter",
                    "batch_filter", "section_filter", "shuffle_questions", "shuffle_options",
                    "negative_marking", "allowed_languages", "require_fullscreen", "block_copy_paste",
                    "max_violations", "show_results", "show_answers", "pass_percentage",
                    "show_leaderboard", "exam_type", "auto_assign_sets")})
    src_items = list(src.items)
    copy.sets = [QuestionSet(name=qs.name, source_filename=qs.source_filename) for qs in src.sets]
    copy.items = [ExamItem(item_type=i.item_type, mcq_id=i.mcq_id, problem_id=i.problem_id, section=i.section,
                           marks=i.marks, order=i.order) for i in src_items]
    db.add(copy)
    db.flush()
    set_map = {old.id: new.id for old, new in zip(src.sets, copy.sets)}
    for new_item, old_item in zip(copy.items, src_items):
        new_item.set_id = set_map.get(old_item.set_id)
    db.commit()
    db.refresh(copy)
    return exam_payload(copy, db, with_items=True)


# ══════════════════════════════════════════════════════════════════════════
# Results, monitoring and proctoring
# ══════════════════════════════════════════════════════════════════════════

def _finalize_expired(db: Session, exam: Exam) -> None:
    for attempt in db.query(Attempt).filter(Attempt.exam_id == exam.id,
                                            Attempt.status == AttemptStatus.IN_PROGRESS).all():
        engine.finalize_if_expired(db, attempt)


def _section_scores(attempt: Attempt) -> dict:
    items = {i.id: i for i in attempt.exam.items}
    scores = {items[i].section: 0.0 for i in attempt.item_order if i in items}
    for answer in list(attempt.mcq_answers) + list(attempt.code_answers):
        item = items.get(answer.item_id)
        if item:
            scores[item.section] = round(scores.get(item.section, 0) + answer.marks_awarded, 2)
    return scores


@router.get("/exams/{exam_id}/results")
def exam_results(exam_id: int, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    _finalize_expired(db, exam)
    attempts = db.query(Attempt).filter(Attempt.exam_id == exam.id).all()
    finished = engine.rank_attempts(attempts)
    ranks = {a.id: idx + 1 for idx, a in enumerate(finished)}
    set_names = {qs.id: qs.name for qs in exam.sets}

    eligible = [s for s in db.query(User).filter(User.college_id == college_id, User.role == Role.STUDENT,
                                                 User.is_active.is_(True)).all()
                if engine.student_is_eligible(exam, s)] if exam.is_published else []
    attempted_ids = {a.student_id for a in attempts}

    rows = []
    for a in attempts:
        pct = round(a.total_score / a.max_score * 100, 1) if a.max_score else 0
        rows.append({
            "attempt_id": a.id, "rank": ranks.get(a.id), "student_id": a.student_id,
            "roll_no": a.student.roll_no, "name": a.student.name, "branch": a.student.branch,
            "section": a.student.section, "status": a.status.value, "submit_reason": a.submit_reason,
            "started_at": as_utc(a.started_at), "submitted_at": as_utc(a.submitted_at),
            "mcq_score": a.mcq_score, "coding_score": a.coding_score, "total_score": a.total_score,
            "max_score": a.max_score, "percentage": pct, "passed": pct >= exam.pass_percentage,
            "violations": a.violation_count, "section_scores": _section_scores(a),
            "set_name": set_names.get(a.set_id),
            "time_taken_seconds": int((as_utc(a.submitted_at) - as_utc(a.started_at)).total_seconds())
            if a.submitted_at else None,
        })
    rows.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0))
    scores = [r["percentage"] for r in rows if r["status"] != "in_progress"]
    return {
        "exam": exam_payload(exam, db),
        "summary": {
            "eligible": len(eligible), "attempted": len(attempts),
            "not_attempted": len([s for s in eligible if s.id not in attempted_ids]),
            "completed": len(finished), "in_progress": len(attempts) - len(finished),
            "average_percentage": round(sum(scores) / len(scores), 1) if scores else None,
            "highest_percentage": max(scores) if scores else None,
            "pass_count": sum(1 for r in rows if r["status"] != "in_progress" and r["passed"]),
            "flagged": sum(1 for r in rows if r["violations"] > 0),
        },
        "results": rows,
        "absentees": [{"student_id": s.id, "roll_no": s.roll_no, "name": s.name, "branch": s.branch}
                      for s in eligible if s.id not in attempted_ids],
    }


@router.get("/exams/{exam_id}/export")
def export_results(exam_id: int, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    data = exam_results(exam_id, college_id, db)
    sections = sorted({s for r in data["results"] for s in r["section_scores"]})
    header = ["Rank", "Roll No", "Name", "Branch", "Section", "Status"] + sections + \
             ["MCQ Score", "Coding Score", "Total", "Max", "Percentage", "Result", "Violations",
              "Time Taken (min)", "Submit Reason"]
    rows = []
    for r in data["results"]:
        rows.append([r["rank"] or "", r["roll_no"], r["name"], r["branch"] or "", r["section"] or "", r["status"]] +
                    [r["section_scores"].get(s, 0) for s in sections] +
                    [r["mcq_score"], r["coding_score"], r["total_score"], r["max_score"], r["percentage"],
                     "PASS" if r["passed"] else "FAIL", r["violations"],
                     round(r["time_taken_seconds"] / 60, 1) if r["time_taken_seconds"] else "",
                     r["submit_reason"] or ""])
    for s in data["absentees"]:
        rows.append(["", s["roll_no"], s["name"], s["branch"] or "", "", "absent"] + [""] * (len(sections) + 9))
    safe_title = "".join(c if c.isalnum() else "_" for c in data["exam"]["title"])[:60]
    return csv_response(f"{safe_title}_results.csv", header, rows)


@router.get("/exams/{exam_id}/live")
def live_monitor(exam_id: int, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    _finalize_expired(db, exam)
    now = utcnow()
    attempts = db.query(Attempt).filter(Attempt.exam_id == exam.id).all()
    rows = []
    for a in attempts:
        answered = sum(1 for m in a.mcq_answers if m.selected) + sum(1 for c in a.code_answers if c.code.strip())
        heartbeat = as_utc(a.last_heartbeat_at)
        last_event = a.events[-1] if a.events else None
        rows.append({
            "attempt_id": a.id, "roll_no": a.student.roll_no, "name": a.student.name,
            "status": a.status.value, "submit_reason": a.submit_reason,
            "answered": answered, "total": len(a.item_order or []),
            "violations": a.violation_count, "max_violations": exam.max_violations,
            "online": bool(heartbeat and (now - heartbeat).total_seconds() < 150)  # pages check in every 60 s
            and a.status == AttemptStatus.IN_PROGRESS,
            "seconds_left": max(0, int((as_utc(a.deadline_at) - now).total_seconds()))
            if a.status == AttemptStatus.IN_PROGRESS else 0,
            "last_event": {"type": last_event.event_type, "at": as_utc(last_event.created_at)} if last_event else None,
            "ip_address": a.ip_address,
        })
    rows.sort(key=lambda r: (r["status"] != "in_progress", -r["violations"], r["roll_no"] or ""))
    recent = (db.query(ProctorEvent, Attempt, User).join(Attempt, ProctorEvent.attempt_id == Attempt.id)
              .join(User, Attempt.student_id == User.id)
              .filter(Attempt.exam_id == exam.id, ProctorEvent.counted.is_(True))
              .order_by(ProctorEvent.created_at.desc()).limit(50).all())
    return {
        "exam": exam_payload(exam, db),
        "attempts": rows,
        "recent_violations": [{"roll_no": u.roll_no, "name": u.name, "type": e.event_type,
                               "details": e.details, "at": as_utc(e.created_at)} for e, a, u in recent],
    }


@router.get("/exams/{exam_id}/similarity")
def code_similarity(exam_id: int, threshold: float = Query(85, ge=50, le=100),
                    college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    exam = get_exam(db, college_id, exam_id)
    return {"threshold": threshold, "pairs": engine.similarity_report(db, exam, threshold / 100)}


@router.get("/attempts/{attempt_id}")
def attempt_detail(attempt_id: int, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    a = get_attempt(db, college_id, attempt_id)
    items = {i.id: i for i in a.exam.items}
    mcq_answers = {m.item_id: m for m in a.mcq_answers}
    code_answers = {c.item_id: c for c in a.code_answers}
    questions = []
    for item_id in a.item_order:
        item = items.get(item_id)
        if not item:
            continue
        entry = {"item_id": item.id, "type": item.item_type.value, "section": item.section,
                 "marks": item.effective_marks}
        if item.item_type == ItemType.MCQ:
            ans = mcq_answers.get(item.id)
            entry.update({"question": item.mcq.question_text, "options": item.mcq.options,
                          "correct_options": item.mcq.correct_options,
                          "selected": ans.selected if ans else [], "is_correct": ans.is_correct if ans else None,
                          "marks_awarded": ans.marks_awarded if ans else 0})
        else:
            ans = code_answers.get(item.id)
            entry.update({"title": item.problem.title, "language": ans.language if ans else None,
                          "code": ans.code if ans else "", "passed_tests": ans.passed_tests if ans else 0,
                          "total_tests": ans.total_tests if ans else 0, "run_count": ans.run_count if ans else 0,
                          "marks_awarded": ans.marks_awarded if ans else 0})
        questions.append(entry)
    return {
        "attempt_id": a.id, "exam_title": a.exam.title, "status": a.status.value,
        "student": student_payload(a.student), "started_at": as_utc(a.started_at),
        "submitted_at": as_utc(a.submitted_at), "deadline_at": as_utc(a.deadline_at),
        "submit_reason": a.submit_reason, "total_score": a.total_score, "max_score": a.max_score,
        "mcq_score": a.mcq_score, "coding_score": a.coding_score, "violations": a.violation_count,
        "ip_address": a.ip_address, "user_agent": a.user_agent, "section_scores": _section_scores(a),
        "questions": questions,
        "events": [{"type": e.event_type, "details": e.details, "counted": e.counted,
                    "at": as_utc(e.created_at)} for e in a.events],
    }


@router.post("/attempts/{attempt_id}/force-submit")
def force_submit(attempt_id: int, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    a = get_attempt(db, college_id, attempt_id)
    if a.status != AttemptStatus.IN_PROGRESS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Attempt is already submitted")
    engine.finalize_attempt(db, a, AttemptStatus.AUTO_SUBMITTED, "admin_force_submit")
    return {"attempt_id": a.id, "status": a.status.value, "total_score": a.total_score}


class ExtendIn(BaseModel):
    minutes: int = Field(..., ge=1, le=240)


@router.post("/attempts/{attempt_id}/extend")
def extend_attempt(attempt_id: int, body: ExtendIn, college_id: int = Depends(scoped_college_id),
                   db: Session = Depends(get_db)):
    """Give a student extra time (e.g. after a power cut)."""
    from datetime import timedelta
    a = get_attempt(db, college_id, attempt_id)
    if a.status != AttemptStatus.IN_PROGRESS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Attempt is already submitted")
    a.deadline_at = as_utc(a.deadline_at) + timedelta(minutes=body.minutes)
    engine.record_event(db, a, "time_extended", f"+{body.minutes} min by admin")
    db.commit()
    return {"attempt_id": a.id, "deadline_at": as_utc(a.deadline_at)}


@router.post("/attempts/{attempt_id}/forgive-violations")
def forgive_violations(attempt_id: int, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    a = get_attempt(db, college_id, attempt_id)
    a.violation_count = 0
    engine.record_event(db, a, "violations_cleared", "by admin")
    db.commit()
    return {"attempt_id": a.id, "violations": 0}


@router.post("/attempts/bulk-forgive-violations")
def bulk_forgive_violations(body: BulkIds, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    attempts = db.query(Attempt).join(Exam).filter(Attempt.id.in_(body.ids), Exam.college_id == college_id).all()
    for a in attempts:
        a.violation_count = 0
        engine.record_event(db, a, "violations_cleared", "by admin (bulk)")
    db.commit()
    return {"updated": len(attempts)}


class ReopenIn(BaseModel):
    minutes: int = Field(10, ge=1, le=240, description="Extra time to give once reopened")


@router.post("/attempts/{attempt_id}/reopen")
def reopen_attempt(attempt_id: int, body: ReopenIn, college_id: int = Depends(scoped_college_id),
                   db: Session = Depends(get_db)):
    """Undo an auto-submit that was only triggered by hitting the violation limit, and give fresh time."""
    import secrets
    from datetime import timedelta
    a = get_attempt(db, college_id, attempt_id)
    if a.status == AttemptStatus.IN_PROGRESS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This attempt is still in progress")
    if a.submit_reason != "max_violations":
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Only an attempt that was auto-submitted for violations can be reopened")
    a.status = AttemptStatus.IN_PROGRESS
    a.violation_count = 0
    a.submitted_at = None
    a.submit_reason = None
    a.deadline_at = utcnow() + timedelta(minutes=body.minutes)
    a.session_nonce = secrets.token_urlsafe(24)
    engine.record_event(db, a, "reopened_by_admin", f"violations cleared, +{body.minutes} min")
    db.commit()
    return {"attempt_id": a.id, "status": a.status.value, "deadline_at": as_utc(a.deadline_at)}


@router.delete("/attempts/{attempt_id}")
def reset_attempt(attempt_id: int, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    """Delete an attempt so the student can take the exam again."""
    a = get_attempt(db, college_id, attempt_id)
    db.delete(a)
    db.commit()
    return {"deleted": attempt_id}


# ══════════════════════════════════════════════════════════════════════════
# Announcements
# ══════════════════════════════════════════════════════════════════════════

@router.get("/announcements")
def list_announcements(college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    rows = db.query(Announcement).filter(or_(Announcement.college_id == college_id,
                                             Announcement.college_id.is_(None))) \
        .order_by(Announcement.created_at.desc()).limit(100).all()
    return [{"id": a.id, "title": a.title, "body": a.body, "is_global": a.college_id is None,
             "created_at": a.created_at} for a in rows]


@router.post("/announcements", status_code=status.HTTP_201_CREATED)
def create_announcement(body: AnnouncementIn, all_colleges: bool = False, user: User = Depends(require_admin),
                        college_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    if user.role == Role.COLLEGE_ADMIN:
        target = user.college_id
    elif all_colleges:
        target = None
    else:
        if college_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pass college_id or all_colleges=true")
        target = college_id
    a = Announcement(college_id=target, created_by=user.id, title=body.title, body=body.body)
    db.add(a)
    db.commit()
    return {"id": a.id}


@router.delete("/announcements/{announcement_id}")
def delete_announcement(announcement_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    a = db.get(Announcement, announcement_id)
    if not a or (user.role == Role.COLLEGE_ADMIN and a.college_id != user.college_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Announcement not found")
    db.delete(a)
    db.commit()
    return {"deleted": announcement_id}


@router.post("/exams/{exam_id}/email-results")
def email_results(exam_id: int, college_id: int = Depends(scoped_college_id), db: Session = Depends(get_db)):
    """Email every finished student their score (and certificate note). Students without an email are skipped."""
    exam = get_exam(db, college_id, exam_id)
    require_feature(exam.college, "email_results")
    finished = engine.rank_attempts(db.query(Attempt).filter(Attempt.exam_id == exam.id).all())
    certs = has_feature(exam.college, "certificates")
    messages, skipped = [], 0
    for rank, a in enumerate(finished, start=1):
        if not a.student.email:
            skipped += 1
            continue
        pct = engine.percentage(a)
        passed = pct >= exam.pass_percentage
        text = (f"Hello {a.student.name},\n\n"
                f"Your result for {exam.title} ({exam.college.name}):\n\n"
                f"  Score: {a.total_score:g} / {a.max_score:g} ({pct:g}%)\n"
                f"  Rank: {rank} of {len(finished)}\n"
                f"  Result: {'Passed' if passed else 'Not passed'} (pass mark {exam.pass_percentage:g}%)\n")
        if certs and passed:
            text += "\nYour certificate is ready to download from your Reios dashboard.\n"
        text += "\nSign in to Reios to see section-wise scores.\n"
        text += "\n-- Reios, developed by Ratiio\n"
        messages.append((a.student.email, f"Your result: {exam.title}", text))
    if not messages:
        return {"sent": 0, "skipped": skipped, "failed": []}
    sent, failed = send_emails(messages)
    return {"sent": sent, "skipped": skipped, "failed": [{"email": e, "error": err} for e, err in failed]}
