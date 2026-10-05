"""
Configuration, read from environment variables (and backend/.env).
"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
SECRET_KEY_FILE = BASE_DIR / ".secret_key"


def _secret_key() -> str:
    """
    SECRET_KEY from the environment, else one generated once and kept in backend/.secret_key.
    Every worker process must sign tokens with the same key, so it can't be random per process.
    """
    key = os.getenv("SECRET_KEY", "").strip()
    if key:
        return key
    if SECRET_KEY_FILE.exists():
        return SECRET_KEY_FILE.read_text().strip()
    key = secrets.token_urlsafe(48)
    try:
        with open(SECRET_KEY_FILE, "x") as f:  # "x": if another worker wrote it first, use theirs
            f.write(key)
    except FileExistsError:
        return SECRET_KEY_FILE.read_text().strip()
    return key


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{BASE_DIR / 'coding_test.db'}"
    # Hosts (Render, Railway, Heroku) hand out postgres:// URLs; use the psycopg 3 driver for them
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class Settings(BaseSettings):
    DATABASE_URL: str = _database_url()
    # Concurrent request handlers (and database connections). Size it to the largest class writing at once.
    WORKER_THREADS: int = int(os.getenv("WORKER_THREADS", "120"))
    # bcrypt cost. 10 is OWASP's minimum and ~4x cheaper than 12, which matters when a whole lab signs in at once
    BCRYPT_ROUNDS: int = int(os.getenv("BCRYPT_ROUNDS", "10"))

    SECRET_KEY: str = _secret_key()
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

    # Firebase project id (e.g. reios-51093). When set, super admins sign in with Firebase only.
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "").strip()

    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


settings = Settings()

if settings.ENVIRONMENT == "production" and len(settings.SECRET_KEY) < 32:
    raise ValueError("SECRET_KEY must be at least 32 characters in production")
