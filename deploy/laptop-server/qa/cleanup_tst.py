"""
Removes everything testing created in the TST test event (rows created after CUTOFF), and proves the
real event (TECHSPRINT) wasn't touched. Usage: python cleanup_tst.py [--dry-run]
"""
import sys
from datetime import datetime, timezone

from app.database import SessionLocal
from app.reios.models import (Announcement, Attempt, College, Exam, ExamItem, MCQQuestion, Role,
                              SetAssignment, User)

CUTOFF = datetime(2026, 10, 9, 11, 20, tzinfo=timezone.utc)   # 16:50 IST, when this test session began
DRY = "--dry-run" in sys.argv
db = SessionLocal()
tst = db.query(College).filter(College.code == "TST").one()
sts = db.query(College).filter(College.code == "STS").one()

exams = db.query(Exam).filter(Exam.college_id == tst.id, Exam.created_at >= CUTOFF).all()
students = db.query(User).filter(User.college_id == tst.id, User.role == Role.STUDENT, User.created_at >= CUTOFF).all()
mcqs = db.query(MCQQuestion).filter(MCQQuestion.college_id == tst.id, MCQQuestion.created_at >= CUTOFF).all()
anns = db.query(Announcement).filter(Announcement.college_id == tst.id, Announcement.created_at >= CUTOFF).all()
print(f"TST test data to remove: {len(exams)} exams, {len(students)} teams, {len(mcqs)} questions, {len(anns)} announcements")

leaked = db.query(User).filter(User.college_id == sts.id, User.roll_no.like("QA-%")).count() + \
         db.query(Exam).filter(Exam.college_id == sts.id, Exam.title.like("%QA%") | Exam.title.like("LOAD TEST%")).count()
print("Test data found in TECHSPRINT:", leaked)

if not DRY:
    exam_ids = [e.id for e in exams]
    student_ids = [s.id for s in students]
    for a in db.query(Attempt).filter(Attempt.exam_id.in_(exam_ids) | Attempt.student_id.in_(student_ids)).all():
        db.delete(a)  # answers and proctoring events cascade
    db.flush()
    db.query(SetAssignment).filter(SetAssignment.exam_id.in_(exam_ids) | SetAssignment.student_id.in_(student_ids)).delete(
        synchronize_session=False)
    for e in exams:
        db.delete(e)  # items and sets cascade
    db.flush()
    still_used = {m for (m,) in db.query(ExamItem.mcq_id).filter(ExamItem.mcq_id.in_([q.id for q in mcqs])).all()}
    for q in mcqs:
        if q.id not in still_used:
            db.delete(q)
    for s in students:
        db.delete(s)
    for a in anns:
        db.delete(a)
    db.commit()
    print("Removed.")
left = (db.query(Exam).filter(Exam.college_id == tst.id).count(),
        db.query(User).filter(User.college_id == tst.id, User.role == Role.STUDENT).count())
print(f"TST now has {left[0]} exams and {left[1]} teams")
db.close()
