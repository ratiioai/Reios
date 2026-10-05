"""
Application configuration
Loads from environment variables
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env file
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/coding_test_db")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    
    # Admin
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@codingtest.local")
    
    # Test Configuration
    DEFAULT_TEST_DURATION_MINUTES: int = int(os.getenv("DEFAULT_TEST_DURATION_MINUTES", "120"))
    EASY_QUESTIONS_PER_TEST: int = int(os.getenv("EASY_QUESTIONS_PER_TEST", "10"))
    MEDIUM_QUESTIONS_PER_TEST: int = int(os.getenv("MEDIUM_QUESTIONS_PER_TEST", "10"))
    HARD_QUESTIONS_PER_TEST: int = int(os.getenv("HARD_QUESTIONS_PER_TEST", "5"))
    EASY_MARKS: int = int(os.getenv("EASY_MARKS", "5"))
    MEDIUM_MARKS: int = int(os.getenv("MEDIUM_MARKS", "10"))
    HARD_MARKS: int = int(os.getenv("HARD_MARKS", "20"))
    
    # Code Execution
    CODE_EXECUTION_API: str = os.getenv("CODE_EXECUTION_API", "https://emkc.org/api/v2/piston")
    CODE_EXECUTION_TIMEOUT_SECONDS: int = int(os.getenv("CODE_EXECUTION_TIMEOUT_SECONDS", "10"))
    PISTON_API_URL: str = os.getenv("PISTON_API_URL", "https://emkc.org/api/v2/piston")
    PISTON_RATE_LIMIT: int = int(os.getenv("PISTON_RATE_LIMIT", "10"))
    
    # Rate Limiting
    LOGIN_RATE_LIMIT: int = int(os.getenv("LOGIN_RATE_LIMIT", "50"))
    LOGIN_LOCKOUT_MINUTES: int = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "1"))
    
    # CORS
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
    
    # Application
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # Paths
    BASE_DIR: Path = BASE_DIR
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    EXPORT_DIR: Path = BASE_DIR / "exports"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._validate_settings()
        self._ensure_directories()
    
    def _validate_settings(self):
        """Validate critical settings"""
        if not self.SECRET_KEY and self.ENVIRONMENT == "production":
            raise ValueError("SECRET_KEY must be set in production")
        
        if len(self.SECRET_KEY) < 32 and self.ENVIRONMENT == "production":
            raise ValueError("SECRET_KEY must be at least 32 characters")
        
        if not self.ADMIN_PASSWORD and self.ENVIRONMENT == "production":
            raise ValueError("ADMIN_PASSWORD must be set in production")
        
        # Auto-generate SECRET_KEY for development
        if not self.SECRET_KEY:
            import secrets
            self.SECRET_KEY = secrets.token_urlsafe(32)
            print(f"⚠️  Generated SECRET_KEY for development: {self.SECRET_KEY}")
            print("   Set this in .env for production!")
    
    def _ensure_directories(self):
        """Create required directories"""
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    @property
    def total_questions_per_test(self) -> int:
        return self.EASY_QUESTIONS_PER_TEST + self.MEDIUM_QUESTIONS_PER_TEST + self.HARD_QUESTIONS_PER_TEST
    
    @property
    def max_score(self) -> int:
        return (
            self.EASY_QUESTIONS_PER_TEST * self.EASY_MARKS +
            self.MEDIUM_QUESTIONS_PER_TEST * self.MEDIUM_MARKS +
            self.HARD_QUESTIONS_PER_TEST * self.HARD_MARKS
        )


settings = Settings()
