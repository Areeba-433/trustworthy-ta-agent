"""add_sessions_table

Revision ID: 0c2defe978f5
Revises: 6863afa13643
Create Date: 2026-09-06 05:12:39.412733

NOTE: This migration was an exact duplicate of 6863afa13643_add_sessions_and_audit_logs.py
(same sessions table creation, same users column changes) - appears to have been
auto-generated twice during independent local development before merge. Emptied
to no-op to prevent "relation already exists" errors. Kept in the revision chain
so downstream migrations don't need their down_revision changed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0c2defe978f5'
down_revision: Union[str, Sequence[str], None] = '6863afa13643'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op - duplicate of 6863afa13643, already applied there."""
    pass


def downgrade() -> None:
    """No-op - see upgrade()."""
    pass