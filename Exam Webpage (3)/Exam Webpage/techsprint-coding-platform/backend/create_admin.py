"""
Create admin user for the platform
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal
from app.models import Admin
from app.auth import hash_password
from app.config import settings

print("=" * 80)
print("CREATING ADMIN USER")
print("=" * 80)

db = SessionLocal()

try:
    # Check if admin exists
    existing_admin = db.query(Admin).filter(Admin.username == settings.ADMIN_USERNAME).first()
    
    if existing_admin:
        print(f"\n[INFO] Admin user '{settings.ADMIN_USERNAME}' already exists!")
        print(f"   Updating password to: {settings.ADMIN_PASSWORD}")
        existing_admin.password_hash = hash_password(settings.ADMIN_PASSWORD)
        db.commit()
        print("[OK] Password updated!")
    else:
        print(f"\n[INFO] Creating new admin user...")
        admin = Admin(
            username=settings.ADMIN_USERNAME,
            email=settings.ADMIN_EMAIL,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            is_super_admin=True,
            is_active=True
        )
        db.add(admin)
        db.commit()
        print("[OK] Admin user created successfully!")
    
    print("\n" + "=" * 80)
    print("ADMIN CREDENTIALS")
    print("=" * 80)
    print(f"Username: {settings.ADMIN_USERNAME}")
    print(f"Password: {settings.ADMIN_PASSWORD}")
    print("=" * 80)
    print("\nYou can now login at: http://localhost:3000")
    print("=" * 80)

except Exception as e:
    print(f"\n[ERROR] Error: {e}")
    db.rollback()
finally:
    db.close()
