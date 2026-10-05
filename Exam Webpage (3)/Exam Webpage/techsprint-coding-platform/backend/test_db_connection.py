"""
Test PostgreSQL database connection
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from app.database import SessionLocal, engine
    from sqlalchemy import text
    
    print("=" * 60)
    print("TESTING DATABASE CONNECTION")
    print("=" * 60)
    print()
    
    # Test connection
    print("Connecting to database...")
    db = SessionLocal()
    
    # Try a simple query
    result = db.execute(text("SELECT version();"))
    version = result.fetchone()[0]
    
    print("✅ Database connection successful!")
    print()
    print(f"PostgreSQL Version:")
    print(f"  {version}")
    print()
    print("=" * 60)
    print("CONNECTION TEST PASSED!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Create tables: python -c \"from app.database import create_tables; create_tables()\"")
    print("2. Create questions: python create_sample_questions_fast.py")
    print()
    
    db.close()
    
except Exception as e:
    print("=" * 60)
    print("❌ DATABASE CONNECTION FAILED")
    print("=" * 60)
    print()
    print(f"Error: {e}")
    print()
    print("Possible solutions:")
    print("1. Make sure PostgreSQL is installed and running")
    print("2. Check your .env file has correct DATABASE_URL")
    print("3. Verify database user and password are correct")
    print("4. See SETUP_POSTGRESQL.md for setup instructions")
    print()
    sys.exit(1)
