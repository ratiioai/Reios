import hashlib
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.auth import authenticate_admin, authenticate_team, create_access_token, bearer_scheme, decode_token, hash_phone
from app.presence import record_team_heartbeat
from app.database import get_db
from app.models import (
    Team, Admin, TestSession, TestStatus, TestConfiguration,
    ProctoringViolation, Question, TeamQuestionAssignment, UsedQuestionSet
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


# Request/Response Models
class AdminLoginRequest(BaseModel):
    username: str
    password: str


class TeamLoginRequest(BaseModel):
    team_name: str
    leader_phone: str


class TeamRegisterRequest(BaseModel):
    team_name: str
    leader_name: str
    leader_phone: str
    college: Optional[str] = "General"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_info: dict


# Helper dependency for token verification (either admin or team)
def get_current_user_any(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db)
):
    """Get current user (admin or team)"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        payload = decode_token(credentials.credentials)
        role = payload.get("role")
        
        if role == "admin":
            from app.models import Admin
            username = payload.get("sub")
            user = db.query(Admin).filter(Admin.username == username).first()
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            return {"role": "admin", "username": user.username, "id": user.id}
        
        elif role == "team":
            from app.models import Team
            team_id = payload.get("team_id")
            user = db.query(Team).filter(Team.id == team_id).first()
            if not user:
                raise HTTPException(status_code=401, detail="Team not found")
            return {
                "role": "team",
                "team_id": user.id,
                "team_name": user.team_name
            }
        
        else:
            raise HTTPException(status_code=401, detail="Invalid token")
    
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


# Routes
@router.post("/admin/login", response_model=TokenResponse)
async def admin_login(
    credentials: AdminLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Admin login endpoint
    Returns JWT token for admin access
    """
    admin = authenticate_admin(db, credentials.username, credentials.password)
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    
    # Create JWT token
    token_data = {
        "sub": admin.username,
        "role": "admin",
        "admin_id": admin.id,
    }
    access_token = create_access_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role="admin",
        user_info={
            "username": admin.username,
            "email": admin.email,
        }
    )


