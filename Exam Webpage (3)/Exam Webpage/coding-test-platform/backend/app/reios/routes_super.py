"""
Super admin endpoints: colleges, college admins and platform-wide stats.
"""
import re
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import get_db
from app.reios import engine
from app.reios.models import (
    Announcement, Attempt, AttemptStatus, CodeAnswer, CodingProblem, College, Exam, ExamItem, MCQAnswer,
    MCQQuestion, ProctorEvent, QuestionSet, Role, SetAssignment, User,
)
from app.reios.features import FEATURES, check_logo, clean_features
from app.reios.security import as_utc, generate_password, require_super_admin, utcnow

router = APIRouter(prefix="/api/reios/super", tags=["Reios Super Admin"])

CODE_RE = re.compile(r"^[A-Za-z0-9_-]{2,32}$")


class CollegeIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    code: str = Field(..., min_length=2, max_length=32)
    city: Optional[str] = Field(None, max_length=120)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=32)
    max_students: Optional[int] = Field(None, ge=1)
    max_exams: Optional[int] = Field(None, ge=1)
    access_until: Optional[datetime] = None
    org_type: str = Field("college", pattern="^(college|event)$")
    features: List[str] = []
    logo: Optional[str] = None
    brand_color: Optional[str] = Field(None, pattern="^#[0-9a-fA-F]{6}$")
    organizer: Optional[str] = Field(None, max_length=255)
    event_starts_at: Optional[datetime] = None
    single_login: bool = False


class CollegeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    city: Optional[str] = Field(None, max_length=120)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=32)
    max_students: Optional[int] = Field(None, ge=1)
    max_exams: Optional[int] = Field(None, ge=1)
    access_until: Optional[datetime] = None
    org_type: Optional[str] = Field(None, pattern="^(college|event)$")
    features: Optional[List[str]] = None
    logo: Optional[str] = None
    brand_color: Optional[str] = Field(None, pattern="^#[0-9a-fA-F]{6}$")
    organizer: Optional[str] = Field(None, max_length=255)
    event_starts_at: Optional[datetime] = None
    single_login: Optional[bool] = None
    is_active: Optional[bool] = None


class CollegeAdminIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=32)
    password: Optional[str] = Field(None, min_length=8, max_length=128)


class CollegeAdminUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=32)
    is_active: Optional[bool] = None


def clean_text(value: Optional[str]) -> Optional[str]:
    return (value or "").strip() or None


def check_event_dates(college: College) -> None:
    start, end = as_utc(college.event_starts_at), as_utc(college.access_until)
    if start and end and end < start:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The event can't end before it starts")


def college_payload(college: College, db: Session) -> dict:
    student_count = db.query(func.count(User.id)).filter(
        User.college_id == college.id, User.role == Role.STUDENT).scalar()
    admin_count = db.query(func.count(User.id)).filter(
        User.college_id == college.id, User.role == Role.COLLEGE_ADMIN).scalar()
    exam_count = db.query(func.count(Exam.id)).filter(Exam.college_id == college.id).scalar()
    return {
        "id": college.id, "name": college.name, "code": college.code, "city": college.city,
        "contact_email": college.contact_email, "contact_phone": college.contact_phone,
        "max_students": college.max_students, "is_active": college.is_active,
        "max_exams": college.max_exams, "access_until": as_utc(college.access_until),
        "expired": bool(college.access_until and as_utc(college.access_until) < utcnow()),
        "org_type": college.org_type, "features": college.features or [],
        "organizer": college.organizer, "event_starts_at": as_utc(college.event_starts_at),
        "single_login": college.single_login,
        "logo": college.logo, "brand_color": college.brand_color,
        "created_at": college.created_at,
        "student_count": student_count, "admin_count": admin_count, "exam_count": exam_count,
    }


def admin_payload(user: User) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "phone": user.phone,
            "is_active": user.is_active, "last_login_at": user.last_login_at,
            "must_change_password": user.must_change_password, "created_at": user.created_at}


def get_college_or_404(db: Session, college_id: int) -> College:
    college = db.get(College, college_id)
    if not college:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "College not found")
    return college


