"""
Authentication and role-based access for the Reios module.
"""
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import create_access_token, decode_token, hash_password, needs_rehash, verify_password
from app.config import settings
from app.database import get_db
from app.reios.models import College, Role, User

bearer_scheme = HTTPBearer(auto_error=False)

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 10


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite returns naive datetimes; treat them as UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def generate_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    # Avoid characters that are easy to misread on a printed credentials sheet
    alphabet = "".join(c for c in alphabet if c not in "0O1lI")
    return "".join(secrets.choice(alphabet) for _ in range(length))


def issue_token(user: User) -> str:
    return create_access_token({
        "sub": str(user.id),
        "role": f"reios_{user.role.value}",
        "tv": user.token_version,
        "cid": user.college_id,
    })


def register_failed_login(db: Session, user: User) -> None:
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= MAX_FAILED_LOGINS:
        user.locked_until = utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
        user.failed_login_attempts = 0
    db.commit()


def check_login(db: Session, user: Optional[User], password: str) -> User:
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if not user:
        raise invalid
    locked_until = as_utc(user.locked_until)
    if locked_until and locked_until > utcnow():
        raise HTTPException(status.HTTP_423_LOCKED,
                            f"Too many failed attempts. Try again after {locked_until.strftime('%H:%M UTC')}")
    if settings.FIREBASE_PROJECT_ID and user.role == Role.SUPER_ADMIN:
        raise invalid  # looks exactly like a wrong password; these accounts sign in elsewhere
    if not verify_password(password, user.hashed_password):
        register_failed_login(db, user)
        raise invalid
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
    check_org_access(user)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = utcnow()
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(password)
    db.commit()
    return user


def claim_single_login_session(db: Session, user: User) -> None:
    """Track that this student/team is now signed in (used for the admin's live login status), and,
    when the college/event enforces one login at a time, refuse this login if an earlier session is
    still within its window."""
    if user.role != Role.STUDENT:
        return
    enforce = bool(user.college and user.college.single_login)
    expires_at = as_utc(user.active_session_expires_at)
    if enforce and expires_at and expires_at > utcnow():
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This account is already logged in elsewhere. Log out there first, or wait for "
                            "that session to expire.")
    user.active_session_expires_at = utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    db.commit()


def release_login_session(db: Session, user: User) -> None:
    user.active_session_expires_at = None
    db.commit()


def needs_password_change(user: User) -> bool:
    """Event organizers hand out the passwords, so event students keep them; everyone else changes a temporary one."""
    if not user.must_change_password:
        return False
    org = user.college if user.college_id else None
    return not (user.role == Role.STUDENT and org is not None and org.org_type == "event")


def check_org_access(user: User) -> None:
    org = user.college if user.college_id else None
    if org is None:
        return
    noun = "event" if org.org_type == "event" else "college"
    if not org.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Your {noun}'s account is disabled")
    until = as_utc(org.access_until)
    if until and until < utcnow():
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"Your {noun}'s access ended on {until.strftime('%d %b %Y')}. "
                            "Contact the Reios team to renew")


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    payload = decode_token(credentials.credentials)
    role = payload.get("role", "")
    if not role.startswith("reios_"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = db.get(User, int(payload.get("sub", 0)))
    if not user or not user.is_active or user.token_version != payload.get("tv"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please log in again")
    check_org_access(user)
    # FastAPI runs each dependency and the route on separate worker-thread hops. Ending this read
    # transaction hands the pooled connection back while the request waits for its next hop;
    # holding it let a burst of requests (e.g. 300 teams pressing Start) take every connection
    # while all worker threads waited for one, stalling until the pool's 30 s timeout.
    db.commit()
    return user


def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.SUPER_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Super admin access required")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in (Role.SUPER_ADMIN, Role.COLLEGE_ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


def require_student(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.STUDENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Student access required")
    return user


def scoped_college_id(
    college_id: Optional[int] = Query(None, description="Super admin only: college to act on"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> int:
    """
    College that an admin request operates on.
    College admins are always pinned to their own college; super admins pick one with ?college_id=.
    """
    if user.role == Role.COLLEGE_ADMIN:
        return user.college_id
    if college_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "college_id query parameter is required for super admin")
    if not db.get(College, college_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "College not found")
    return college_id


def bank_scope(
    college_id: Optional[int] = Query(None),
    user: User = Depends(require_admin),
) -> Optional[int]:
    """
    Question bank scope. College admins see their college's questions plus the global bank.
    Super admins work on the global bank unless they pass ?college_id=.
    """
    if user.role == Role.COLLEGE_ADMIN:
        return user.college_id
    return college_id


def ensure_super_admin(db: Session) -> None:
    """Create the first super admin from environment variables if none exists."""
    import logging
    import os
    logger = logging.getLogger("reios")
    if settings.FIREBASE_PROJECT_ID:
        # Firebase mode: every address in SUPER_ADMIN_EMAIL (comma-separated) is a super admin.
        # Firebase checks the password, so the local one is random and never used.
        for email in {e.strip().lower() for e in os.getenv("SUPER_ADMIN_EMAIL", "").split(",") if e.strip()}:
            existing = db.query(User).filter(func.lower(User.email) == email).first()
            if existing is None:
                db.add(User(role=Role.SUPER_ADMIN, name="Super Admin", email=email,
                            hashed_password=hash_password(secrets.token_urlsafe(32)), must_change_password=False))
                logger.info(f"Reios super admin added for Firebase sign-in: {email}")
            elif existing.role != Role.SUPER_ADMIN:
                logger.error(f"{email} is in SUPER_ADMIN_EMAIL but already belongs to a {existing.role.value}")
        db.commit()
        return
    if db.query(User).filter(User.role == Role.SUPER_ADMIN).first():
        return
    email = os.getenv("SUPER_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("SUPER_ADMIN_PASSWORD", "")
    if not email or not password:
        logger.warning("No Reios super admin exists. Set SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD in .env "
                       "or run: python create_super_admin.py")
        return
    if len(password) < 8 and settings.ENVIRONMENT == "production":
        logger.error("SUPER_ADMIN_PASSWORD must be at least 8 characters")
        return
    db.add(User(role=Role.SUPER_ADMIN, name="Super Admin", email=email,
                hashed_password=hash_password(password), must_change_password=False))
    db.commit()
    logger.info(f"Reios super admin created: {email}")
