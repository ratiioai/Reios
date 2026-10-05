"""
Database models for Coding Test Platform
All models use SQLAlchemy ORM
"""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, 
    String, Text, Float, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


# Enums
class DifficultyLevel(str, PyEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class TestStatus(str, PyEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    AUTO_SUBMITTED = "auto_submitted"


class Language(str, PyEnum):
    PYTHON = "python"
    CPP = "cpp"
    JAVA = "java"
    JAVASCRIPT = "javascript"


# Models
class Admin(Base):
    """Admin users who manage the platform"""
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    audit_logs = relationship("AuditLog", back_populates="admin")


class Team(Base):
    """Teams participating in the test"""
    __tablename__ = "teams"
    
    id = Column(Integer, primary_key=True, index=True)
    team_name = Column(String(255), unique=True, nullable=False, index=True)
    leader_name = Column(String(255), nullable=False)
    leader_phone_hash = Column(String(255), nullable=False)  # Hashed phone number
    member_2 = Column(String(255), nullable=True)
    member_3 = Column(String(255), nullable=True)
    member_4 = Column(String(255), nullable=True)
    college = Column(String(255), nullable=True)
    csv_row_ref = Column(Integer, nullable=True)  # Reference to CSV row number
    is_active = Column(Boolean, default=True, nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    test_session = relationship("TestSession", back_populates="team", uselist=False)
    question_assignments = relationship("TeamQuestionAssignment", back_populates="team")
    submissions = relationship("Submission", back_populates="team")


class Question(Base):
    """Master question bank"""
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    difficulty = Column(Enum(DifficultyLevel), nullable=False, index=True)
    prompt_markdown = Column(Text, nullable=False)
    starter_code_python = Column(Text, nullable=True)
    starter_code_cpp = Column(Text, nullable=True)
    starter_code_java = Column(Text, nullable=True)
    starter_code_javascript = Column(Text, nullable=True)
    time_limit_seconds = Column(Integer, default=5, nullable=False)
    memory_limit_mb = Column(Integer, default=256, nullable=False)
    marks = Column(Integer, nullable=False)  # 5, 10, or 20 based on difficulty
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    sample_test_cases = relationship("SampleTestCase", back_populates="question", cascade="all, delete-orphan")
    hidden_test_cases = relationship("HiddenTestCase", back_populates="question", cascade="all, delete-orphan")
    team_assignments = relationship("TeamQuestionAssignment", back_populates="question")


class SampleTestCase(Base):
    """Visible test cases shown to teams"""
    __tablename__ = "sample_test_cases"
    
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    input_data = Column(Text, nullable=False)
    expected_output = Column(Text, nullable=False)
    explanation = Column(Text, nullable=True)
    order = Column(Integer, default=0, nullable=False)
    
    # Relationships
    question = relationship("Question", back_populates="sample_test_cases")


class HiddenTestCase(Base):
    """Hidden test cases for grading (never shown to teams)"""
    __tablename__ = "hidden_test_cases"
    
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    input_data = Column(Text, nullable=False)
    expected_output = Column(Text, nullable=False)
    order = Column(Integer, default=0, nullable=False)
    
    # Relationships
    question = relationship("Question", back_populates="hidden_test_cases")


class TestSession(Base):
    """Records when a team starts and submits their test"""
    __tablename__ = "test_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), unique=True, nullable=False, index=True)
    test_started_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    auto_submitted = Column(Boolean, default=False, nullable=False)
    status = Column(Enum(TestStatus), default=TestStatus.NOT_STARTED, nullable=False, index=True)
    time_taken_seconds = Column(Integer, nullable=True)  # submitted_at - test_started_at
    total_score = Column(Integer, default=0, nullable=False)
    easy_score = Column(Integer, default=0, nullable=False)
    medium_score = Column(Integer, default=0, nullable=False)
    hard_score = Column(Integer, default=0, nullable=False)
    rank = Column(Integer, nullable=True, index=True)
    
    # Relationships
    team = relationship("Team", back_populates="test_session")


class TeamQuestionAssignment(Base):
    """Tracks which 25 questions each team gets"""
    __tablename__ = "team_question_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    position = Column(Integer, nullable=False)  # 1-25, order in the test
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    team = relationship("Team", back_populates="question_assignments")
    question = relationship("Question", back_populates="team_assignments")
    
    __table_args__ = (
        UniqueConstraint('team_id', 'question_id', name='uq_team_question'),
        UniqueConstraint('team_id', 'position', name='uq_team_position'),
        Index('idx_team_question_lookup', 'team_id', 'question_id'),
    )


class UsedQuestionSet(Base):
    """Tracks used question set hashes to ensure uniqueness"""
    __tablename__ = "used_question_sets"
    
    id = Column(Integer, primary_key=True, index=True)
    set_hash = Column(String(64), unique=True, nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Submission(Base):
    """Code submissions for each question"""
    __tablename__ = "submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    code = Column(Text, nullable=False)
    language = Column(Enum(Language), nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    is_final = Column(Boolean, default=False, nullable=False)  # True when team clicks "Submit Answer"
    
    # Relationships
    team = relationship("Team", back_populates="submissions")
    grading_result = relationship("GradingResult", back_populates="submission", uselist=False)
    
    __table_args__ = (
        Index('idx_team_question_submission', 'team_id', 'question_id'),
    )


class GradingResult(Base):
    """Auto-grading results for submissions"""
    __tablename__ = "grading_results"
    
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), unique=True, nullable=False, index=True)
    marks_awarded = Column(Integer, default=0, nullable=False)
    passed_hidden_tests = Column(Integer, default=0, nullable=False)
    total_hidden_tests = Column(Integer, nullable=False)
    test_results = Column(JSON, nullable=True)  # Detailed per-test-case results
    error_output = Column(Text, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    memory_used_mb = Column(Float, nullable=True)
    auto_graded_at = Column(DateTime(timezone=True), server_default=func.now())
    overridden_by_admin_id = Column(Integer, ForeignKey("admins.id"), nullable=True)
    override_reason = Column(Text, nullable=True)
    overridden_at = Column(DateTime(timezone=True), nullable=True)
    original_marks = Column(Integer, nullable=True)  # Marks before override
    
    # Relationships
    submission = relationship("Submission", back_populates="grading_result")
    overridden_by = relationship("Admin")


class TestConfiguration(Base):
    """Global test configuration"""
    __tablename__ = "test_configuration"
    
    id = Column(Integer, primary_key=True)
    test_open_at = Column(DateTime(timezone=True), nullable=True)
    test_close_at = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, default=120, nullable=False)
    synchronized_start = Column(Boolean, default=True, nullable=False)
    global_start_time = Column(DateTime(timezone=True), nullable=True)
    allow_team_view_leaderboard = Column(Boolean, default=False, nullable=False)
    leaderboard_published = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AuditLog(Base):
    """Audit trail of all admin actions"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id"), nullable=False, index=True)
    action = Column(String(100), nullable=False)  # e.g., "grade_override", "csv_upload", "question_edit"
    object_type = Column(String(50), nullable=False)  # e.g., "submission", "team", "question"
    object_id = Column(Integer, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    admin = relationship("Admin", back_populates="audit_logs")


class ProctoringViolation(Base):
    """Audit log of participant anti-cheat violations and fullscreen strikes"""
    __tablename__ = "proctoring_violations"
    
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    team_name = Column(String(100), nullable=False)
    leader_phone = Column(String(20), nullable=False)
    violation_type = Column(String(50), nullable=False)  # "fullscreen_exit", "tab_switch"
    strike_count = Column(Integer, nullable=False)  # 1, 2, 3
    action_taken = Column(String(100), nullable=False)  # "warning_1", "warning_2", "auto_submitted"
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    team = relationship("Team")


# Indexes for performance
Index('idx_team_session_status', TestSession.team_id, TestSession.status)
Index('idx_submission_team_final', Submission.team_id, Submission.is_final)
Index('idx_grading_submission', GradingResult.submission_id)
Index('idx_audit_timestamp', AuditLog.timestamp.desc())
Index('idx_proctoring_timestamp', ProctoringViolation.timestamp.desc())
