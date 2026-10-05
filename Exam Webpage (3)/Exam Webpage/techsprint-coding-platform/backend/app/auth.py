"""
Authentication utilities
Handles password hashing, JWT tokens, and login verification
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Admin, Team

# Bearer token extraction
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain_password: str) -> str:
    """Hash a plain text password using bcrypt"""
    # Truncate to 72 bytes (bcrypt limit)
    password_bytes = plain_password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        password_bytes = plain_password.encode('utf-8')[:72]
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def hash_phone(phone: str) -> str:
    """
    Hash a phone number for storage
    Treat phone as a password - hash it the same way
    """
    return hash_password(phone)


def verify_phone(plain_phone: str, hashed_phone: str) -> bool:
    """Verify a phone number against its hash"""
    return verify_password(plain_phone, hashed_phone)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# FastAPI Dependencies

def _extract_token(credentials: Optional[HTTPAuthorizationCredentials]) -> str:
    """Extract token from Authorization header"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Admin:
    """Get current authenticated admin"""
    token = _extract_token(credentials)
    payload = decode_token(token)
    
    username: str = payload.get("sub")
    role: str = payload.get("role")
    
    if not username or role != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin account not found or inactive"
        )
    
    return admin


def get_current_team(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Team:
    """Get current authenticated team"""
    token = _extract_token(credentials)
    payload = decode_token(token)
    
    team_id: int = payload.get("team_id")
    role: str = payload.get("role")
    
    if not team_id or role != "team":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team or not team.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Team account not found or inactive"
        )
    
    # Check if locked due to failed login attempts
    if team.locked_until and team.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account locked until {team.locked_until.isoformat()}"
        )
    
    return team


def authenticate_admin(db: Session, username: str, password: str) -> Optional[Admin]:
    """Authenticate an admin user"""
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin or not admin.is_active:
        return None
    
    if not verify_password(password, admin.hashed_password):
        return None
    
    return admin


def authenticate_team(db: Session, team_name: str, leader_phone: str) -> Optional[Team]:
    """
    Authenticate a team
    team_name is case-insensitive and trimmed
    Supports identically named teams by matching correct leader_phone hash
    """
    clean_name = team_name.strip().lower()
    clean_phone = leader_phone.strip()
    
    # Find all teams by name (case-insensitive)
    from sqlalchemy import func
    candidates = db.query(Team).filter(
        func.lower(func.trim(Team.team_name)) == clean_name
    ).all()
    
    if not candidates:
        return None
    
    # Find matching team candidate by verifying phone hash
    for team in candidates:
        if not team.is_active:
            continue
        
        # Check if locked
        if team.locked_until and team.locked_until > datetime.utcnow():
            continue
        
        if verify_phone(clean_phone, team.leader_phone_hash):
            # Reset failed attempts on successful login
            if team.failed_login_attempts > 0:
                team.failed_login_attempts = 0
                team.locked_until = None
                db.commit()
            return team
    
    # If no candidate matched, increment failed attempts on candidates
    for team in candidates:
        team.failed_login_attempts += 1
        if team.failed_login_attempts >= settings.LOGIN_RATE_LIMIT:
            team.locked_until = datetime.utcnow() + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
    db.commit()
    
    return None


def create_admin_user(db: Session, username: str, password: str, email: str) -> Admin:
    """Create an admin user"""
    admin = Admin(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        is_active=True
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin
