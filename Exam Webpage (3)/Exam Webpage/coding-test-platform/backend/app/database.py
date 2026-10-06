"""
Database configuration and session management
"""
from contextlib import contextmanager

from sqlalchemy import create_engine, event, make_url, text
from sqlalchemy.orm import sessionmaker

from app.config import settings

is_sqlite = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}

# SQLite: plenty of cheap connections. PostgreSQL: a small pool that stays open; in a rush, requests wait
# their turn for a connection rather than opening new ones (hosted databases cap connections, and a
# burst of new connections overwhelmed the host's name lookup in testing).
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=not is_sqlite,
    pool_size=30 if is_sqlite else settings.DB_POOL_SIZE,
    max_overflow=max(settings.WORKER_THREADS - 30, 20) if is_sqlite else settings.DB_MAX_OVERFLOW,
    pool_timeout=90,
    echo=False,
)

if not is_sqlite:
    import socket
    import threading
    import time

    _db_host = make_url(settings.DATABASE_URL).host
    _dns = {"ip": None, "at": 0.0}
    _dns_lock = threading.Lock()

    @event.listens_for(engine, "do_connect")
    def _reuse_resolved_address(dialect, conn_rec, cargs, cparams):
        """Look the database host up once every few minutes, not once per new connection."""
        if not _db_host:
            return
        with _dns_lock:
            if not _dns["ip"] or time.time() - _dns["at"] > 300:
                try:
                    _dns["ip"] = socket.getaddrinfo(_db_host, None, socket.AF_INET)[0][4][0]
                    _dns["at"] = time.time()
                except OSError:
                    pass  # keep using the last address that worked
        if _dns["ip"]:
            cparams["hostaddr"] = _dns["ip"]  # host is still sent, so TLS checks the real name

# Enable WAL (Write-Ahead Logging) and busy timeout for concurrent readers/writers on SQLite
if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Dependency for FastAPI routes
    Yields a database session and ensures cleanup
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def startup_lock():
    """
    Several worker processes start at once; on PostgreSQL only one may create tables and seed data at a
    time, or they collide ("type already exists"). Others wait here, then find everything already done.
    """
    if is_sqlite:
        yield
        return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("SELECT pg_advisory_lock(727001)"))
        try:
            yield
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(727001)"))


def create_tables():
    from app.models import Base
    import app.reios.models  # noqa: F401  registers the reios_* tables
    from app.reios.migrate import upgrade
    Base.metadata.create_all(bind=engine)
    upgrade(engine)
