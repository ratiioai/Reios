"""
Reios login and account endpoints, shared by all roles.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.config import settings
from app.database import get_db
from app.reios.features import branding, has_feature, logo_image
from app.reios.firebase_auth import verify_id_token
from app.reios.models import College, Role, User
from app.reios.security import (
    check_login, claim_single_login_session, get_current_user, issue_token, needs_password_change,
    release_login_session, utcnow,
)

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
        "must_change_password": needs_password_change(user),
        "college": {"id": user.college.id, "name": user.college.name, "code": user.college.code,
                    "org_type": user.college.org_type, "features": user.college.features or [],
                    "branding": branding(user.college)}
        if user.college else None,
    }


MAX_ID_CANDIDATES = 20  # bounds the password checks one sign-in can trigger


def _find_by_id_and_password(db: Session, identifier: str, password: str) -> Optional[User]:
    """
    Sign in with a roll number / team ID alone. IDs repeat between colleges and events, so when several
    accounts share the ID, the password decides. Only if two of them also share the password is the
    college / event code needed.
    """
    candidates = db.query(User).filter(User.role == Role.STUDENT,
                                       func.lower(User.roll_no) == identifier.lower()).limit(MAX_ID_CANDIDATES).all()
    if len(candidates) <= 1:
        return candidates[0] if candidates else None  # check_login verifies and counts failures as usual
    matches = [u for u in candidates if verify_password(password, u.hashed_password)]
    if len(matches) > 1:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "More than one account uses this ID. Enter your college or event code as well")
    # No match: a wrong password. Don't count it against any one of them, as we can't tell whose it was.
    if not matches:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return matches[0]


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
        user = _find_by_id_and_password(db, identifier, body.password)

    user = check_login(db, user, body.password)
    claim_single_login_session(db, user)
    return {"access_token": issue_token(user), "token_type": "bearer", "user": user_payload(user)}


class FirebaseLoginRequest(BaseModel):
    id_token: str = Field(..., min_length=20, max_length=8192)


@router.get("/branding")
def org_branding(code: str = Query(..., min_length=1, max_length=32), db: Session = Depends(get_db)):
    """Public: logo and colour for an organization code, so the sign-in page can show them."""
    org = db.query(College).filter(func.lower(College.code) == code.strip().lower(), College.is_active.is_(True)).first()
    return branding(org)


@router.get("/logo/{code}")
def org_logo(code: str = Path(..., min_length=1, max_length=32), db: Session = Depends(get_db)):
    """Public: an organization's logo image (only when its branding add-on is on). Cacheable: the link
    carries a version of the image, so a new logo gets a new link."""
    org = db.query(College).filter(func.lower(College.code) == code.strip().lower(), College.is_active.is_(True)).first()
    image = logo_image(org) if org and has_feature(org, "branding") else None
    if not image:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No logo")
    return Response(content=image[0], media_type=image[1],
                    headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"})


@router.get("/config")
def auth_config():
    """What the sign-in page should offer."""
    return {"google_signin": bool(settings.FIREBASE_PROJECT_ID)}


@router.post("/firebase")
def firebase_login(body: FirebaseLoginRequest, db: Session = Depends(get_db)):
    """Super admin sign-in: a Firebase ID token for an email listed as a super admin."""
    claims = verify_id_token(body.id_token)
    email = claims["email"].strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email, User.role == Role.SUPER_ADMIN).first()
    if not user:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account isn't allowed to sign in here")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
    # The first Firebase account to sign in owns this super admin; a different account with the same
    # email (e.g. after the Firebase user was deleted and recreated) is refused.
    if user.firebase_uid and user.firebase_uid != claims["sub"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account isn't allowed to sign in here")
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


@router.post("/logout")
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Free up this account's login slot immediately, instead of waiting for it to lapse on its own."""
    release_login_session(db, user)
    return {"message": "Logged out"}


@router.post("/logout-all")
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.token_version += 1
    db.commit()
    return {"message": "Logged out from all devices"}
