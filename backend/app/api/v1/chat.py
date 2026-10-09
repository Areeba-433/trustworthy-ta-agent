"""Chat endpoint. Owner: Member 4. Skeleton: no endpoints yet."""
from fastapi import APIRouter

router = APIRouter(prefix="/courses/{course_id}/chat", tags=["chat"])
