"""fix_user_updated_at_default

Revision ID: fb4bdb206dc3
Revises: a76834aa922e
Create Date: 2026-09-04 11:21:42.254372
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fb4bdb206dc3'
down_revision: Union[str, Sequence[str], None] = 'a76834aa922e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add server_default to users.updated_at column."""
    # Alter the updated_at column to have a default value
    op.alter_column(
        'users',
        'updated_at',
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text('now()'),
        existing_nullable=False
    )


def downgrade() -> None:
    """Remove server_default from users.updated_at column."""
    op.alter_column(
        'users',
        'updated_at',
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        existing_nullable=False
    )