@router.get("/stats")
def platform_stats(db: Session = Depends(get_db), _=Depends(require_super_admin)):
    def count(model, *filters):
        return db.query(func.count(model.id)).filter(*filters).scalar()
    return {
        "colleges": count(College),
        "active_colleges": count(College, College.is_active.is_(True)),
        "college_admins": count(User, User.role == Role.COLLEGE_ADMIN),
        "students": count(User, User.role == Role.STUDENT),
        "exams": count(Exam),
        "attempts": count(Attempt),
        "live_attempts": count(Attempt, Attempt.status == AttemptStatus.IN_PROGRESS),
        "global_mcqs": count(MCQQuestion, MCQQuestion.college_id.is_(None), MCQQuestion.is_active.is_(True)),
        "global_problems": count(CodingProblem, CodingProblem.college_id.is_(None),
                                 CodingProblem.is_active.is_(True)),
    }


@router.get("/colleges")
def list_colleges(db: Session = Depends(get_db), _=Depends(require_super_admin)):
    colleges = db.query(College).order_by(College.name).all()
    return [college_payload(c, db) for c in colleges]


@router.post("/colleges", status_code=status.HTTP_201_CREATED)
def create_college(body: CollegeIn, db: Session = Depends(get_db), _=Depends(require_super_admin)):
    code = body.code.strip().upper()
    if not CODE_RE.match(code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The code may only contain letters, digits, - and _")
    if db.query(College).filter(func.upper(College.code) == code).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"The code {code} is already in use")
    college = College(name=body.name.strip(), code=code, city=body.city, contact_email=body.contact_email,
                      contact_phone=body.contact_phone, max_students=body.max_students,
                      max_exams=body.max_exams, access_until=body.access_until, org_type=body.org_type,
                      features=clean_features(body.org_type, body.features), logo=check_logo(body.logo),
                      brand_color=body.brand_color, organizer=clean_text(body.organizer),
                      event_starts_at=body.event_starts_at if body.org_type == "event" else None,
                      single_login=body.single_login)
    check_event_dates(college)
    db.add(college)
    db.commit()
    db.refresh(college)
    return college_payload(college, db)


@router.patch("/colleges/{college_id}")
def update_college(college_id: int, body: CollegeUpdate, db: Session = Depends(get_db),
                   _=Depends(require_super_admin)):
    college = get_college_or_404(db, college_id)
    data = body.model_dump(exclude_unset=True)
    if "logo" in data:
        data["logo"] = check_logo(data["logo"])
    for field, value in data.items():
        setattr(college, field, value)
    college.features = clean_features(college.org_type, college.features)
    if "organizer" in data:
        college.organizer = clean_text(college.organizer)
    if college.org_type != "event":
        college.organizer, college.event_starts_at = None, None
    check_event_dates(college)
    db.commit()
    return college_payload(college, db)


@router.delete("/colleges/{college_id}")
def delete_college(college_id: int, confirm: str = Query(..., description="The college's code, typed to confirm"),
                   force: bool = Query(False, description="Also end any exam attempts still in progress"),
                   db: Session = Depends(get_db), _=Depends(require_super_admin)):
    """
    Permanently remove a college and everything it owns: admins, students, exams, sets, attempts,
    answers, proctoring logs, announcements and its own question bank. Global questions are kept.
    """
    college = get_college_or_404(db, college_id)
    if confirm.strip().upper() != college.code.upper():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Type the college code ({college.code}) to confirm")
    exam_ids = select(Exam.id).where(Exam.college_id == college.id)
    writing = db.query(Attempt).filter(Attempt.exam_id.in_(exam_ids),
                                       Attempt.status == AttemptStatus.IN_PROGRESS).count()
    if writing and not force:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{writing} students are writing an exam right now. End the exam, or delete again "
                            "to also end their attempts and erase those results, instead of deleting it")
    if writing:
        for (exam_id,) in db.query(Exam.id).filter(Exam.college_id == college.id).all():
            engine.force_submit_in_progress(db, exam_id, "deleted_by_super_admin")

    attempt_ids = select(Attempt.id).where(Attempt.exam_id.in_(exam_ids))
    counts = {
        "deleted": college.code,
        "students": db.query(User).filter(User.college_id == college.id, User.role == Role.STUDENT).count(),
        "exams": db.query(Exam).filter(Exam.college_id == college.id).count(),
        "attempts": db.query(Attempt).filter(Attempt.exam_id.in_(exam_ids)).count(),
    }
    gone = dict(synchronize_session=False)
    for model in (MCQAnswer, CodeAnswer, ProctorEvent):
        db.query(model).filter(model.attempt_id.in_(attempt_ids)).delete(**gone)
    db.query(Attempt).filter(Attempt.exam_id.in_(exam_ids)).delete(**gone)
    db.query(SetAssignment).filter(SetAssignment.exam_id.in_(exam_ids)).delete(**gone)
    db.query(ExamItem).filter(ExamItem.exam_id.in_(exam_ids)).delete(**gone)
    db.query(QuestionSet).filter(QuestionSet.exam_id.in_(exam_ids)).delete(**gone)
    db.query(Exam).filter(Exam.college_id == college.id).delete(**gone)
    # The college's own bank, which includes every question uploaded in its sets
    db.query(MCQQuestion).filter(MCQQuestion.college_id == college.id).delete(**gone)
    db.query(CodingProblem).filter(CodingProblem.college_id == college.id).delete(**gone)
    db.query(Announcement).filter(Announcement.college_id == college.id).delete(**gone)
    db.query(User).filter(User.college_id == college.id).delete(**gone)
    db.query(College).filter(College.id == college.id).delete(**gone)
    db.commit()
    return counts


