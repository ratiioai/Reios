"""
Pydantic schemas for request/response validation
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from app.models import DifficultyLevel, TestStatus, Language


# Auth schemas
class AdminLoginRequest(BaseModel):
    username: str
    password: str


class TeamLoginRequest(BaseModel):
    team_name: str
    leader_phone: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_info: Dict[str, Any]


# Question schemas
class SampleTestCaseCreate(BaseModel):
    input_data: str
    expected_output: str
    explanation: Optional[str] = None
    order: int = 0


class HiddenTestCaseCreate(BaseModel):
    input_data: str
    expected_output: str
    order: int = 0


class QuestionCreate(BaseModel):
    title: str = Field(..., max_length=500)
    difficulty: DifficultyLevel
    prompt_markdown: str
    starter_code_python: Optional[str] = None
    starter_code_cpp: Optional[str] = None
    starter_code_java: Optional[str] = None
    starter_code_javascript: Optional[str] = None
    time_limit_seconds: int = 5
    memory_limit_mb: int = 256
    sample_test_cases: List[SampleTestCaseCreate]
    hidden_test_cases: List[HiddenTestCaseCreate]


class QuestionUpdate(BaseModel):
    title: Optional[str] = None
    prompt_markdown: Optional[str] = None
    starter_code_python: Optional[str] = None
    starter_code_cpp: Optional[str] = None
    starter_code_java: Optional[str] = None
    starter_code_javascript: Optional[str] = None
    time_limit_seconds: Optional[int] = None
    memory_limit_mb: Optional[int] = None
    is_active: Optional[bool] = None


class SampleTestCaseResponse(BaseModel):
    input_data: str
    expected_output: str
    explanation: Optional[str] = None

    class Config:
        from_attributes = True


class QuestionResponse(BaseModel):
    id: int
    title: str
    difficulty: DifficultyLevel
    marks: int
    prompt_markdown: str
    starter_code: Dict[str, Optional[str]]
    sample_test_cases: List[SampleTestCaseResponse]
    time_limit_seconds: int
    memory_limit_mb: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class QuestionListItem(BaseModel):
    id: int
    title: str
    difficulty: DifficultyLevel
    marks: int
    is_active: bool
    sample_test_cases_count: int
    hidden_test_cases_count: int
    created_at: datetime


# Team schemas
class TeamResponse(BaseModel):
    id: int
    team_name: str
    leader_name: str
    college: Optional[str]

    class Config:
        from_attributes = True


# Test configuration schemas
class TestConfigurationUpdate(BaseModel):
    test_open_at: Optional[datetime] = None
    test_close_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    synchronized_start: Optional[bool] = None
    global_start_time: Optional[datetime] = None
    allow_team_view_leaderboard: Optional[bool] = None
    leaderboard_published: Optional[bool] = None


class TestConfigurationResponse(BaseModel):
    test_open_at: Optional[datetime]
    test_close_at: Optional[datetime]
    duration_minutes: int
    synchronized_start: bool
    global_start_time: Optional[datetime]
    allow_team_view_leaderboard: bool
    leaderboard_published: bool


# Submission schemas
class CodeSubmitRequest(BaseModel):
    code: str
    language: Language


class SampleTestRunResult(BaseModel):
    test_case: int
    input_data: str
    expected_output: str
    actual_output: str
    passed: bool
    execution_time_ms: int
    error: Optional[str] = None


class CodeRunRequest(BaseModel):
    code: str
    language: Language
    custom_input: Optional[str] = ""
    question_id: Optional[int] = None


class CodeRunResponse(BaseModel):
    success: bool
    stdout: str
    stderr: str
    execution_time_ms: int
    error: Optional[str] = None
    sample_test_results: Optional[List[SampleTestRunResult]] = None
    ai_evaluation: Optional[str] = None
    ai_model: Optional[str] = None


class TestResultDetail(BaseModel):
    test_case: int
    passed: bool
    execution_time_ms: Optional[int]
    error: Optional[str] = None


class GradingResultResponse(BaseModel):
    submission_id: int
    status: str
    marks_awarded: int
    passed_tests: int
    total_tests: int
    execution_time_ms: Optional[int]
    memory_used_mb: Optional[float]
    test_results: Optional[List[TestResultDetail]]
    error_output: Optional[str]


class SubmissionResponse(BaseModel):
    submission_id: int
    status: str
    message: str
    estimated_grading_time_seconds: Optional[int] = None
    check_status_url: Optional[str] = None
    queue_position: Optional[int] = None


# Test session schemas
class TestStartResponse(BaseModel):
    test_started: bool
    started_at: datetime
    expires_at: datetime
    duration_minutes: int
    questions_count: int
    auto_submit_warning: str


class SprintStatusResponse(BaseModel):
    sprint_started: bool
    sprint_active: bool
    sprint_ended: bool
    global_start_time: Optional[datetime] = None
    test_close_at: Optional[datetime] = None
    time_remaining_seconds: int = 0
    duration_minutes: int = 120
    team_status: Optional[str] = None
    total_score: Optional[int] = 0
    solved_count: Optional[int] = 0
    message: Optional[str] = None


class SprintActionResponse(BaseModel):
    success: bool
    message: str
    global_start_time: Optional[datetime] = None
    test_close_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None


class TestStatusResponse(BaseModel):
    started_at: Optional[datetime]
    time_remaining_seconds: Optional[int]
    auto_submit_at: Optional[datetime]
    status: TestStatus
    total_score: Optional[int] = 0
    solved_count: Optional[int] = 0


class AssignedQuestionResponse(BaseModel):
    position: int
    question_id: int
    title: str
    difficulty: DifficultyLevel
    marks: int
    prompt_markdown: str
    starter_code: Dict[str, Optional[str]]
    sample_test_cases: List[SampleTestCaseResponse]
    time_limit_seconds: int
    memory_limit_mb: int
    submission_status: Optional[str] = None
    awarded_marks: Optional[int] = None
    saved_code: Optional[str] = None
    saved_language: Optional[str] = None


class QuestionsListResponse(BaseModel):
    questions: List[AssignedQuestionResponse]
    test_status: TestStatusResponse
    total_score: Optional[int] = 0
    solved_count: Optional[int] = 0


class TestSubmitResponse(BaseModel):
    test_submitted: bool
    submitted_at: datetime
    time_taken_seconds: int
    time_taken_formatted: str
    questions_submitted: int
    questions_pending_grade: int
    preliminary_score: int
    message: str


# Leaderboard schemas
class ScoreBreakdown(BaseModel):
    easy_score: int
    medium_score: int
    hard_score: int


class LeaderboardEntry(BaseModel):
    rank: int
    team_id: int
    team_name: str
    college_name: Optional[str] = None
    total_score: int
    time_taken_seconds: Optional[int] = None
    time_taken_formatted: Optional[str] = None
    last_submission_time: Optional[datetime] = None
    last_submission_formatted: Optional[str] = None
    score_breakdown: ScoreBreakdown
    questions_attempted: int
    questions_solved: int
    submitted_at: Optional[datetime] = None


class LeaderboardResponse(BaseModel):
    leaderboard: List[LeaderboardEntry]
    total_teams: int
    teams_submitted: int
    teams_in_progress: int
    teams_not_started: int


class TeamLeaderboardResponse(BaseModel):
    leaderboard_published: bool
    your_rank: Optional[int]
    your_score: Optional[int]
    top_10: List[LeaderboardEntry]


# Admin schemas
class CSVUploadResponse(BaseModel):
    success: bool
    teams_created: int
    teams_failed: int
    question_sets_assigned: int
    errors: List[Dict[str, Any]]
    summary: Dict[str, int]


class GradeOverrideRequest(BaseModel):
    marks_awarded: int
    reason: str


class GradeOverrideResponse(BaseModel):
    submission_id: int
    original_marks: int
    new_marks: int
    overridden_by: str
    overridden_at: datetime
    leaderboard_recalculated: bool


class TestStatusSummary(BaseModel):
    total_teams: int
    teams_not_started: int
    teams_in_progress: int
    teams_submitted: int
    teams_auto_submitted: int


class QueueStatsResponse(BaseModel):
    queue_depth: int
    grading_in_progress: int
    completed_today: int
    failed_today: int
    average_grading_time_seconds: float


# Proctoring Schemas
class ProctoringViolationRequest(BaseModel):
    violation_type: str = "fullscreen_exit"
    count: int = 1


class ProctoringViolationResponse(BaseModel):
    success: bool
    strike_count: int
    max_strikes: int = 3
    action_taken: str
    auto_submitted: bool
    message: str


class ProctoringAlertItem(BaseModel):
    id: int
    team_id: int
    team_name: str
    leader_phone: str
    violation_type: str
    strike_count: int
    action_taken: str
    timestamp: datetime

    class Config:
        from_attributes = True


class ProctoringAlertsListResponse(BaseModel):
    alerts: List[ProctoringAlertItem]
    total_violations: int


# AI Evaluation Schemas
class AIEvaluationRequest(BaseModel):
    question_id: int
    code: str
    language: str


class AIEvaluationResponse(BaseModel):
    success: bool
    model: Optional[str] = None
    review: Optional[str] = None
    error: Optional[str] = None

