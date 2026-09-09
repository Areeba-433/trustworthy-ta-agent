"""merge_role_and_session_migration_heads

Revision ID: d97b33d4d303
Revises: 0c2defe978f5, 10f2cd6b73dc, fareeha_add_role_001
Create Date: 2026-09-09 11:38:52.728247

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd97b33d4d303'
down_revision: Union[str, Sequence[str], None] = ('0c2defe978f5', '10f2cd6b73dc', 'fareeha_add_role_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