@router.get("/colleges/{college_id}/admins")
def list_college_admins(college_id: int, db: Session = Depends(get_db), _=Depends(require_super_admin)):
    get_college_or_404(db, college_id)
    admins = db.query(User).filter(User.college_id == college_id, User.role == Role.COLLEGE_ADMIN) \
        .order_by(User.name).all()
    return [admin_payload(a) for a in admins]


@router.post("/colleges/{college_id}/admins", status_code=status.HTTP_201_CREATED)
def create_college_admin(college_id: int, body: CollegeAdminIn, db: Session = Depends(get_db),
                         _=Depends(require_super_admin)):
    get_college_or_404(db, college_id)
    email = body.email.lower()
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists")
    password = body.password or generate_password()
    admin = User(role=Role.COLLEGE_ADMIN, college_id=college_id, name=body.name.strip(), email=email,
                 phone=body.phone, hashed_password=hash_password(password), must_change_password=True)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return {**admin_payload(admin), "temporary_password": password}


@router.patch("/admins/{admin_id}")
def update_college_admin(admin_id: int, body: CollegeAdminUpdate, db: Session = Depends(get_db),
                         _=Depends(require_super_admin)):
    admin = db.get(User, admin_id)
    if not admin or admin.role != Role.COLLEGE_ADMIN:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "College admin not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(admin, field, value)
    if body.is_active is False:
        admin.token_version += 1
    db.commit()
    return admin_payload(admin)


@router.post("/admins/{admin_id}/reset-password")
def reset_college_admin_password(admin_id: int, db: Session = Depends(get_db), _=Depends(require_super_admin)):
    admin = db.get(User, admin_id)
    if not admin or admin.role != Role.COLLEGE_ADMIN:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "College admin not found")
    password = generate_password()
    admin.hashed_password = hash_password(password)
    admin.must_change_password = True
    admin.token_version += 1
    admin.locked_until = None
    db.commit()
    return {"id": admin.id, "temporary_password": password}


@router.get("/features")
def list_features(_=Depends(require_super_admin)):
    return [{"key": k, "label": v} for k, v in FEATURES.items()]


@router.get("/usage")
def usage_report(month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"), db: Session = Depends(get_db),
                 _=Depends(require_super_admin)):
    """Per organization: students, exams created and attempts taken in the month (UTC). Default: this month."""
    now = utcnow()
    year, mon = (int(x) for x in month.split("-")) if month else (now.year, now.month)
    start = datetime(year, mon, 1, tzinfo=timezone.utc)
    end = datetime(year + (mon == 12), mon % 12 + 1, 1, tzinfo=timezone.utc)
    rows = []
    for c in db.query(College).order_by(College.name).all():
        exam_ids = select(Exam.id).where(Exam.college_id == c.id)
        rows.append({
            "id": c.id, "name": c.name, "code": c.code, "org_type": c.org_type, "features": c.features or [],
            "is_active": c.is_active, "expired": bool(c.access_until and as_utc(c.access_until) < now),
            "students": db.query(User).filter(User.college_id == c.id, User.role == Role.STUDENT).count(),
            "exams_total": db.query(Exam).filter(Exam.college_id == c.id).count(),
            "max_exams": c.max_exams,
            "exams_created": db.query(Exam).filter(Exam.college_id == c.id, Exam.created_at >= start,
                                                   Exam.created_at < end).count(),
            "attempts": db.query(Attempt).filter(Attempt.exam_id.in_(exam_ids), Attempt.started_at >= start,
                                                 Attempt.started_at < end).count(),
        })
    return {"month": f"{year:04d}-{mon:02d}", "organizations": rows,
            "totals": {k: sum(r[k] for r in rows) for k in ("students", "exams_created", "attempts")}}
