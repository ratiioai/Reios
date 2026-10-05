"""
Team routes for taking the test
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List
from datetime import datetime, timedelta

from app.auth import get_current_team
from app.database import get_db
from app.models import (
    Team, TestSession, TestConfiguration, TeamQuestionAssignment,
    Question, SampleTestCase, Submission, GradingResult,
    TestStatus, Language, ProctoringViolation
)
from app.schemas import (
    TestStartResponse, TestStatusResponse, QuestionsListResponse,
    AssignedQuestionResponse, SampleTestCaseResponse,
    CodeSubmitRequest, SubmissionResponse, GradingResultResponse,
    TestSubmitResponse, TestResultDetail,
    CodeRunRequest, CodeRunResponse, SampleTestRunResult,
    LeaderboardResponse, LeaderboardEntry, ScoreBreakdown,
    ProctoringViolationRequest, ProctoringViolationResponse,
    SprintStatusResponse, AIEvaluationRequest, AIEvaluationResponse
)
from app.grading_queue import GradingQueue
from app.ai_evaluator import AICodeEvaluator
from app.config import settings
import logging

from app.presence import record_team_heartbeat, clear_team_presence

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("/sprint/status", response_model=SprintStatusResponse)
async def get_team_sprint_status(
    current_team: Team = Depends(get_current_team),
    db: Session = Depends(get_db)
):
    """Check if the administrator has started the synchronized sprint"""
    # Track live online presence
    record_team_heartbeat(current_team.id)
    
    config = db.query(TestConfiguration).first()
    now = datetime.utcnow()
    
    session = db.query(TestSession).filter(TestSession.team_id == current_team.id).first()
    if not session:
        session = TestSession(team_id=current_team.id)
        db.add(session)
        db.commit()
        db.refresh(session)
    
    solved_count = db.query(Submission).join(GradingResult).filter(
        Submission.team_id == current_team.id,
        Submission.is_final == True,
        GradingResult.marks_awarded > 0
    ).count()
    
    if not config or not config.global_start_time:
        return SprintStatusResponse(
            sprint_started=False,
            sprint_active=False,
            sprint_ended=False,
            time_remaining_seconds=0,
            duration_minutes=config.duration_minutes if config else 120,
            team_status=session.status,
            total_score=session.total_score or 0,
            solved_count=solved_count,
            message="Sprint has not been started yet. Please wait for the admin."
        )
    
    duration = config.duration_minutes or 120
    close_at = config.test_close_at or (config.global_start_time + timedelta(minutes=duration))
    
    if now < config.global_start_time:
        return SprintStatusResponse(
            sprint_started=False,
            sprint_active=False,
            sprint_ended=False,
            global_start_time=config.global_start_time,
            test_close_at=close_at,
            time_remaining_seconds=0,
            duration_minutes=duration,
            team_status=session.status,
            total_score=session.total_score or 0,
            solved_count=solved_count,
            message="Sprint is scheduled but not active yet."
        )
    elif now >= close_at:
        # If in progress when time expired, auto-submit
        if session.status == TestStatus.IN_PROGRESS:
            session.status = TestStatus.AUTO_SUBMITTED
            session.auto_submitted = True
            session.submitted_at = close_at
            if session.test_started_at:
                session.time_taken_seconds = int((close_at - session.test_started_at).total_seconds())
            db.commit()
            
        return SprintStatusResponse(
            sprint_started=True,
            sprint_active=False,
            sprint_ended=True,
            global_start_time=config.global_start_time,
            test_close_at=close_at,
            time_remaining_seconds=0,
            duration_minutes=duration,
            team_status=session.status,
            total_score=session.total_score or 0,
            solved_count=solved_count,
            message="Sprint has ended."
        )
    else:
        # Sprint is active
        if session.status == TestStatus.NOT_STARTED:
            session.status = TestStatus.IN_PROGRESS
            session.test_started_at = config.global_start_time
            db.commit()
            
        remaining = int((close_at - now).total_seconds())
        return SprintStatusResponse(
            sprint_started=True,
            sprint_active=True,
            sprint_ended=False,
            global_start_time=config.global_start_time,
            test_close_at=close_at,
            time_remaining_seconds=max(0, remaining),
            duration_minutes=duration,
            team_status=session.status,
            total_score=session.total_score or 0,
            solved_count=solved_count,
            message="Sprint is active."
        )


@router.post("/test/start", response_model=TestStartResponse)
async def start_test(
    current_team: Team = Depends(get_current_team),
    db: Session = Depends(get_db)
):
    """Check & return sprint start details (started globally by admin)"""
    config = db.query(TestConfiguration).first()
    now = datetime.utcnow()
    
    if not config or not config.global_start_time or now < config.global_start_time:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The sprint has not been started by the admin yet. Please wait in the lobby."
        )
    
    duration = config.duration_minutes or settings.DEFAULT_TEST_DURATION_MINUTES
    close_at = config.test_close_at or (config.global_start_time + timedelta(minutes=duration))
    
    if now > close_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The sprint has concluded."
        )
    
    # Get or create test session
    test_session = db.query(TestSession).filter(
        TestSession.team_id == current_team.id
    ).first()
    
    if not test_session:
        test_session = TestSession(
            team_id=current_team.id,
            test_started_at=config.global_start_time,
            status=TestStatus.IN_PROGRESS
        )
        db.add(test_session)
    else:
        if test_session.status == TestStatus.NOT_STARTED:
            test_session.status = TestStatus.IN_PROGRESS
            test_session.test_started_at = config.global_start_time
    
    db.commit()
    
    return TestStartResponse(
        test_started=True,
        started_at=config.global_start_time,
        expires_at=close_at,
        duration_minutes=duration,
        questions_count=25,
        auto_submit_warning="Test will auto-submit at expiry"
    )


@router.get("/questions", response_model=QuestionsListResponse)
async def get_questions(
    current_team: Team = Depends(get_current_team),
    db: Session = Depends(get_db)
):
    """Get the team's assigned 25 questions"""
    config = db.query(TestConfiguration).first()
    now = datetime.utcnow()
    
    if not config or not config.global_start_time or now < config.global_start_time:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The sprint has not been started by the administrator yet. Please wait in the lobby."
        )
    
    duration = config.duration_minutes or settings.DEFAULT_TEST_DURATION_MINUTES
    close_at = config.test_close_at or (config.global_start_time + timedelta(minutes=duration))
    
    # Check test session
    test_session = db.query(TestSession).filter(
        TestSession.team_id == current_team.id
    ).first()
    
    if not test_session:
        test_session = TestSession(
            team_id=current_team.id,
            test_started_at=config.global_start_time,
            status=TestStatus.IN_PROGRESS
        )
        db.add(test_session)
        db.commit()
    elif test_session.status == TestStatus.NOT_STARTED:
        test_session.status = TestStatus.IN_PROGRESS
        test_session.test_started_at = config.global_start_time
        db.commit()
    
    # Get assigned questions
    assignments = db.query(TeamQuestionAssignment).filter(
        TeamQuestionAssignment.team_id == current_team.id
    ).order_by(TeamQuestionAssignment.position).all()
    
    if len(assignments) == 0:
        try:
            from app.question_assignment import QuestionAssignmentService
            QuestionAssignmentService.assign_questions_to_team(db, current_team.id)
            assignments = db.query(TeamQuestionAssignment).filter(
                TeamQuestionAssignment.team_id == current_team.id
            ).order_by(TeamQuestionAssignment.position).all()
        except Exception as e:
            pass
    
    questions = []
    for assignment in assignments:
        question = db.query(Question).filter(Question.id == assignment.question_id).first()
        
        if not question:
            continue
        
        # Get submission status
        submission = db.query(Submission).filter(
            Submission.team_id == current_team.id,
            Submission.question_id == question.id,
            Submission.is_final == True
        ).first()
        
        submission_status = None
        awarded_marks = None
        if submission:
            grading = db.query(GradingResult).filter(
                GradingResult.submission_id == submission.id
            ).first()
            if grading:
                submission_status = "graded"
                awarded_marks = grading.marks_awarded
            else:
                # Check if in queue
                queue_pos = GradingQueue.get_queue_position(db, submission.id)
                if queue_pos:
                    submission_status = "grading"
                else:
                    submission_status = "submitted"
        
        # Get latest submission (final or draft) for preserving candidate's work
        latest_sub = db.query(Submission).filter(
            Submission.team_id == current_team.id,
            Submission.question_id == question.id
        ).order_by(Submission.id.desc()).first()
        
        saved_code = latest_sub.code if latest_sub else None
        saved_lang = (latest_sub.language.value if hasattr(latest_sub.language, 'value') else str(latest_sub.language)) if latest_sub else None

        questions.append(AssignedQuestionResponse(
            position=assignment.position,
            question_id=question.id,
            title=question.title,
            difficulty=question.difficulty,
            marks=question.marks,
            prompt_markdown=question.prompt_markdown,
            starter_code={
                "python": question.starter_code_python,
                "cpp": question.starter_code_cpp,
                "java": question.starter_code_java,
                "javascript": question.starter_code_javascript
            },
            sample_test_cases=[
                SampleTestCaseResponse(
                    input_data=tc.input_data,
                    expected_output=tc.expected_output,
                    explanation=tc.explanation
                )
                for tc in question.sample_test_cases
            ],
            time_limit_seconds=question.time_limit_seconds,
            memory_limit_mb=question.memory_limit_mb,
            submission_status=submission_status,
            awarded_marks=awarded_marks,
            saved_code=saved_code,
            saved_language=saved_lang
        ))
    
    time_remaining = int((close_at - now).total_seconds())
    solved_count = sum(1 for q in questions if q.submission_status == "graded" and (q.awarded_marks or 0) > 0)
    
    return QuestionsListResponse(
        questions=questions,
        test_status=TestStatusResponse(
            started_at=config.global_start_time,
            time_remaining_seconds=max(0, time_remaining),
            auto_submit_at=close_at,
            status=test_session.status,
            total_score=test_session.total_score or 0,
            solved_count=solved_count
        ),
        total_score=test_session.total_score or 0,
        solved_count=solved_count
    )


