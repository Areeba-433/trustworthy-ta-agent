"""add courses table

Revision ID: a61174adbffa
Revises: 8f2a1c9d4e6b
Create Date: 2026-10-05 10:01:52.742687

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a61174adbffa'
down_revision: Union[str, Sequence[str], None] = '8f2a1c9d4e6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ta_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_courses_teacher_id"), "courses", ["teacher_id"], unique=False)
    op.create_index(op.f("ix_courses_ta_id"), "courses", ["ta_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_courses_ta_id"), table_name="courses")
    op.drop_index(op.f("ix_courses_teacher_id"), table_name="courses")
    op.drop_table("courses")