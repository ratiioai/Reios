"""
Main FastAPI Application
Coding Test Platform for 175 Teams
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import SessionLocal, create_tables
from app.auth import create_admin_user
from app.models import Admin

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events"""
    # Startup
    logger.info("=" * 60)
    logger.info("Coding Test Platform Starting")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info("=" * 60)
    
    # Create database tables
    create_tables()
    logger.info("Database tables initialized")
    
    # Create admin user if doesn't exist
    db = SessionLocal()
    try:
        existing_admin = db.query(Admin).filter(Admin.username == settings.ADMIN_USERNAME).first()
        if not existing_admin:
            if not settings.ADMIN_PASSWORD:
                logger.error("ADMIN_PASSWORD not set in environment!")
            else:
                create_admin_user(
                    db,
                    username=settings.ADMIN_USERNAME,
                    password=settings.ADMIN_PASSWORD,
                    email=settings.ADMIN_EMAIL
                )
                logger.info(f"Admin account created: '{settings.ADMIN_USERNAME}'")
        else:
            logger.info(f"Admin account exists: '{settings.ADMIN_USERNAME}'")
    except Exception as e:
        logger.error(f"Admin account setup error: {e}")
    finally:
        db.close()

    # Reios module: create the first super admin from SUPER_ADMIN_EMAIL / SUPER_ADMIN_PASSWORD
    from app.reios.security import ensure_super_admin
    db = SessionLocal()
    try:
        ensure_super_admin(db)
    except Exception as e:
        logger.error(f"Reios super admin setup error: {e}")
    finally:
        db.close()
    
    logger.info("=" * 60)
    logger.info("Coding Test Platform Ready")
    logger.info(f"Max teams: 175")
    logger.info(f"Questions per test: {settings.total_questions_per_test}")
    logger.info(f"Max score: {settings.max_score}")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("Coding Test Platform shutting down")


# Create FastAPI app
app = FastAPI(
    title="Coding Test Platform",
    description="Auto-graded coding test platform for 175 teams with unique question sets",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# CORS - Allow all origins for Vercel, Cloudflare Tunnels, LAN, and Localhost
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://.*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Coding Test Platform",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "config": {
            "questions_per_test": settings.total_questions_per_test,
            "max_score": settings.max_score,
            "test_duration_minutes": settings.DEFAULT_TEST_DURATION_MINUTES,
        }
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions"""
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}")
    
    if settings.DEBUG:
        detail = str(exc)
    else:
        detail = "An unexpected error occurred"
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": detail,
        }
    )


# Import and include routers
from app.routes import auth, admin, teams

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(teams.router)

# Reios multi-college exam module
from app.reios import (
    routes_admin as reios_admin, routes_auth as reios_auth, routes_student as reios_student,
    routes_super as reios_super,
)

app.include_router(reios_auth.router)
app.include_router(reios_super.router)
app.include_router(reios_admin.router)
app.include_router(reios_student.router)

# Serve the frontend from the same server, e.g. http://localhost:8000/app/reios/
from pathlib import Path
from fastapi.staticfiles import StaticFiles

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