@router.post("/run-code", response_model=CodeRunResponse)
async def run_code(
    run_data: CodeRunRequest,
    current_team: Team = Depends(get_current_team),
    db: Session = Depends(get_db)
):
    """Compile & execute candidate code locally against custom input or sample test cases.
    Supports any valid code structure/algorithm in Python, C++, Java, and JavaScript."""
    from code_compiler_tester import CodeCompilerTester

    # If running against sample test cases (no custom input)
    if run_data.question_id and (not run_data.custom_input or run_data.custom_input.strip() == ""):
        sample_tests = db.query(SampleTestCase).filter(
            SampleTestCase.question_id == run_data.question_id
        ).order_by(SampleTestCase.order).all()
        
        if sample_tests:
            test_inputs = [tc.input_data for tc in sample_tests]
            raw_results = CodeCompilerTester.execute_multi_test_cases(
                code=run_data.code,
                language=run_data.language.value,
                test_inputs=test_inputs,
                timeout_seconds=5
            )
            
            all_passed = True
            combined_stdout = ""
            combined_stderr = ""
            total_time = 0
            sample_results = []
            
            for idx, (tc, res) in enumerate(zip(sample_tests, raw_results), 1):
                actual = res["stdout"].strip()
                expected = tc.expected_output.strip()
                passed = res["success"] and CodeCompilerTester.compare_outputs(actual, expected)
                if not passed:
                    all_passed = False
                    
                total_time += res["execution_time_ms"]
                if res["stderr"]:
                    combined_stderr += f"[Test {idx} Error]: {res['stderr']}\n"
                combined_stdout += f"[Sample Test {idx} Output]:\n{res['stdout']}\n"
                
                err_msg = None
                if not passed:
                    err_msg = res.get("stderr") if res.get("stderr") else res.get("error")
                
                sample_results.append(SampleTestRunResult(
                    test_case=idx,
                    input_data=tc.input_data,
                    expected_output=tc.expected_output,
                    actual_output=res["stdout"] if res.get("stdout") is not None else "",
                    passed=passed,
                    execution_time_ms=res["execution_time_ms"],
                    error=err_msg
                ))
                
            return CodeRunResponse(
                success=all_passed,
                stdout=combined_stdout,
                stderr=combined_stderr,
                execution_time_ms=total_time,
                error=None if all_passed else "One or more sample test cases failed",
                sample_test_results=sample_results,
                ai_evaluation=None,
                ai_model=None
            )
            
    # Run with custom input
    res = CodeCompilerTester.execute_code(
        code=run_data.code,
        language=run_data.language.value,
        stdin=run_data.custom_input or "",
        timeout_seconds=5
    )
    
    return CodeRunResponse(
        success=res["success"],
        stdout=res["stdout"],
        stderr=res["stderr"],
        execution_time_ms=res["execution_time_ms"],
        error=res.get("error"),
        sample_test_results=None,
        ai_evaluation=None,
        ai_model=None
    )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_team_leaderboard(
    current_team: Team = Depends(get_current_team),
    db: Session = Depends(get_db)
):
    """Get leaderboard for participants sorted by Score DESC, then Timestamp ASC"""
    config = db.query(TestConfiguration).first()
    
    # Allow viewing if published or team leaderboard view enabled
    if not config or (not config.leaderboard_published and not config.allow_team_view_leaderboard):
        pass
    
    sessions = db.query(TestSession).filter(
        TestSession.status.in_([TestStatus.IN_PROGRESS, TestStatus.SUBMITTED, TestStatus.AUTO_SUBMITTED])
    ).all()
    
    raw_entries = []
    
    for session in sessions:
        team = db.query(Team).filter(Team.id == session.team_id).first()
        
        last_sub_time = db.query(func.max(Submission.submitted_at)).filter(
            Submission.team_id == session.team_id,
            Submission.is_final == True
        ).scalar()
        
        eff_dt = session.submitted_at or last_sub_time or session.test_started_at or datetime.max
        
        if session.time_taken_seconds and session.time_taken_seconds > 0:
            time_taken = session.time_taken_seconds
        elif session.test_started_at and eff_dt != datetime.max:
            time_taken = max(0, int((eff_dt - session.test_started_at).total_seconds()))
        else:
            time_taken = 0
            
        total_submissions = db.query(Submission).filter(
            Submission.team_id == session.team_id,
            Submission.is_final == True
        ).count()
        
        solved_submissions = db.query(Submission).join(GradingResult).filter(
            Submission.team_id == session.team_id,
            Submission.is_final == True,
            GradingResult.marks_awarded > 0
        ).count()
        
        hrs = time_taken // 3600
        mins = (time_taken % 3600) // 60
        secs = time_taken % 60
        formatted_time = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        
        last_sub_str = eff_dt.strftime("%H:%M:%S") if eff_dt != datetime.max else "--:--:--"
        
        raw_entries.append({
            "session": session,
            "team": team,
            "total_score": session.total_score or 0,
            "eff_dt": eff_dt,
            "time_taken": time_taken,
            "formatted_time": formatted_time,
            "last_sub_time": eff_dt if eff_dt != datetime.max else None,
            "last_sub_str": last_sub_str,
            "total_submissions": total_submissions,
            "solved_submissions": solved_submissions
        })
    
    # Sort: Score DESC, eff_dt ASC (earlier finish/submission ranks higher!), time_taken ASC, team_id ASC
    raw_entries.sort(key=lambda x: (-x["total_score"], x["eff_dt"], x["time_taken"], x["session"].team_id))
    
    leaderboard = []
    for rank, entry in enumerate(raw_entries, 1):
        s = entry["session"]
        t = entry["team"]
        leaderboard.append(LeaderboardEntry(
            rank=rank,
            team_id=s.team_id,
            team_name=t.team_name if t else "Unknown",
            college_name=t.college if t else None,
            total_score=entry["total_score"],
            time_taken_seconds=entry["time_taken"],
            time_taken_formatted=entry["formatted_time"],
            last_submission_time=entry["last_sub_time"],
            last_submission_formatted=entry["last_sub_str"],
            score_breakdown=ScoreBreakdown(
                easy_score=s.easy_score or 0,
                medium_score=s.medium_score or 0,
                hard_score=s.hard_score or 0
            ),
            questions_attempted=entry["total_submissions"],
            questions_solved=entry["solved_submissions"],
            submitted_at=s.submitted_at
        ))
        s.rank = rank
        
    try:
        db.commit()
    except Exception:
        db.rollback()
        
    total_teams = db.query(Team).count()
    teams_submitted = db.query(TestSession).filter(
        TestSession.status.in_([TestStatus.SUBMITTED, TestStatus.AUTO_SUBMITTED])
    ).count()
    teams_in_progress = db.query(TestSession).filter(
        TestSession.status == TestStatus.IN_PROGRESS
    ).count()
    teams_not_started = total_teams - teams_submitted - teams_in_progress
    
    return LeaderboardResponse(
        leaderboard=leaderboard,
        total_teams=total_teams,
        teams_submitted=teams_submitted,
        teams_in_progress=teams_in_progress,
        teams_not_started=teams_not_started
    )


