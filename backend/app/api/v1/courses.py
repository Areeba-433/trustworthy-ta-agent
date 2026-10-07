from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_role
from app.models.user import User
from app.schemas.auth import error_response, success_response
from app.schemas.course import CourseCreate, CourseOut, CourseUpdate
from app.schemas.enrollment import EnrolledCourseOut, JoinByCodeRequest
from app.services.course_service import CourseNotFoundError, CourseService
from app.services.enrollment_service import (
    AlreadyEnrolledError,
    CourseNotFoundByCodeError,
    EnrollmentService,
)

router = APIRouter(prefix="/courses", tags=["Courses"])


def _course_json(course) -> dict:
    return CourseOut.model_validate(course).model_dump(mode="json")


def _enrolled_json(course) -> dict:
    return EnrolledCourseOut.model_validate(course).model_dump(mode="json")


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=error_response("COURSE_NOT_FOUND", "Course not found"),
    )


# ---------------------------------------------------------------------------
# Teacher routes
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_course(
    body: CourseCreate,
    teacher: User = Depends(require_role("TEACHER")),
    db: Session = Depends(get_db),
):
    course = CourseService(db).create_course(teacher.id, body)
    return success_response("Course created", {"course": _course_json(course)})


@router.get("")
async def list_courses(
    teacher: User = Depends(require_role("TEACHER")),
    db: Session = Depends(get_db),
):
    courses = CourseService(db).list_courses(teacher.id)
    return success_response(
        "Courses fetched", {"courses": [_course_json(c) for c in courses]}
    )


# ---------------------------------------------------------------------------
# Student routes — MUST come before /{course_id} so 'join' and 'enrolled'
# are not interpreted as UUID path params.
# ---------------------------------------------------------------------------

@router.post("/join")
async def join_course_by_code(
    body: JoinByCodeRequest,
    student: User = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db),
):
    try:
        course = EnrollmentService(db).join_by_code(student.id, body.code)
    except CourseNotFoundByCodeError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response("INVALID_CODE", "Invalid or expired class code"),
        )
    except AlreadyEnrolledError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response(
                "ALREADY_ENROLLED", "You have already joined this class"
            ),
        )
    return success_response(
        "Joined class",
        {
            "course": {
                "id": str(course.id),
                "name": course.name,
                "code": course.code,
            }
        },
    )


@router.get("/enrolled")
async def list_my_enrolled_courses(
    student: User = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db),
):
    courses = EnrollmentService(db).list_student_courses(student.id)
    return success_response(
        "Enrolled courses fetched",
        {"courses": [_enrolled_json(c) for c in courses]},
    )


# ---------------------------------------------------------------------------
# Per-course routes
# ---------------------------------------------------------------------------

@router.get("/{course_id}")
async def get_course(
    course_id: UUID,
    teacher: User = Depends(require_role("TEACHER")),
    db: Session = Depends(get_db),
):
    try:
        course = CourseService(db).get_course(teacher.id, course_id)
    except CourseNotFoundError:
        raise _not_found()
    return success_response("Course fetched", {"course": _course_json(course)})


@router.put("/{course_id}")
async def update_course(
    course_id: UUID,
    body: CourseUpdate,
    teacher: User = Depends(require_role("TEACHER")),
    db: Session = Depends(get_db),
):
    try:
        course = CourseService(db).update_course(teacher.id, course_id, body)
    except CourseNotFoundError:
        raise _not_found()
    return success_response("Course updated", {"course": _course_json(course)})


@router.delete("/{course_id}")
async def delete_course(
    course_id: UUID,
    teacher: User = Depends(require_role("TEACHER")),
    db: Session = Depends(get_db),
):
    try:
        CourseService(db).delete_course(teacher.id, course_id)
    except CourseNotFoundError:
        raise _not_found()
    return success_response("Course deleted")


# ---------------------------------------------------------------------------
# Student leave — after /{course_id} routes is fine because path is longer.
# ---------------------------------------------------------------------------

@router.delete("/{course_id}/leave")
async def leave_course(
    course_id: UUID,
    student: User = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db),
):
    EnrollmentService(db).leave_course(student.id, course_id)
    return success_response("Left class")