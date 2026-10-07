"""add teaching_assistants and drop courses.ta_id

Revision ID: 21e0bfbacf2f
Revises: da1db0c19521
Create Date: ...

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '21e0bfbacf2f'
down_revision: Union[str, Sequence[str], None] = 'da1db0c19521'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create the teaching_assistants table (one-to-one with courses).
    op.create_table(
        "teaching_assistants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "ACTIVE", "INACTIVE", name="ta_status"),
            nullable=False,
            server_default=sa.text("'DRAFT'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id", name="uq_teaching_assistants_course_id"
        ),
    )
    op.create_index(
        op.f("ix_teaching_assistants_course_id"),
        "teaching_assistants",
        ["course_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_teaching_assistants_teacher_id"),
        "teaching_assistants",
        ["teacher_id"],
        unique=False,
    )

    # 2. Backfill: give every existing course a default TA.
    op.execute(
        """
        INSERT INTO teaching_assistants (id, course_id, teacher_id, name, status)
        SELECT
            gen_random_uuid(),
            c.id,
            c.teacher_id,
            c.name || ' Assistant',
            'DRAFT'
        FROM courses c
        WHERE NOT EXISTS (
            SELECT 1 FROM teaching_assistants t WHERE t.course_id = c.id
        )
        """
    )

    # 3. Drop the old nullable ta_id column from courses.
    op.drop_index("ix_courses_ta_id", table_name="courses")
    op.drop_column("courses", "ta_id")


def downgrade() -> None:
    # 1. Re-add courses.ta_id (nullable, no FK — as it was before).
    op.add_column(
        "courses",
        sa.Column("ta_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_courses_ta_id"), "courses", ["ta_id"], unique=False
    )

    # 2. Backfill courses.ta_id from the one-to-one table.
    op.execute(
        """
        UPDATE courses c
        SET ta_id = t.id
        FROM teaching_assistants t
        WHERE t.course_id = c.id
        """
    )

    # 3. Drop the TA table and enum.
    op.drop_index(
        op.f("ix_teaching_assistants_teacher_id"),
        table_name="teaching_assistants",
    )
    op.drop_index(
        op.f("ix_teaching_assistants_course_id"),
        table_name="teaching_assistants",
    )
    op.drop_table("teaching_assistants")
    op.execute("DROP TYPE IF EXISTS ta_status")