@router.post("/submissions/{question_id}/autosave")
@router.post("/questions/{question_id}/autosave")
async def autosave_code(
    question_id: int,
    code_data: CodeSubmitRequest,
    current_team: Team = Depends(get_current_team),
    db: Session = Depends(get_db)
):
    """Autosave code without grading (for recovery & persistence)"""
    # Verify test session
    test_session = db.query(TestSession).filter(
        TestSession.team_id == current_team.id
    ).first()
    
    if not test_session:
        test_session = TestSession(
            team_id=current_team.id,
            status=TestStatus.IN_PROGRESS,
            test_started_at=datetime.utcnow()
        )
        db.add(test_session)
        db.flush()
    elif test_session.status == TestStatus.NOT_STARTED:
        test_session.status = TestStatus.IN_PROGRESS
        test_session.test_started_at = datetime.utcnow()
        db.flush()
    elif test_session.status in [TestStatus.SUBMITTED, TestStatus.AUTO_SUBMITTED]:
        return {"autosaved": False, "detail": "Test concluded"}
    
    # Verify question assigned
    assignment = db.query(TeamQuestionAssignment).filter(
        TeamQuestionAssignment.team_id == current_team.id,
        TeamQuestionAssignment.question_id == question_id
    ).first()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not assigned to team"
        )
    
    # Upsert autosave submission (reuse existing draft or final submission if any)
    existing_sub = db.query(Submission).filter(
        Submission.team_id == current_team.id,
        Submission.question_id == question_id
    ).order_by(Submission.id.desc()).first()
    
    if existing_sub and not existing_sub.is_final:
        existing_sub.code = code_data.code
        existing_sub.language = code_data.language
        existing_sub.submitted_at = datetime.utcnow()
        submission = existing_sub
    else:
        submission = Submission(
            team_id=current_team.id,
            question_id=question_id,
            code=code_data.code,
            language=code_data.language,
            is_final=False
        )
        db.add(submission)
    
    db.commit()
    
    return {
        "autosaved": True,
        "saved_at": submission.submitted_at,
        "recoverable": True
    }


