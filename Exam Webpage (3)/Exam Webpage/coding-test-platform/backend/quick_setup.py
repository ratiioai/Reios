"""
Quick setup script to initialize the platform
Run this FIRST before starting the server
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

print("=" * 80)
print("SPEC INDUSTRY HACK - PLATFORM SETUP")
print("=" * 80)

print("\n[1/4] Loading configuration...")
from app.config import settings
print(f"✓ Database: {settings.DATABASE_URL}")
print(f"✓ Environment: {settings.ENVIRONMENT}")

print("\n[2/4] Creating database tables...")
from app.database import create_tables
from app.grading_queue import GradingQueueItem
create_tables()
print("✓ All tables created")

print("\n[3/4] Creating admin account...")
from app.database import SessionLocal
from app.models import Admin
from app.auth import hash_password

db = SessionLocal()

# Check if admin exists
existing_admin = db.query(Admin).filter(Admin.username == settings.ADMIN_USERNAME).first()
if existing_admin:
    print(f"✓ Admin already exists: {settings.ADMIN_USERNAME}")
else:
    admin = Admin(
        username=settings.ADMIN_USERNAME,
        email=settings.ADMIN_EMAIL,
        password_hash=hash_password(settings.ADMIN_PASSWORD),
        is_super_admin=True,
        is_active=True
    )
    db.add(admin)
    db.commit()
    print(f"✓ Admin created: {settings.ADMIN_USERNAME}")

print("\n[4/4] Checking questions...")
from app.models import Question
question_count = db.query(Question).count()
print(f"✓ Questions in database: {question_count}")

if question_count == 0:
    print("\n⚠️  WARNING: No questions found!")
    print("   Run: python create_sample_questions_fast.py")
    print("   This will create 150 questions (60 easy, 60 medium, 30 hard)")
else:
    print(f"✓ Ready to assign unique question sets to teams")

db.close()

print("\n" + "=" * 80)
print("SETUP COMPLETE!")
print("=" * 80)
print("\nNEXT STEPS:")
print("1. If questions = 0, run: python create_sample_questions_fast.py")
print("2. Start backend server: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
print("3. Start frontend server: cd ../frontend && python -m http.server 3000")
print("4. Start grading worker: python grading_worker.py")
print("\nAdmin Login:")
print(f"  Username: {settings.ADMIN_USERNAME}")
print(f"  Password: {settings.ADMIN_PASSWORD}")
print("\nTeam Login Format:")
print("  Username: [team_name]")
print("  Password: [leader_phone]")
print("=" * 80)
