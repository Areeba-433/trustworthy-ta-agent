"""add role column back to users

Revision ID: fareeha_add_role_001
Revises: f6abdf1581ee
Create Date: 2026-09-07 12:00:00.000000

NOTE: This migration was a duplicate of ccd20a59a04b_add_role_column_to_users
(both branched off f6abdf1581ee and both add the same 'role' column to 'users').
ccd20a59a04b is the version being kept as the real implementation because it
was the one already applied to existing team databases. Emptied to no-op to
prevent "column already exists" errors when both branches are merged. Kept
in the revision chain so this history remains valid.
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
    """No-op - duplicate of ccd20a59a04b, already applied there."""
    pass


def downgrade() -> None:
    """No-op - see upgrade()."""
    pass