@router.post("/submissions/{question_id}/submit", response_model=SubmissionResponse)
async def submit_code(
    question_id: int,
    code_data: CodeSubmitRequest,
    current_team: Team = Depends(get_current_team),
    db: Session = Depends(get_db)
):
    """Submit code for final grading"""
    # Verify test in progress
    test_session = db.query(TestSession).filter(
        TestSession.team_id == current_team.id
    ).first()
    
    if not test_session:
        test_session = TestSession(
            team_id=current_team.id,
            status=TestStatus.IN_PROGRESS,
            test_started_at=datetime.utcnow()
        )
        db.add(test_session)
        db.flush()
    elif test_session.status == TestStatus.NOT_STARTED:
        test_session.status = TestStatus.IN_PROGRESS
        test_session.test_started_at = datetime.utcnow()
        db.flush()
    elif test_session.status in [TestStatus.SUBMITTED, TestStatus.AUTO_SUBMITTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test has already been submitted and concluded"
        )
    
    # Verify question assigned
    assignment = db.query(TeamQuestionAssignment).filter(
        TeamQuestionAssignment.team_id == current_team.id,
        TeamQuestionAssignment.question_id == question_id
    ).first()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not assigned to team"
        )
    
    # Check if already submitted -> allow updating and re-grading
    existing = db.query(Submission).filter(
        Submission.team_id == current_team.id,
        Submission.question_id == question_id,
        Submission.is_final == True
    ).first()
    
    if existing:
        existing.code = code_data.code
        existing.language = code_data.language
        existing.submitted_at = datetime.utcnow()
        # Delete old grading result so fresh execution occurs
        db.query(GradingResult).filter(GradingResult.submission_id == existing.id).delete()
        submission = existing
    else:
        # Create final submission
        submission = Submission(
            team_id=current_team.id,
            question_id=question_id,
            code=code_data.code,
            language=code_data.language,
            is_final=True
        )
        db.add(submission)
        db.flush()
    
    # Enqueue for grading
    GradingQueue.enqueue(db, submission.id)
    db.commit()
    
    # Grading handled by external grading_worker.py process
    
    queue_pos = GradingQueue.get_queue_position(db, submission.id)
    
    return SubmissionResponse(
        submission_id=submission.id,
        status="queued",
        message="Submission queued for grading",
        estimated_grading_time_seconds=2,
        check_status_url=f"/api/teams/submissions/{submission.id}/status",
        queue_position=queue_pos
    )


