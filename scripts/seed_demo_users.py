"""Insert the five demo roles. An existing email keeps its password and role.

Run after Alembic 0006:

    python -m scripts.seed_demo_users

New accounts share the demo password already used by hr.demo. The script does
not reseed policies.
"""

import asyncio

from sqlalchemy import select

from src.core.security.auth_handler import AuthHandler
from src.core.security.seeder import seed_rbac
from src.db.session import SessionLocal
from src.models.users import User

DEMO_PASSWORD = "Demo-hr-2026"
DEMO_USERS = (
    ("hr.demo@vinuni.edu.vn", "HR", "HR Demo"),
    ("manager.demo@vinuni.edu.vn", "MANAGER", "Manager Demo"),
    ("legal.demo@vinuni.edu.vn", "LEGAL", "Legal Demo"),
    ("signer.demo@vinuni.edu.vn", "SIGNER", "Signer Demo"),
    ("admin.demo@vinuni.edu.vn", "ADMIN", "Admin Demo"),
)


async def seed_demo_users() -> None:
    """Create missing demo users, then mirror their roles into user_roles."""
    async with SessionLocal() as session:
        for email, role, full_name in DEMO_USERS:
            found = await session.scalar(select(User).where(User.email == email))
            if found is not None:
                print(f"exists {email} role={found.role}")
                continue
            session.add(
                User(
                    email=email,
                    password_hash=AuthHandler.get_password_hash(DEMO_PASSWORD),
                    full_name=full_name,
                    role=role,
                    is_active=True,
                )
            )
            print(f"created {email} role={role}")
        await session.commit()
        await seed_rbac(session)


def main() -> None:
    asyncio.run(seed_demo_users())


if __name__ == "__main__":
    main()
