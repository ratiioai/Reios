"""
Database models for the Reios module.
All tables are prefixed with reios_ so they live alongside the legacy team contest tables.
"""
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, Index, Integer,
    JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models import Base


class Role(str, PyEnum):
    SUPER_ADMIN = "super_admin"
    COLLEGE_ADMIN = "college_admin"
    STUDENT = "student"


class AttemptStatus(str, PyEnum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    AUTO_SUBMITTED = "auto_submitted"


class ItemType(str, PyEnum):
    MCQ = "mcq"
    CODING = "coding"


# Standard Reios sections; free text is also accepted
SECTIONS = ["Quantitative Aptitude", "Logical Reasoning", "Verbal Ability", "Technical", "Coding"]
DIFFICULTIES = ["easy", "medium", "hard"]
LANGUAGES = ["python", "cpp", "c", "java", "javascript"]
EXAM_TYPES = ["mcq", "coding", "mixed"]


class College(Base):
    __tablename__ = "reios_colleges"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(32), unique=True, nullable=False, index=True)  # used by students at login
    city = Column(String(120), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(32), nullable=True)
    max_students = Column(Integer, nullable=True)  # licence limit, None = unlimited
    max_exams = Column(Integer, nullable=True)  # exams the plan includes, None = unlimited
    access_until = Column(DateTime(timezone=True), nullable=True)  # account locks after this, None = no end
    org_type = Column(String(16), default="college", nullable=False)  # college | event
    features = Column(JSON, nullable=True)  # paid add-ons switched on for an event, see features.FEATURES
    logo = Column(Text, nullable=True)  # data: URL, shown when branding is on
    brand_color = Column(String(16), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="college")


