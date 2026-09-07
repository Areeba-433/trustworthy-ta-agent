"""add role column back to users

Revision ID: fareeha_add_role_001
Revises: f6abdf1581ee
Create Date: 2026-09-07 12:00:00.000000

NOTE: The 'role' column was dropped from 'users' during an earlier auto-generated
migration (6863afa13643) — but it's required for RBAC (require_role dependency)
and the User model still declares it. Adding it back here since RBAC (TTA-10/TTA-12)
depends on it. Did not touch the existing migration that dropped it.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'fareeha_add_role_001'
down_revision: Union[str, Sequence[str], None] = 'f6abdf1581ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    userrole_enum = postgresql.ENUM('STUDENT', 'TEACHER', 'ADMIN', name='userrole')
    userrole_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'users',
        sa.Column('role', userrole_enum, nullable=False, server_default='STUDENT')
    )


def downgrade() -> None:
    op.drop_column('users', 'role')
    postgresql.ENUM(name='userrole').drop(op.get_bind(), checkfirst=True)