from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_role
from app.models.user import User
from app.schemas.auth import error_response, success_response
from app.schemas.teaching_assistant import TAOut, TAUpdate
from app.services.teaching_assistant_service import (
    TAAccessDeniedError,
    TANotFoundError,
    TeachingAssistantService,
)

router = APIRouter(prefix="/courses", tags=["Teaching Assistant"])


def _ta_json(ta) -> dict:
    return TAOut.model_validate(ta).model_dump(mode="json")


def _no_access() -> HTTPException:
    # 404 so we don't leak whether the course exists.
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=error_response("COURSE_NOT_FOUND", "Course not found"),
    )


def _ta_missing() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=error_response("TA_NOT_FOUND", "Teaching assistant not found"),
    )


@router.get("/{course_id}/ta")
async def get_ta(
    course_id: UUID,
    teacher: User = Depends(require_role("TEACHER")),
    db: Session = Depends(get_db),
):
    try:
        ta = TeachingAssistantService(db).get_for_course(teacher.id, course_id)
    except TAAccessDeniedError:
        raise _no_access()
    except TANotFoundError:
        raise _ta_missing()
    return success_response("Teaching assistant fetched", {"ta": _ta_json(ta)})


@router.put("/{course_id}/ta")
async def update_ta(
    course_id: UUID,
    body: TAUpdate,
    teacher: User = Depends(require_role("TEACHER")),
    db: Session = Depends(get_db),
):
    try:
        ta = TeachingAssistantService(db).update_for_course(
            teacher.id, course_id, body
        )
    except TAAccessDeniedError:
        raise _no_access()
    except TANotFoundError:
        raise _ta_missing()
    return success_response("Teaching assistant updated", {"ta": _ta_json(ta)})