class User(Base):
    __tablename__ = "reios_users"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(Enum(Role), nullable=False, index=True)
    college_id = Column(Integer, ForeignKey("reios_colleges.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, unique=True, index=True)
    roll_no = Column(String(64), nullable=True)  # students log in with college code + roll number
    phone = Column(String(32), nullable=True)
    branch = Column(String(64), nullable=True)
    section = Column(String(32), nullable=True)
    batch_year = Column(Integer, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    must_change_password = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    firebase_uid = Column(String(128), nullable=True, index=True)  # bound at first Firebase sign-in
    token_version = Column(Integer, default=0, nullable=False)  # bump to invalidate all tokens
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    college = relationship("College", back_populates="users")

    __table_args__ = (
        UniqueConstraint("college_id", "roll_no", name="uq_reios_college_roll"),
    )


class MCQQuestion(Base):
    __tablename__ = "reios_mcq_questions"

    id = Column(Integer, primary_key=True, index=True)
    college_id = Column(Integer, ForeignKey("reios_colleges.id"), nullable=True, index=True)  # None = global bank
    created_by = Column(Integer, ForeignKey("reios_users.id"), nullable=True)
    section = Column(String(64), nullable=False, index=True)
    topic = Column(String(128), nullable=True)
    difficulty = Column(String(16), default="medium", nullable=False)
    question_text = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)  # list[str]
    correct_options = Column(JSON, nullable=False)  # list[int], indices into options
    is_multi = Column(Boolean, default=False, nullable=False)
    explanation = Column(Text, nullable=True)
    marks = Column(Float, default=1.0, nullable=False)
    negative_marks = Column(Float, default=0.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CodingProblem(Base):
    __tablename__ = "reios_coding_problems"

    id = Column(Integer, primary_key=True, index=True)
    college_id = Column(Integer, ForeignKey("reios_colleges.id"), nullable=True, index=True)  # None = global bank
    created_by = Column(Integer, ForeignKey("reios_users.id"), nullable=True)
    title = Column(String(255), nullable=False)
    difficulty = Column(String(16), default="medium", nullable=False)
    statement = Column(Text, nullable=False)  # markdown
    input_format = Column(Text, nullable=True)
    output_format = Column(Text, nullable=True)
    constraints = Column(Text, nullable=True)
    sample_tests = Column(JSON, nullable=False, default=list)  # [{input, output, explanation}]
    hidden_tests = Column(JSON, nullable=False, default=list)  # [{input, output}]
    starter_code = Column(JSON, nullable=True)  # {language: code}
    marks = Column(Float, default=10.0, nullable=False)
    time_limit_seconds = Column(Integer, default=5, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Exam(Base):
    __tablename__ = "reios_exams"

    id = Column(Integer, primary_key=True, index=True)
    college_id = Column(Integer, ForeignKey("reios_colleges.id"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("reios_users.id"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    instructions = Column(Text, nullable=True)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, nullable=False, default=60)
    is_published = Column(Boolean, default=False, nullable=False)
    # Audience filters: comma-separated, empty = everyone in the college
    branch_filter = Column(String(255), nullable=True)
    batch_filter = Column(String(255), nullable=True)
    section_filter = Column(String(255), nullable=True)
    shuffle_questions = Column(Boolean, default=True, nullable=False)
    shuffle_options = Column(Boolean, default=True, nullable=False)
    negative_marking = Column(Boolean, default=False, nullable=False)
    allowed_languages = Column(JSON, nullable=True)  # None = all
    # Anti-cheat
    require_fullscreen = Column(Boolean, default=True, nullable=False)
    block_copy_paste = Column(Boolean, default=True, nullable=False)
    max_violations = Column(Integer, default=3, nullable=False)  # auto-submit when reached
    # Results
    show_results = Column(Boolean, default=True, nullable=False)
    show_answers = Column(Boolean, default=False, nullable=False)
    pass_percentage = Column(Float, default=40.0, nullable=False)
    show_leaderboard = Column(Boolean, default=False, nullable=False)
    # mcq | coding | mixed — decides which kinds of questions the paper may hold
    exam_type = Column(String(16), default="mixed", nullable=False)
    # Keep sets rotated over students in roll order (1..N, then repeat) whenever sets change
    auto_assign_sets = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    college = relationship("College")
    items = relationship("ExamItem", back_populates="exam", cascade="all, delete-orphan",
                         order_by="ExamItem.order", lazy="selectin")
    sets = relationship("QuestionSet", back_populates="exam", cascade="all, delete-orphan",
                        order_by="QuestionSet.id", lazy="selectin")


class QuestionSet(Base):
    """One uploaded paper variant. Each student sits the common items plus exactly one set."""
    __tablename__ = "reios_question_sets"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("reios_exams.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(64), nullable=False)
    source_filename = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    exam = relationship("Exam", back_populates="sets")

    __table_args__ = (UniqueConstraint("exam_id", "name", name="uq_reios_set_name"),)


class SetAssignment(Base):
    __tablename__ = "reios_set_assignments"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("reios_exams.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("reios_users.id"), nullable=False, index=True)
    set_id = Column(Integer, ForeignKey("reios_question_sets.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (UniqueConstraint("exam_id", "student_id", name="uq_reios_set_assignment"),)


class ExamItem(Base):
    __tablename__ = "reios_exam_items"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("reios_exams.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type = Column(Enum(ItemType), nullable=False)
    mcq_id = Column(Integer, ForeignKey("reios_mcq_questions.id"), nullable=True)
    problem_id = Column(Integer, ForeignKey("reios_coding_problems.id"), nullable=True)
    section = Column(String(64), nullable=False)
    marks = Column(Float, nullable=True)  # None = use the question's own marks
    order = Column(Integer, default=0, nullable=False)
    # None = common to every student; otherwise only students sitting this set see it
    set_id = Column(Integer, ForeignKey("reios_question_sets.id", ondelete="CASCADE"), nullable=True, index=True)

    exam = relationship("Exam", back_populates="items")
    mcq = relationship("MCQQuestion", lazy="selectin")
    problem = relationship("CodingProblem", lazy="selectin")

    @property
    def effective_marks(self) -> float:
        if self.marks is not None:
            return self.marks
        source = self.mcq if self.item_type == ItemType.MCQ else self.problem
        return source.marks if source else 0.0


class Attempt(Base):
    __tablename__ = "reios_attempts"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("reios_exams.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("reios_users.id"), nullable=False, index=True)
    status = Column(Enum(AttemptStatus), default=AttemptStatus.IN_PROGRESS, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    deadline_at = Column(DateTime(timezone=True), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    set_id = Column(Integer, ForeignKey("reios_question_sets.id", ondelete="SET NULL"), nullable=True)
    item_order = Column(JSON, nullable=False)  # list[item_id] in the order this student sees them
    option_order = Column(JSON, nullable=True)  # {item_id: [original option indices]}
    session_nonce = Column(String(64), nullable=False)  # only one browser tab may hold the attempt
    mcq_score = Column(Float, default=0.0, nullable=False)
    coding_score = Column(Float, default=0.0, nullable=False)
    total_score = Column(Float, default=0.0, nullable=False)
    max_score = Column(Float, default=0.0, nullable=False)
    violation_count = Column(Integer, default=0, nullable=False)
    submit_reason = Column(String(64), nullable=True)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)

    exam = relationship("Exam")
    student = relationship("User")
    mcq_answers = relationship("MCQAnswer", cascade="all, delete-orphan")
    code_answers = relationship("CodeAnswer", cascade="all, delete-orphan")
    events = relationship("ProctorEvent", cascade="all, delete-orphan", order_by="ProctorEvent.created_at")

    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", name="uq_reios_exam_student"),
    )


class MCQAnswer(Base):
    __tablename__ = "reios_mcq_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("reios_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("reios_exam_items.id", ondelete="CASCADE"), nullable=False)
    selected = Column(JSON, nullable=False, default=list)  # list[int] original option indices
    marked_for_review = Column(Boolean, default=False, nullable=False)
    is_correct = Column(Boolean, nullable=True)
    marks_awarded = Column(Float, default=0.0, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("attempt_id", "item_id", name="uq_reios_mcq_answer"),)


class CodeAnswer(Base):
    __tablename__ = "reios_code_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("reios_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("reios_exam_items.id", ondelete="CASCADE"), nullable=False)
    language = Column(String(16), nullable=False)
    code = Column(Text, nullable=False, default="")
    graded_code_hash = Column(String(64), nullable=True)  # hash of the code last graded
    passed_tests = Column(Integer, default=0, nullable=False)
    total_tests = Column(Integer, default=0, nullable=False)
    marks_awarded = Column(Float, default=0.0, nullable=False)
    run_count = Column(Integer, default=0, nullable=False)
    graded_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("attempt_id", "item_id", name="uq_reios_code_answer"),)


class ProctorEvent(Base):
    __tablename__ = "reios_proctor_events"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("reios_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    details = Column(String(500), nullable=True)
    counted = Column(Boolean, default=True, nullable=False)  # counts toward max_violations
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class Announcement(Base):
    __tablename__ = "reios_announcements"

    id = Column(Integer, primary_key=True, index=True)
    college_id = Column(Integer, ForeignKey("reios_colleges.id"), nullable=True, index=True)  # None = all colleges
    created_by = Column(Integer, ForeignKey("reios_users.id"), nullable=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


Index("idx_reios_attempt_exam_status", Attempt.exam_id, Attempt.status)
