"""add_real_server_default_to_profiles_updated_at

profiles.updated_at is NOT NULL with no DB-level default. Every current
insert path (register endpoint, seed_admin.py) happens to pass it
explicitly, so this is not currently breaking anything - but it is a
silent trap for any future insert path that forgets to. This adds a real
server default so the column is correct on its own.

Revision ID: 8f2a1c9d4e6b
Revises: d97b33d4d303
Create Date: 2026-09-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f2a1c9d4e6b'
down_revision: Union[str, Sequence[str], None] = 'd97b33d4d303'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'profiles',
        'updated_at',
        server_default=sa.text('now()'),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'profiles',
        'updated_at',
        server_default=None,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
