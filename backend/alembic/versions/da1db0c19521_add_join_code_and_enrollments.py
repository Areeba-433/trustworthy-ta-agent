"""add join_code and enrollments

Revision ID: da1db0c19521
Revises: a61174adbffa
Create Date: 2026-10-05 13:29:25.023360

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'da1db0c19521'
down_revision: Union[str, Sequence[str], None] = 'a61174adbffa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Add join_code to courses (nullable for existing rows)
    op.add_column(
        "courses",
        sa.Column("join_code", sa.String(length=12), nullable=True),
    )

    # 2) Backfill any existing courses with a random 6-char code,
    #    using an alphabet that avoids confusables (0/O, 1/I/L, 2/Z, 5/S).
    op.execute(
        """
        UPDATE courses
        SET join_code = (
            SELECT string_agg(
                substr('ABCDEFGHJKMNPQRTUVWXY346789',
                       floor(random() * 30 + 1)::int, 1),
                ''
            )
            FROM generate_series(1, 6)
        )
        WHERE join_code IS NULL
        """
    )

    # 3) Enforce NOT NULL + UNIQUE now that every row has a code
    op.alter_column("courses", "join_code", nullable=False)
    op.create_unique_constraint("uq_courses_join_code", "courses", ["join_code"])

    # 4) Create enrollments table
    op.create_table(
        "enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id", "student_id", name="uq_enrollment_course_student"
        ),
    )
    op.create_index(
        op.f("ix_enrollments_course_id"), "enrollments", ["course_id"], unique=False
    )
    op.create_index(
        op.f("ix_enrollments_student_id"), "enrollments", ["student_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_enrollments_student_id"), table_name="enrollments")
    op.drop_index(op.f("ix_enrollments_course_id"), table_name="enrollments")
    op.drop_table("enrollments")
    op.drop_constraint("uq_courses_join_code", "courses", type_="unique")
    op.drop_column("courses", "join_code")
