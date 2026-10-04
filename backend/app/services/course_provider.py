"""
Course provider used by the Teaching Assistant module.

STUB: Course Management is being built on another branch
(feature/course-management). Until it is merged, this returns fixed,
obviously fake course data in the agreed Course shape, so the TA module
can be built and tested on its own.
"""

from uuid import UUID


class DummyCourseProvider:
    """STUB. Real version: query courses where Course.ta_id == ta_id
    and Course.teacher_id == teacher_id."""

    # TODO(TA owner): replace with the real Course query once
    # feature/course-management is merged into develop.
    def get_courses_for_ta(self, teacher_id: UUID, ta_id: UUID) -> list[dict]:
        return [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "name": "(stub) Artificial Intelligence",
                "code": "AI-101",
            }
        ]


course_provider = DummyCourseProvider()