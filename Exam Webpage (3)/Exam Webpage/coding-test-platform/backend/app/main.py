"""
Reios API server. Also serves the built React app (web/dist) at /app/.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import SessionLocal, create_tables
from app.reios import (
    routes_admin as reios_admin, routes_auth as reios_auth, routes_sets as reios_sets,
    routes_student as reios_student, routes_super as reios_super,
)
from app.reios.security import ensure_super_admin

logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("reios")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_tables()
    # Route handlers run on worker threads; the default 40 queues a lab of students behind each other
    anyio.to_thread.current_default_thread_limiter().total_tokens = settings.WORKER_THREADS
    db = SessionLocal()
    try:
        ensure_super_admin(db)
    except Exception:
        logger.exception("Super admin setup failed")
    finally:
        db.close()
    logger.info("Reios ready (environment: %s)", settings.ENVIRONMENT)
    yield


app = FastAPI(title="Reios", version="2.0.0", docs_url="/api/docs", redoc_url="/api/redoc", lifespan=lifespan)

# Any origin: the frontend may be served from this server, a LAN address or a separate host such as Vercel.
# Auth uses bearer tokens, not cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://.*$",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "Reios", "environment": settings.ENVIRONMENT}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    detail = str(exc) if settings.DEBUG else "An unexpected error occurred"
    return JSONResponse(status_code=500, content={"error": "Internal server error", "detail": detail})


for module in (reios_auth, reios_super, reios_admin, reios_student, reios_sets):
    app.include_router(module.router)

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"

if WEB_DIST.is_dir():
    # Hashed bundles live under /app/assets; everything else falls through to index.html
    # so React Router can handle deep links like /app/console/students on a hard refresh.
    app.mount("/app/assets", StaticFiles(directory=WEB_DIST / "assets"), name="web-assets")

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/app/")

    @app.get("/app", include_in_schema=False)
    @app.get("/app/{path:path}", include_in_schema=False)
    def serve_web(path: str = ""):
        candidate = (WEB_DIST / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(WEB_DIST):
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")
