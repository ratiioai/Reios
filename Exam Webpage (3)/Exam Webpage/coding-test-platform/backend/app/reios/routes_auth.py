"""
Reios login and account endpoints, shared by all roles.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.config import settings
from app.database import get_db
from app.reios.firebase_auth import verify_id_token
from app.reios.models import College, Role, User
from app.reios.security import check_login, get_current_user, issue_token, utcnow

router = APIRouter(prefix="/api/reios/auth", tags=["Reios Auth"])


class LoginRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=255, description="Email, or roll number for students")
    password: str = Field(..., min_length=1, max_length=128)
    college_code: Optional[str] = Field(None, max_length=32, description="Required when logging in with a roll number")


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


def user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "role": user.role.value,
        "name": user.name,
        "email": user.email,
        "roll_no": user.roll_no,
        "branch": user.branch,
        "section": user.section,
        "batch_year": user.batch_year,
        "phone": user.phone,
        "must_change_password": user.must_change_password,
        "college": {"id": user.college.id, "name": user.college.name, "code": user.college.code}
        if user.college else None,
    }


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    identifier = body.identifier.strip()
    user = None
    if body.college_code:
        college = db.query(College).filter(func.lower(College.code) == body.college_code.strip().lower()).first()
        if college:
            user = db.query(User).filter(
                User.college_id == college.id,
                func.lower(User.roll_no) == identifier.lower(),
            ).first()
            if not user and "@" in identifier:
                user = db.query(User).filter(User.college_id == college.id,
                                             func.lower(User.email) == identifier.lower()).first()
    elif "@" in identifier:
        user = db.query(User).filter(func.lower(User.email) == identifier.lower()).first()
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Enter your college code to log in with a roll number")

    user = check_login(db, user, body.password)
    return {"access_token": issue_token(user), "token_type": "bearer", "user": user_payload(user)}


class FirebaseLoginRequest(BaseModel):
    id_token: str = Field(..., min_length=20, max_length=8192)


@router.get("/config")
def auth_config():
    """What the sign-in page should offer."""
    return {"firebase_super_admin": bool(settings.FIREBASE_PROJECT_ID)}


@router.post("/firebase")
def firebase_login(body: FirebaseLoginRequest, db: Session = Depends(get_db)):
    """Super admin sign-in: a Firebase ID token for an email listed as a super admin."""
    claims = verify_id_token(body.id_token)
    email = claims["email"].strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email, User.role == Role.SUPER_ADMIN).first()
    if not user:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"{email} isn't a Reios super admin. Add it to SUPER_ADMIN_EMAIL in backend/.env "
                            "and restart the server")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
    # The first Firebase account to sign in owns this super admin; a different account with the same
    # email (e.g. after the Firebase user was deleted and recreated) is refused.
    if user.firebase_uid and user.firebase_uid != claims["sub"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "This super admin is linked to a different Firebase account")
    user.firebase_uid = claims["sub"]
    user.last_login_at = utcnow()
    user.failed_login_attempts = 0
    db.commit()
    return {"access_token": issue_token(user), "token_type": "bearer", "user": user_payload(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_payload(user)


@router.post("/change-password")
def change_password(body: ChangePasswordRequest, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if body.current_password == body.new_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "New password must be different")
    user.hashed_password = hash_password(body.new_password)
    user.must_change_password = False
    user.token_version += 1  # log out other sessions
    db.commit()
    return {"access_token": issue_token(user), "token_type": "bearer", "user": user_payload(user)}


@router.post("/logout-all")
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.token_version += 1
    db.commit()
    return {"message": "Logged out from all devices"}