@router.get("/submissions/{submission_id}/status", response_model=GradingResultResponse)
async def get_submission_status(
    submission_id: int,
    current_team: Team = Depends(get_current_team),
    db: Session = Depends(get_db)
):
    """Check grading status of a submission"""
    # Verify submission belongs to team
    submission = db.query(Submission).filter(
        Submission.id == submission_id,
        Submission.team_id == current_team.id
    ).first()
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )
    
    # Check if graded
    grading_result = db.query(GradingResult).filter(
        GradingResult.submission_id == submission_id
    ).first()
    
    if grading_result:
        # Graded
        test_results = []
        if grading_result.test_results:
            for tr in grading_result.test_results:
                test_results.append(TestResultDetail(
                    test_case=tr.get("test_case"),
                    passed=tr.get("passed"),
                    execution_time_ms=tr.get("execution_time_ms"),
                    error=tr.get("error")
                ))
        
        return GradingResultResponse(
            submission_id=submission_id,
            status="graded",
            marks_awarded=grading_result.marks_awarded,
            passed_tests=grading_result.passed_hidden_tests,
            total_tests=grading_result.total_hidden_tests,
            execution_time_ms=grading_result.execution_time_ms,
            memory_used_mb=grading_result.memory_used_mb,
            test_results=test_results,
            error_output=grading_result.error_output
        )
    
    # Check if in queue
    queue_pos = GradingQueue.get_queue_position(db, submission_id)
    
    if queue_pos:
        return GradingResultResponse(
            submission_id=submission_id,
            status="grading",
            marks_awarded=0,
            passed_tests=0,
            total_tests=0,
            execution_time_ms=None,
            memory_used_mb=None,
            test_results=None,
            error_output=None
        )
    
    # Queued but position unknown
    return GradingResultResponse(
        submission_id=submission_id,
        status="queued",
        marks_awarded=0,
        passed_tests=0,
        total_tests=0,
        execution_time_ms=None,
        memory_used_mb=None,
        test_results=None,
        error_output=None
    )


