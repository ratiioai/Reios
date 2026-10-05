"""
Admin routes for platform management
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List
import io
import csv
from datetime import datetime, timedelta

from app.auth import get_current_admin
from app.database import get_db
from app.models import (
    Admin, Team, Question, SampleTestCase, HiddenTestCase,
    TestConfiguration, TestSession, Submission, GradingResult,
    TestStatus, DifficultyLevel, ProctoringViolation
)
from app.schemas import (
    QuestionCreate, QuestionUpdate, QuestionResponse, QuestionListItem,
    TestConfigurationUpdate, TestConfigurationResponse,
    CSVUploadResponse, TestStatusSummary, LeaderboardResponse,
    GradeOverrideRequest, GradeOverrideResponse, QueueStatsResponse,
    LeaderboardEntry, ScoreBreakdown,
    ProctoringAlertItem, ProctoringAlertsListResponse,
    SprintStatusResponse, SprintActionResponse
)
from app.csv_import import validate_csv_structure, validate_csv_data, CSVImportError
import app.question_assignment as question_assignment
from app.grading_queue import GradingQueue
import pandas as pd

router = APIRouter(prefix="/api/admin", tags=["admin"])


# CSV Upload
@router.post("/teams/upload-csv", response_model=CSVUploadResponse)
async def upload_teams_csv(
    file: UploadFile = File(...),
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Upload 175 teams from CSV"""
    try:
        # Read CSV file
        contents = await file.read()
        csv_file = io.StringIO(contents.decode('utf-8'))
        df = pd.read_csv(csv_file)
        
        # Validate structure
        is_valid, structure_errors = validate_csv_structure(df)
        if not is_valid:
            return CSVUploadResponse(
                success=False,
                teams_created=0,
                teams_failed=len(structure_errors),
                question_sets_assigned=0,
                errors=[{"row": 0, "error": e} for e in structure_errors],
                summary={"validation_errors": len(structure_errors)}
            )
        
        # Validate data
        validation_result = validate_csv_data(df, db)
        teams = validation_result.valid_rows
        errors = validation_result.errors
        
        if errors:
            return CSVUploadResponse(
                success=False,
                teams_created=0,
                teams_failed=len(errors),
                question_sets_assigned=0,
                errors=errors,
                summary={"total_rows": len(teams) + len(errors), "validation_errors": len(errors)}
            )
        
        # Import teams
        from app.auth import hash_phone
        created_teams = []
        for row_data in teams:
            team = Team(
                team_name=row_data['team_name'],
                leader_name=row_data['leader_name'],
                leader_phone_hash=hash_phone(row_data['leader_phone']),
                member_2=row_data.get('member_2'),
                member_3=row_data.get('member_3'),
                member_4=row_data.get('member_4'),
                college=row_data.get('college'),
                csv_row_ref=row_data['row'],
                is_active=True,
                failed_login_attempts=0,
            )
            db.add(team)
            created_teams.append(team)
        
        db.commit()
        
        # Refresh to get IDs
        for team in created_teams:
            db.refresh(team)
        
        # Assign unique question sets
        assigned_count = 0
        for team in created_teams:
            try:
                success = question_assignment.assign_unique_question_set(db, team)
                if success:
                    assigned_count += 1
            except Exception as e:
                print(f"Error assigning questions to team {team.id}: {e}")
        
        return CSVUploadResponse(
            success=True,
            teams_created=len(created_teams),
            teams_failed=0,
            question_sets_assigned=assigned_count,
            errors=[],
            summary={
                "total_rows": len(teams),
                "duplicates_skipped": 0,
                "validation_errors": 0
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading CSV: {str(e)}"
        )


# Question Management
@router.post("/questions", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
async def create_question(
    question_data: QuestionCreate,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Create a new question with test cases"""
    # Auto-assign marks based on difficulty
    marks_map = {
        DifficultyLevel.EASY: 5,
        DifficultyLevel.MEDIUM: 10,
        DifficultyLevel.HARD: 20
    }
    
    question = Question(
        title=question_data.title,
        difficulty=question_data.difficulty,
        prompt_markdown=question_data.prompt_markdown,
        starter_code_python=question_data.starter_code_python,
        starter_code_cpp=question_data.starter_code_cpp,
        starter_code_java=question_data.starter_code_java,
        starter_code_javascript=question_data.starter_code_javascript,
        time_limit_seconds=question_data.time_limit_seconds,
        memory_limit_mb=question_data.memory_limit_mb,
        marks=marks_map[question_data.difficulty],
        is_active=True
    )
    
    db.add(question)
    db.flush()  # Get question.id
    
    # Add sample test cases
    for tc in question_data.sample_test_cases:
        sample_tc = SampleTestCase(
            question_id=question.id,
            input_data=tc.input_data,
            expected_output=tc.expected_output,
            explanation=tc.explanation,
            order=tc.order
        )
        db.add(sample_tc)
    
    # Add hidden test cases
    for tc in question_data.hidden_test_cases:
        hidden_tc = HiddenTestCase(
            question_id=question.id,
            input_data=tc.input_data,
            expected_output=tc.expected_output,
            order=tc.order
        )
        db.add(hidden_tc)
    
    db.commit()
    db.refresh(question)
    
    return QuestionResponse(
        id=question.id,
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
            {"input_data": tc.input_data, "expected_output": tc.expected_output, "explanation": tc.explanation}
            for tc in question.sample_test_cases
        ],
        time_limit_seconds=question.time_limit_seconds,
        memory_limit_mb=question.memory_limit_mb,
        is_active=question.is_active,
        created_at=question.created_at
    )


@router.get("/questions", response_model=List[QuestionListItem])
async def list_questions(
    difficulty: str = None,
    active_only: bool = True,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """List all questions"""
    query = db.query(Question)
    
    if active_only:
        query = query.filter(Question.is_active == True)
    
    if difficulty:
        query = query.filter(Question.difficulty == difficulty)
    
    questions = query.order_by(desc(Question.created_at)).all()
    
    return [
        QuestionListItem(
            id=q.id,
            title=q.title,
            difficulty=q.difficulty,
            marks=q.marks,
            is_active=q.is_active,
            sample_test_cases_count=len(q.sample_test_cases),
            hidden_test_cases_count=len(q.hidden_test_cases),
            created_at=q.created_at
        )
        for q in questions
    ]


@router.patch("/questions/{question_id}")
async def update_question(
    question_id: int,
    question_data: QuestionUpdate,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update existing question (doesn't affect existing assignments)"""
    question = db.query(Question).filter(Question.id == question_id).first()
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Update fields
    if question_data.title:
        question.title = question_data.title
    if question_data.prompt_markdown:
        question.prompt_markdown = question_data.prompt_markdown
    if question_data.starter_code_python is not None:
        question.starter_code_python = question_data.starter_code_python
    if question_data.starter_code_cpp is not None:
        question.starter_code_cpp = question_data.starter_code_cpp
    if question_data.starter_code_java is not None:
        question.starter_code_java = question_data.starter_code_java
    if question_data.starter_code_javascript is not None:
        question.starter_code_javascript = question_data.starter_code_javascript
    if question_data.time_limit_seconds:
        question.time_limit_seconds = question_data.time_limit_seconds
    if question_data.memory_limit_mb:
        question.memory_limit_mb = question_data.memory_limit_mb
    if question_data.is_active is not None:
        question.is_active = question_data.is_active
    
    question.updated_at = datetime.utcnow()
    db.commit()
    
    return {"id": question.id, "updated_at": question.updated_at, "affected_teams": 0}


# Test Configuration
@router.post("/test/configure", response_model=TestConfigurationResponse)
async def configure_test(
    config_data: TestConfigurationUpdate,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Configure test timing and rules"""
    config = db.query(TestConfiguration).first()
    
    if not config:
        config = TestConfiguration(id=1)
        db.add(config)
    
    if config_data.test_open_at:
        config.test_open_at = config_data.test_open_at
    if config_data.test_close_at:
        config.test_close_at = config_data.test_close_at
    if config_data.duration_minutes:
        config.duration_minutes = config_data.duration_minutes
    if config_data.synchronized_start is not None:
        config.synchronized_start = config_data.synchronized_start
    if config_data.global_start_time:
        config.global_start_time = config_data.global_start_time
    if config_data.allow_team_view_leaderboard is not None:
        config.allow_team_view_leaderboard = config_data.allow_team_view_leaderboard
    if config_data.leaderboard_published is not None:
        config.leaderboard_published = config_data.leaderboard_published
    
    config.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(config)
    
    return TestConfigurationResponse(
        test_open_at=config.test_open_at,
        test_close_at=config.test_close_at,
        duration_minutes=config.duration_minutes,
        synchronized_start=config.synchronized_start,
        global_start_time=config.global_start_time,
        allow_team_view_leaderboard=config.allow_team_view_leaderboard,
        leaderboard_published=config.leaderboard_published
    )


@router.get("/test/configuration", response_model=TestConfigurationResponse)
async def get_test_configuration(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get current test timing and configuration"""
    config = db.query(TestConfiguration).first()
    if not config:
        config = TestConfiguration(id=1, duration_minutes=120)
        db.add(config)
        db.commit()
        db.refresh(config)
        
    return TestConfigurationResponse(
        test_open_at=config.test_open_at,
        test_close_at=config.test_close_at,
        duration_minutes=config.duration_minutes,
        synchronized_start=config.synchronized_start,
        global_start_time=config.global_start_time,
        allow_team_view_leaderboard=config.allow_team_view_leaderboard,
        leaderboard_published=config.leaderboard_published
    )


from app.presence import get_online_team_ids, is_team_online, clear_team_presence


@router.get("/test/status", response_model=TestStatusSummary)
async def get_test_status(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get test status summary with real-time online presence"""
    total_teams = db.query(Team).filter(Team.is_active == True).count()
    online_ids = get_online_team_ids()
    
    # Check if sprint is globally active
    config = db.query(TestConfiguration).first()
    now = datetime.utcnow()
    sprint_is_live = bool(config and config.global_start_time and now >= config.global_start_time and (not config.test_close_at or now < config.test_close_at))
    
    # Active writing = online teams that are in an active sprint
    # In lobby = online teams that are waiting
    # Submitted = teams with finished sessions
    submitted_count = db.query(TestSession).filter(
        TestSession.status.in_([TestStatus.SUBMITTED, TestStatus.AUTO_SUBMITTED])
    ).count()
    
    in_progress_count = 0
    in_lobby_count = 0
    
    for tid in online_ids:
        session = db.query(TestSession).filter(TestSession.team_id == tid).first()
        if session and session.status in [TestStatus.SUBMITTED, TestStatus.AUTO_SUBMITTED]:
            continue
        if sprint_is_live:
            in_progress_count += 1
        else:
            in_lobby_count += 1
            
    not_started_count = max(0, total_teams - in_progress_count - submitted_count)
    
    return TestStatusSummary(
        total_teams=total_teams,
        teams_not_started=in_lobby_count,
        teams_in_progress=in_progress_count,
        teams_submitted=submitted_count,
        teams_auto_submitted=0
    )


@router.get("/teams/live-directory")
async def get_teams_live_directory(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get real-time presence & status of all teams (1 to 153) in a single fast query"""
    teams = db.query(Team).filter(Team.is_active == True).order_by(Team.id).all()
    online_ids = get_online_team_ids()
    
    # Bulk fetch all sessions and strike counts in 2 fast queries
    sessions_map = {s.team_id: s for s in db.query(TestSession).all()}
    
    from sqlalchemy import func
    strikes_list = db.query(
        ProctoringViolation.team_id,
        func.count(ProctoringViolation.id)
    ).group_by(ProctoringViolation.team_id).all()
    strikes_map = {tid: count for tid, count in strikes_list}
    
    config = db.query(TestConfiguration).first()
    now = datetime.utcnow()
    sprint_is_live = bool(config and config.global_start_time and now >= config.global_start_time and (not config.test_close_at or now < config.test_close_at))
    
    result = []
    for t in teams:
        session = sessions_map.get(t.id)
        strikes = strikes_map.get(t.id, 0)
        is_online = t.id in online_ids
        
        status_val = "offline"
        score = 0
        auto_sub = False
        time_taken = None
        
        if session:
            score = session.total_score or 0
            auto_sub = bool(session.auto_submitted)
            time_taken = session.time_taken_seconds
            
            if session.status == TestStatus.SUBMITTED:
                status_val = "submitted"
            elif session.status == TestStatus.AUTO_SUBMITTED or auto_sub:
                status_val = "auto_submitted"
            elif is_online:
                status_val = "in_progress" if sprint_is_live else "not_started"
            else:
                status_val = "offline"
        else:
            if is_online:
                status_val = "in_progress" if sprint_is_live else "not_started"
            else:
                status_val = "offline"
            
        result.append({
            "id": t.id,
            "team_name": t.team_name,
            "leader_name": t.leader_name,
            "college": t.college or "N/A",
            "status": status_val,
            "is_online": is_online,
            "total_score": score,
            "strikes": strikes,
            "auto_submitted": auto_sub,
            "time_taken_seconds": time_taken
        })
        
    return {
        "total": len(result),
        "online_count": len(online_ids),
        "teams": result
    }


# Sprint Synchronization Controls
@router.post("/sprint/start", response_model=SprintActionResponse)
async def admin_start_sprint(
    duration_minutes: int = None,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin starts the sprint officially for all teams synchronously"""
    config = db.query(TestConfiguration).first()
    if not config:
        config = TestConfiguration(id=1)
        db.add(config)
    
    now = datetime.utcnow()
    duration = duration_minutes if duration_minutes and duration_minutes > 0 else (config.duration_minutes or 120)
    
    config.duration_minutes = duration
    config.global_start_time = now
    config.test_open_at = now
    config.test_close_at = now + timedelta(minutes=duration)
    config.synchronized_start = True
    config.updated_at = now
    
    # Transition currently connected lobby teams to IN_PROGRESS
    online_ids = get_online_team_ids()
    for tid in online_ids:
        session = db.query(TestSession).filter(TestSession.team_id == tid).first()
        if not session:
            session = TestSession(
                team_id=tid,
                test_started_at=now,
                status=TestStatus.IN_PROGRESS
            )
            db.add(session)
        elif session.status == TestStatus.NOT_STARTED:
            session.test_started_at = now
            session.status = TestStatus.IN_PROGRESS
    
    db.commit()
    db.refresh(config)
    
    return SprintActionResponse(
        success=True,
        message=f"Sprint started globally for {duration} minutes.",
        global_start_time=config.global_start_time,
        test_close_at=config.test_close_at,
        duration_minutes=duration
    )


@router.post("/sprint/stop", response_model=SprintActionResponse)
async def admin_stop_sprint(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin forcefully ends the sprint for all teams"""
    config = db.query(TestConfiguration).first()
    if not config:
        raise HTTPException(status_code=400, detail="Test configuration not found")
    
    now = datetime.utcnow()
    config.test_close_at = now
    config.updated_at = now
    
    # Auto-submit all active sessions
    active_sessions = db.query(TestSession).filter(
        TestSession.status == TestStatus.IN_PROGRESS
    ).all()
    
    for session in active_sessions:
        session.status = TestStatus.AUTO_SUBMITTED
        session.auto_submitted = True
        session.submitted_at = now
        if session.test_started_at:
            session.time_taken_seconds = int((now - session.test_started_at).total_seconds())
    
    # Recalculate leaderboard
    _recalculate_leaderboard_ranks(db)
    
    db.commit()
    
    return SprintActionResponse(
        success=True,
        message=f"Sprint stopped. {len(active_sessions)} active sessions auto-submitted.",
        global_start_time=config.global_start_time,
        test_close_at=config.test_close_at,
        duration_minutes=config.duration_minutes
    )


@router.post("/sprint/reset", response_model=SprintActionResponse)
async def admin_reset_sprint(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Reset sprint back to pre-start lobby state"""
    config = db.query(TestConfiguration).first()
    if not config:
        config = TestConfiguration(id=1)
        db.add(config)
    
    config.global_start_time = None
    config.test_open_at = None
    config.test_close_at = None
    config.updated_at = datetime.utcnow()
    
    # Reset all test sessions back to NOT_STARTED
    sessions = db.query(TestSession).all()
    for session in sessions:
        session.status = TestStatus.NOT_STARTED
        session.test_started_at = None
        session.submitted_at = None
        session.auto_submitted = False
        session.time_taken_seconds = 0
        session.total_score = 0
        session.easy_score = 0
        session.medium_score = 0
        session.hard_score = 0
        session.rank = None
    
    db.commit()
    
    return SprintActionResponse(
        success=True,
        message="Sprint reset back to lobby. All teams can now wait for new sprint start.",
        global_start_time=None,
        test_close_at=None,
        duration_minutes=config.duration_minutes
    )


@router.get("/sprint/status", response_model=SprintStatusResponse)
async def admin_get_sprint_status(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get real-time global sprint status"""
    config = db.query(TestConfiguration).first()
    now = datetime.utcnow()
    
    if not config or not config.global_start_time:
        return SprintStatusResponse(
            sprint_started=False,
            sprint_active=False,
            sprint_ended=False,
            time_remaining_seconds=0,
            duration_minutes=config.duration_minutes if config else 120,
            message="Sprint has not been started yet."
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
            message="Sprint is scheduled but not started."
        )
    elif now >= close_at:
        return SprintStatusResponse(
            sprint_started=True,
            sprint_active=False,
            sprint_ended=True,
            global_start_time=config.global_start_time,
            test_close_at=close_at,
            time_remaining_seconds=0,
            duration_minutes=duration,
            message="Sprint has ended."
        )
    else:
        remaining = int((close_at - now).total_seconds())
        return SprintStatusResponse(
            sprint_started=True,
            sprint_active=True,
            sprint_ended=False,
            global_start_time=config.global_start_time,
            test_close_at=close_at,
            time_remaining_seconds=max(0, remaining),
            duration_minutes=duration,
            message="Sprint is currently active."
        )



# Grade Override
@router.post("/grading/{submission_id}/override", response_model=GradeOverrideResponse)
async def override_grade(
    submission_id: int,
    override_data: GradeOverrideRequest,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Manually override submission grade"""
    grading_result = db.query(GradingResult).filter(
        GradingResult.submission_id == submission_id
    ).first()
    
    if not grading_result:
        raise HTTPException(status_code=404, detail="Grading result not found")
    
    # Store original marks
    if grading_result.original_marks is None:
        grading_result.original_marks = grading_result.marks_awarded
    
    original = grading_result.original_marks
    
    # Update marks
    grading_result.marks_awarded = override_data.marks_awarded
    grading_result.overridden_by_admin_id = current_admin.id
    grading_result.override_reason = override_data.reason
    grading_result.overridden_at = datetime.utcnow()
    
    # Get submission to find team
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    
    # Recalculate team total score
    from app.grading_service import GradingService
    GradingService._update_test_session_score(db, submission.team_id)
    
    # Recalculate ranks
    _recalculate_leaderboard_ranks(db)
    
    db.commit()
    
    return GradeOverrideResponse(
        submission_id=submission_id,
        original_marks=original,
        new_marks=override_data.marks_awarded,
        overridden_by=current_admin.username,
        overridden_at=grading_result.overridden_at,
        leaderboard_recalculated=True
    )


# Leaderboard
@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_admin_leaderboard(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get full leaderboard (admin view) sorted by Score DESC, then Timestamp ASC (earlier submissions rank higher)"""
    sessions = db.query(TestSession).filter(
        TestSession.status.in_([TestStatus.IN_PROGRESS, TestStatus.SUBMITTED, TestStatus.AUTO_SUBMITTED])
    ).all()
    
    raw_entries = []
    
    for session in sessions:
        team = db.query(Team).filter(Team.id == session.team_id).first()
        
        # Query latest final submission time
        last_sub_time = db.query(func.max(Submission.submitted_at)).filter(
            Submission.team_id == session.team_id,
            Submission.is_final == True
        ).scalar()
        
        # Effective timestamp for tie-breaker:
        eff_dt = session.submitted_at or last_sub_time or session.test_started_at or datetime.max
        
        # Calculate precise elapsed time
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


@router.get("/queue/stats", response_model=QueueStatsResponse)
async def get_queue_stats(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get grading queue statistics"""
    stats = GradingQueue.get_stats(db)
    
    # Calculate average grading time (mock for now)
    avg_time = 5.0
    
    return QueueStatsResponse(
        queue_depth=stats["pending"],
        grading_in_progress=stats["processing"],
        completed_today=0,  # Would need to track this
        failed_today=stats["failed"],
        average_grading_time_seconds=avg_time
    )


# Proctoring Alerts
@router.get("/proctoring/alerts", response_model=ProctoringAlertsListResponse)
async def get_proctoring_alerts(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get live proctoring violations and anti-cheat alerts"""
    violations = db.query(ProctoringViolation).order_by(
        desc(ProctoringViolation.timestamp)
    ).limit(50).all()
    
    total = db.query(ProctoringViolation).count()
    
    return ProctoringAlertsListResponse(
        alerts=[
            ProctoringAlertItem(
                id=v.id,
                team_id=v.team_id,
                team_name=v.team_name,
                leader_phone=v.leader_phone,
                violation_type=v.violation_type,
                strike_count=v.strike_count,
                action_taken=v.action_taken,
                timestamp=v.timestamp
            )
            for v in violations
        ],
        total_violations=total
    )


@router.post("/proctoring/clear")
async def clear_proctoring_alerts(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Clear all proctoring alerts"""
    db.query(ProctoringViolation).delete()
    db.commit()
    return {"success": True, "message": "Proctoring alerts cleared"}


@router.post("/teams/{team_id}/unlock")
async def unlock_team_session(
    team_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Grant admin permission & unlock an auto-submitted team session"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Reset lockouts on Team model
    team.locked_until = None
    team.failed_login_attempts = 0
    
    # Reset test session to IN_PROGRESS
    test_session = db.query(TestSession).filter(TestSession.team_id == team_id).first()
    if test_session:
        test_session.auto_submitted = False
        test_session.status = TestStatus.IN_PROGRESS
    
    # Log the permission grant
    violation = ProctoringViolation(
        team_id=team.id,
        team_name=team.team_name,
        leader_phone="N/A",
        violation_type="Admin Permission Granted (Re-entry Allowed)",
        strike_count=0,
        action_taken="Session Unlocked & Active"
    )
    db.add(violation)
    db.commit()
    
    return {
        "success": True,
        "team_id": team.id,
        "team_name": team.team_name,
        "status": "in_progress",
        "message": f"Team '{team.team_name}' has been granted permission. They can now log in and continue."
    }


@router.post("/teams/{team_id}/reset")
async def reset_team_session(
    team_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Reset a specific team's test session back to NOT STARTED"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    test_session = db.query(TestSession).filter(TestSession.team_id == team_id).first()
    if test_session:
        test_session.status = TestStatus.NOT_STARTED
        test_session.test_started_at = None
        test_session.submitted_at = None
        test_session.time_taken_seconds = None
        test_session.auto_submitted = False
    
    # Clear their proctoring strikes
    db.query(ProctoringViolation).filter(ProctoringViolation.team_id == team_id).delete()
    team.locked_until = None
    team.failed_login_attempts = 0
    db.commit()
    
    return {"success": True, "message": f"Session for '{team.team_name}' reset to NOT STARTED."}


@router.post("/teams/{team_id}/force-submit")
async def force_submit_team_session(
    team_id: int,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Force submit a team's test session"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    test_session = db.query(TestSession).filter(TestSession.team_id == team_id).first()
    if not test_session:
        test_session = TestSession(
            team_id=team.id,
            status=TestStatus.AUTO_SUBMITTED,
            submitted_at=datetime.utcnow(),
            auto_submitted=True
        )
        db.add(test_session)
    else:
        test_session.status = TestStatus.AUTO_SUBMITTED
        test_session.auto_submitted = True
        test_session.submitted_at = datetime.utcnow()
        if test_session.test_started_at:
            test_session.time_taken_seconds = int((test_session.submitted_at - test_session.test_started_at).total_seconds())
    
    db.commit()
    return {"success": True, "message": f"Team '{team.team_name}' test session force-submitted."}


@router.post("/proctoring/simulate")
async def simulate_proctoring_alert(
    strike: int = 1,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Simulate a test proctoring violation for testing alert audio & visual feed"""
    first_team = db.query(Team).first()
    team_name = first_team.team_name if first_team else "Test Demo Team"
    team_id = first_team.id if first_team else 999
    
    reasons = [
        "Fullscreen Exit (Simulated)",
        "Tab Switch / Window Focus Lost (Simulated)",
        "DevTools Inspector Attempt (Simulated)"
    ]
    reason = reasons[(strike - 1) % len(reasons)]
    action = "auto_submitted" if strike >= 3 else f"warning_{strike}"
    
    violation = ProctoringViolation(
        team_id=team_id,
        team_name=f"[TEST] {team_name}",
        leader_phone="9999999999",
        violation_type=reason,
        strike_count=strike,
        action_taken=action
    )
    db.add(violation)
    db.commit()
    db.refresh(violation)
    
    return {
        "success": True,
        "message": f"Simulated Strike {strike}/3 logged for '{team_name}'",
        "alert": {
            "id": violation.id,
            "team_name": violation.team_name,
            "violation_type": violation.violation_type,
            "strike_count": violation.strike_count,
            "action_taken": violation.action_taken
        }
    }


# Helper functions
def _recalculate_leaderboard_ranks(db: Session):
    """Recalculate ranks for all teams using Score DESC and Timestamp ASC"""
    sessions = db.query(TestSession).filter(
        TestSession.status.in_([TestStatus.IN_PROGRESS, TestStatus.SUBMITTED, TestStatus.AUTO_SUBMITTED])
    ).all()
    
    raw = []
    for s in sessions:
        last_sub_time = db.query(func.max(Submission.submitted_at)).filter(
            Submission.team_id == s.team_id,
            Submission.is_final == True
        ).scalar()
        eff_dt = s.submitted_at or last_sub_time or s.test_started_at or datetime.max
        time_taken = s.time_taken_seconds or 0
        raw.append((s, s.total_score or 0, eff_dt, time_taken, s.team_id))
        
    raw.sort(key=lambda x: (-x[1], x[2], x[3], x[4]))
    
    for rank, (session, _, _, _, _) in enumerate(raw, 1):
        session.rank = rank
    
    try:
        db.commit()
    except Exception:
        db.rollback()


def _format_time(seconds: int) -> str:
    """Format seconds to human-readable time"""
    if seconds is None:
        return "N/A"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"
