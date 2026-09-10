"""
Seed script to create or update the initial Administrator account.

Usage:
    python -m scripts.seed_admin
    or
    python scripts/seed_admin.py
"""

import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.profile import Profile


def seed_admin():
    admin_email = os.getenv("ADMIN_EMAIL", "admin@trustworthy-ta.com")
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "Admin1234!")
    first_name = os.getenv("ADMIN_FIRST_NAME", "System")
    last_name = os.getenv("ADMIN_LAST_NAME", "Administrator")

    db = SessionLocal()
    try:
        user = db.query(User).filter(
            (User.email == admin_email) | (User.username == admin_username)
        ).first()

        hashed_password = get_password_hash(admin_password)

        if user:
            print(f"[*] Found existing user '{user.username}' ({user.email}). Promoting to ADMIN...")
            user.role = UserRole.ADMIN
            user.is_active = True
            user.is_verified = True
            user.password_hash = hashed_password
            db.commit()
            print(f"[+] Admin account updated successfully!")
        else:
            print(f"[*] Creating new Administrator account ({admin_email})...")
            new_user = User(
                username=admin_username,
                email=admin_email,
                password_hash=hashed_password,
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            db.add(new_user)
            db.flush()

            profile = Profile(
                user_id=new_user.id,
                first_name=first_name,
                last_name=last_name,
                department="Administration",
                expertise="System Management",
            )
            db.add(profile)
            db.commit()
            print(f"[+] Administrator account created successfully!")

        print("\nAdmin Credentials:")
        print(f"  Identifier: {admin_email} (or {admin_username})")
        print(f"  Role:       ADMIN")
        print(f"  Password:   {admin_password}")
        print("  Status:     Active & Verified\n")

    except Exception as e:
        db.rollback()
        print(f"[-] Error seeding admin account: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