@router.post("/test/submit-final", response_model=TestSubmitResponse)
async def submit_final_test(
    current_team: Team = Depends(get_current_team),
    db: Session = Depends(get_db)
):
    """Submit entire test (mark all autosaves as final)"""
    # Get test session
    test_session = db.query(TestSession).filter(
        TestSession.team_id == current_team.id
    ).first()
    
    if not test_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test session not found"
        )
    
    # Check if already submitted (idempotency)
    if test_session.status in [TestStatus.SUBMITTED, TestStatus.AUTO_SUBMITTED]:
        time_taken = f"{test_session.time_taken_seconds // 60}m"
        return TestSubmitResponse(
            test_submitted=True,
            submitted_at=test_session.submitted_at,
            time_taken_seconds=test_session.time_taken_seconds,
            time_taken_formatted=time_taken,
            questions_submitted=25,
            questions_pending_grade=0,
            preliminary_score=test_session.total_score,
            message="Test already submitted"
        )
    
    # Check if test in progress
    if test_session.status != TestStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test not in progress"
        )
    
    # Mark all autosaves as final (if not already submitted)
    now = datetime.utcnow()
    
    # Get all questions for this team
    assignments = db.query(TeamQuestionAssignment).filter(
        TeamQuestionAssignment.team_id == current_team.id
    ).all()
    
    questions_submitted = 0
    for assignment in assignments:
        # Check if already has final submission
        existing_final = db.query(Submission).filter(
            Submission.team_id == current_team.id,
            Submission.question_id == assignment.question_id,
            Submission.is_final == True
        ).first()
        
        if existing_final:
            questions_submitted += 1
            continue
        
        # Get latest autosave
        latest_autosave = db.query(Submission).filter(
            Submission.team_id == current_team.id,
            Submission.question_id == assignment.question_id,
            Submission.is_final == False
        ).order_by(desc(Submission.submitted_at)).first()
        
        if latest_autosave:
            # Mark as final and enqueue
            latest_autosave.is_final = True
            GradingQueue.enqueue(db, latest_autosave.id)
            questions_submitted += 1
    
    # Update test session
    test_session.submitted_at = now
    test_session.status = TestStatus.SUBMITTED
    test_session.time_taken_seconds = int((now - test_session.test_started_at).total_seconds())
    
    db.commit()
    
    time_formatted = f"{test_session.time_taken_seconds // 3600}h {(test_session.time_taken_seconds % 3600) // 60}m"
    
    return TestSubmitResponse(
        test_submitted=True,
        submitted_at=now,
        time_taken_seconds=test_session.time_taken_seconds,
        time_taken_formatted=time_formatted,
        questions_submitted=questions_submitted,
        questions_pending_grade=questions_submitted,  # All pending initially
        preliminary_score=test_session.total_score,
        message="Test submitted successfully. Grading in progress."
    )


