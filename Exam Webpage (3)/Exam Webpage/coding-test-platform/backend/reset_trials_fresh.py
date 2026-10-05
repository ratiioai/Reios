"""
Reset all trial submissions, violations, test sessions, and configuration for a fresh start.
Preserves all 153 imported teams, master questions, and question assignments.
"""
from app.database import SessionLocal
from app.models import (
    TestSession, TestConfiguration, Submission, GradingResult,
    ProctoringViolation, AuditLog, Team, TestStatus
)
from app.grading_queue import GradingQueueItem

def reset_all_for_fresh_start():
    db = SessionLocal()
    try:
        print("[1/5] Deleting all trial grading results...")
        deleted_grades = db.query(GradingResult).delete()
        print(f"       -> Deleted {deleted_grades} grading records.")

        print("[2/5] Deleting all trial submissions and queue items...")
        deleted_queue = db.query(GradingQueueItem).delete()
        deleted_subs = db.query(Submission).delete()
        print(f"       -> Deleted {deleted_subs} submissions, {deleted_queue} queue items.")

        print("[3/5] Deleting all trial proctoring violations & audit logs...")
        deleted_violations = db.query(ProctoringViolation).delete()
        deleted_audits = db.query(AuditLog).delete()
        print(f"       -> Deleted {deleted_violations} violations, {deleted_audits} audit logs.")

        print("[4/5] Resetting all team test sessions and login states...")
        sessions = db.query(TestSession).all()
        for session in sessions:
            session.status = TestStatus.NOT_STARTED
            session.test_started_at = None
            session.submitted_at = None
            session.auto_submitted = False
            session.time_taken_seconds = 0
            session.total_score = 0
            session.easy_score = 0
            session.medium_score = 0
            session.hard_score = 0
            session.rank = None
        
        teams = db.query(Team).all()
        for team in teams:
            team.failed_login_attempts = 0
            team.locked_until = None
            team.is_active = True
        
        print(f"       -> Reset {len(sessions)} test sessions and {len(teams)} teams.")

        print("[5/5] Resetting test configuration to pre-start lobby state...")
        config = db.query(TestConfiguration).first()
        if not config:
            config = TestConfiguration(id=1)
            db.add(config)
        
        config.duration_minutes = 120
        config.synchronized_start = True
        config.global_start_time = None
        config.test_open_at = None
        config.test_close_at = None
        config.leaderboard_published = False
        config.allow_team_view_leaderboard = False

        db.commit()
        print("\n========================================================")
        print(" SUCCESS: ALL TRIAL DATA CLEARED! READY FOR FRESH START")
        print("========================================================")

    except Exception as e:
        db.rollback()
        print(f"Error resetting database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    reset_all_for_fresh_start()