@router.post("/team/login", response_model=TokenResponse)
async def team_login(
    credentials: TeamLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Team login endpoint
    Uses team_name (case-insensitive) + leader_phone (hashed comparison)
    Implements rate limiting (5 attempts → 15 min lockout)
    """
    team = authenticate_team(db, credentials.team_name, credentials.leader_phone)
    
    if not team:
        # Check if it's a lockout situation
        locked_team = db.query(Team).filter(
            func.lower(func.trim(Team.team_name)) == credentials.team_name.strip().lower(),
            Team.locked_until != None,
            Team.locked_until > datetime.utcnow()
        ).first()
        
        if locked_team:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account locked due to too many failed login attempts. Try again after {locked_team.locked_until.strftime('%H:%M:%S')}",
            )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid team name or phone number",
        )
    
    # Check if team's test session was auto-submitted due to proctoring strikes or locked
    test_session = db.query(TestSession).filter(TestSession.team_id == team.id).first()
    if test_session and (test_session.auto_submitted or test_session.status == TestStatus.AUTO_SUBMITTED):
        # Log re-login attempt alert in admin proctoring feed
        violation = ProctoringViolation(
            team_id=team.id,
            team_name=team.team_name,
            leader_phone=credentials.leader_phone,
            violation_type="Re-Login Attempt After 3 Alerts (Auto-Submitted)",
            strike_count=3,
            action_taken="Blocked (Awaiting Admin Unlock)"
        )
        db.add(violation)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your test session was auto-submitted after 3 proctoring alerts. Re-entry requires administrator permission from the Command Center."
        )

    # Initialize or update test session
    config = db.query(TestConfiguration).first()
    now = datetime.utcnow()
    sprint_is_live = bool(config and config.global_start_time and now >= config.global_start_time and (not config.test_close_at or now < config.test_close_at))
    
    if not test_session:
        test_session = TestSession(
            team_id=team.id,
            status=TestStatus.IN_PROGRESS if sprint_is_live else TestStatus.NOT_STARTED,
            test_started_at=config.global_start_time if sprint_is_live else None
        )
        db.add(test_session)
    else:
        if test_session.status == TestStatus.NOT_STARTED and sprint_is_live:
            test_session.status = TestStatus.IN_PROGRESS
            test_session.test_started_at = config.global_start_time
            
    db.commit()

    # Create JWT token
    token_data = {
        "sub": team.team_name,
        "role": "team",
        "team_id": team.id,
    }
    access_token = create_access_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role="team",
        user_info={
            "team_id": team.id,
            "team_name": team.team_name,
            "leader_name": team.leader_name,
            "college": team.college,
        }
    )


@router.post("/team/register", response_model=TokenResponse)
@router.post("/team/signup", response_model=TokenResponse)
async def team_register(
    reg: TeamRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Instant Team Registration / Sign-Up.
    Allocates a 25-question set immediately (SET1 to SET15 balanced allocation)
    and returns a JWT token for instant login into the lobby / contest.
    """
    clean_name = reg.team_name.strip()
    clean_leader = reg.leader_name.strip()
    clean_phone = reg.leader_phone.strip()
    clean_college = (reg.college or "").strip() or "General"

    if not clean_name or not clean_leader or not clean_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team Name, Leader Name, and Phone Number are required."
        )

    # Check if team already exists (case-insensitive)
    existing = db.query(Team).filter(
        func.lower(func.trim(Team.team_name)) == clean_name.lower()
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team '{clean_name}' is already registered. Please log in directly with your leader phone number."
        )

    # Create new Team
    new_team = Team(
        team_name=clean_name,
        leader_name=clean_leader,
        leader_phone_hash=hash_phone(clean_phone),
        college=clean_college,
        is_active=True,
        failed_login_attempts=0
    )
    db.add(new_team)
    db.flush()  # Populates new_team.id

    # Allocate 25-Question Set (SET1 to SET15 across 14 sets)
    set_labels = ["SET1", "SET2", "SET3", "SET4", "SET5", "SET6", "SET7", "SET8", "SET10", "SET11", "SET12", "SET13", "SET14", "SET15"]
    set_idx = (new_team.id - 1) % len(set_labels)
    assigned_set_name = set_labels[set_idx]

    start_q_id = set_idx * 25 + 1
    end_q_id = (set_idx + 1) * 25

    questions = db.query(Question).filter(
        Question.id >= start_q_id,
        Question.id <= end_q_id
    ).order_by(Question.id).all()

    for pos, q in enumerate(questions, start=1):
        assignment = TeamQuestionAssignment(
            team_id=new_team.id,
            question_id=q.id,
            position=pos
        )
        db.add(assignment)

    set_hash = hashlib.sha256(f"{new_team.id}_{assigned_set_name}".encode()).hexdigest()
    used_set = UsedQuestionSet(set_hash=set_hash, team_id=new_team.id)
    db.add(used_set)

    # Initialize Test Session
    config = db.query(TestConfiguration).first()
    now = datetime.utcnow()
    sprint_is_live = bool(config and config.global_start_time and now >= config.global_start_time and (not config.test_close_at or now < config.test_close_at))

    test_session = TestSession(
        team_id=new_team.id,
        status=TestStatus.IN_PROGRESS if sprint_is_live else TestStatus.NOT_STARTED,
        test_started_at=config.global_start_time if (sprint_is_live and config) else None,
        total_score=0,
        easy_score=0,
        medium_score=0,
        hard_score=0,
        time_taken_seconds=0
    )
    db.add(test_session)
    db.commit()
    db.refresh(new_team)

    # Record online presence
    record_team_heartbeat(new_team.id)

    # Create Activity Log in proctoring / admin feed
    violation = ProctoringViolation(
        team_id=new_team.id,
        team_name=new_team.team_name,
        leader_phone=clean_phone,
        violation_type="New Team Registered",
        strike_count=0,
        action_taken=f"Allotted {assigned_set_name} (25 Questions)"
    )
    db.add(violation)
    db.commit()

    # Create JWT access token
    token_data = {
        "sub": new_team.team_name,
        "role": "team",
        "team_id": new_team.id,
    }
    access_token = create_access_token(token_data)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role="team",
        user_info={
            "team_id": new_team.id,
            "team_name": new_team.team_name,
            "leader_name": new_team.leader_name,
            "college": new_team.college,
            "assigned_set": assigned_set_name
        }
    )



@router.get("/verify")
async def verify_token(
    current_user = Depends(get_current_user_any)
):
    """
    Verify if current token is valid
    Works for both admin and team tokens
    """
    return {
        "valid": True,
        "user": current_user
    }
