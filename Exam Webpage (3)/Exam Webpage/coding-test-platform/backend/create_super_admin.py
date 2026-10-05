"""
Create (or reset the password of) a Reios super admin.

Usage (from the backend folder):
    python create_super_admin.py admin@example.com "Your Name"
You will be asked for the password.
"""
import getpass
import sys

from app.auth import hash_password
from app.database import SessionLocal, create_tables
from app.reios.models import Role, User


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    email = sys.argv[1].strip().lower()
    name = sys.argv[2] if len(sys.argv) > 2 else "Super Admin"
    password = getpass.getpass("Password (min 8 chars): ")
    if len(password) < 8 or password != getpass.getpass("Confirm password: "):
        print("Passwords must match and be at least 8 characters.")
        sys.exit(1)

    create_tables()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user and user.role != Role.SUPER_ADMIN:
            print(f"{email} already belongs to a {user.role.value}; use another email.")
            sys.exit(1)
        if user:
            user.hashed_password = hash_password(password)
            user.token_version += 1
            user.locked_until = None
            print(f"Password reset for super admin {email}")
        else:
            db.add(User(role=Role.SUPER_ADMIN, name=name, email=email,
                        hashed_password=hash_password(password), must_change_password=False))
            print(f"Super admin created: {email}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
