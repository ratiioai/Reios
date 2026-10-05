"""
Verify Firebase Authentication ID tokens without a service-account key.

Firebase ID tokens are RS256 JWTs signed by Google. The public certificates are published at
CERTS_URL; we check the signature, audience (project id), issuer, expiry and that the account's
email is verified. See https://firebase.google.com/docs/auth/admin/verify-id-tokens#verify_id_tokens_using_a_third-party_jwt_library
"""
import json
import re
import threading
import time
import urllib.request

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.config import settings

CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"

_lock = threading.Lock()
_cache = {"certs": {}, "expires": 0.0}


def _certs() -> dict:
    """Google's current signing certificates {kid: PEM}, cached for as long as Google says."""
    with _lock:
        if _cache["certs"] and time.time() < _cache["expires"]:
            return _cache["certs"]
        try:
            with urllib.request.urlopen(CERTS_URL, timeout=10) as res:
                certs = json.loads(res.read())
                m = re.search(r"max-age=(\d+)", res.headers.get("Cache-Control", ""))
        except Exception:
            if _cache["certs"]:
                return _cache["certs"]  # keep working through a brief outage with the last good keys
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                                "Can't reach Google to check the sign-in. Check this server's internet connection")
        _cache["certs"] = certs
        _cache["expires"] = time.time() + (int(m.group(1)) if m else 3600)
        return certs


def verify_id_token(id_token: str) -> dict:
    project = settings.FIREBASE_PROJECT_ID
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Firebase sign-in isn't set up on this server")
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Firebase sign-in could not be verified. Try again")
    try:
        kid = jwt.get_unverified_header(id_token).get("kid")
    except JWTError:
        raise invalid
    cert = _certs().get(kid)
    if not cert:
        raise invalid
    try:
        claims = jwt.decode(id_token, cert, algorithms=["RS256"], audience=project,
                            issuer=f"https://securetoken.google.com/{project}",
                            options={"verify_at_hash": False})
    except JWTError:
        raise invalid
    if not claims.get("sub") or claims.get("auth_time", 0) > time.time() + 60:
        raise invalid
    if not claims.get("email"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This Firebase account has no email address")
    if not claims.get("email_verified"):
        # Otherwise anyone could register an unverified Firebase account using the admin's address
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Verify your email first: open the link Firebase sent you, then sign in again")
    return claims