@router.post("/proctoring/violation", response_model=ProctoringViolationResponse)
async def record_proctoring_violation(
    violation_data: ProctoringViolationRequest,
    current_team: Team = Depends(get_current_team),
    db: Session = Depends(get_db)
):
    """Record fullscreen exit or tab switch alert while keeping test active (auto-submit disabled)"""
    existing_strikes = db.query(ProctoringViolation).filter(
        ProctoringViolation.team_id == current_team.id
    ).count()
    
    current_strike = existing_strikes + 1
    auto_submitted = False
    action = f"alert_{current_strike}"
    message = f"Alert #{current_strike}: Fullscreen/tab switch logged to admin proctoring monitor."

    # Look up phone
    phone = "N/A"
    try:
        import csv
        with open("teams_real.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["team_name"] == current_team.team_name:
                    phone = row["leader_phone"]
                    break
    except Exception:
        phone = "N/A"

    violation = ProctoringViolation(
        team_id=current_team.id,
        team_name=current_team.team_name,
        leader_phone=phone,
        violation_type=violation_data.violation_type,
        strike_count=current_strike,
        action_taken=action
    )
    db.add(violation)
    db.commit()
    
    return ProctoringViolationResponse(
        success=True,
        strike_count=current_strike,
        max_strikes=999,
        action_taken=action,
        auto_submitted=False,
        message=message
    )


@router.post("/evaluate-ai", response_model=AIEvaluationResponse)
async def evaluate_code_ai(
    eval_data: AIEvaluationRequest,
    current_team: Team = Depends(get_current_team),
    db: Session = Depends(get_db)
):
    """
    Evaluate user-written code using OpenRouter (Poolside Laguna S 2.1)
    Provides code structure, complexity, and best practice analysis.
    """
    question = db.query(Question).filter(Question.id == eval_data.question_id).first()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    # Check if team has a graded submission to include pass/fail context
    last_submission = db.query(Submission).filter(
        Submission.team_id == current_team.id,
        Submission.question_id == eval_data.question_id,
        Submission.is_final == True
    ).first()
    
    test_passed = None
    if last_submission:
        g_res = db.query(GradingResult).filter(GradingResult.submission_id == last_submission.id).first()
        if g_res:
            test_passed = (g_res.passed_hidden_tests == g_res.total_hidden_tests and g_res.marks_awarded > 0)
    
    result = await AICodeEvaluator.evaluate_code(
        problem_title=question.title,
        problem_prompt=question.prompt_markdown or "",
        code=eval_data.code,
        language=eval_data.language,
        test_passed=test_passed
    )
    
    if not result.get("success"):
        return AIEvaluationResponse(
            success=False,
            error=result.get("error", "AI evaluation failed")
        )
    
    return AIEvaluationResponse(
        success=True,
        model=result.get("model"),
        review=result.get("review")
    )


@router.post("/logout")
async def team_logout(
    current_team: Team = Depends(get_current_team),
    db: Session = Depends(get_db)
):
    """Log out participant, clear active presence from lobby immediately, and log event"""
    # 1. Clear presence from in-memory tracker
    clear_team_presence(current_team.id)

    # 2. Look up leader phone
    phone = "N/A"
    try:
        import csv
        with open("teams_real.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["team_name"] == current_team.team_name:
                    phone = row["leader_phone"]
                    break
    except Exception:
        phone = "N/A"

    # 3. Record logout audit log / proctoring alert
    violation = ProctoringViolation(
        team_id=current_team.id,
        team_name=current_team.team_name,
        leader_phone=phone,
        violation_type="Participant Logged Out",
        strike_count=0,
        action_taken="Logged Out (Presence Cleared)"
    )
    db.add(violation)
    db.commit()

    return {
        "success": True,
        "message": f"Team {current_team.team_name} logged out. Presence cleared from lobby."
    }


