from fastapi import APIRouter
from app.api.v1 import auth, users, courses, teaching_assistants, resources, chat

router = APIRouter()
router.include_router(auth.router, tags=["authentication"])
router.include_router(users.router, tags=["users"])
router.include_router(courses.router)
router.include_router(teaching_assistants.router)
router.include_router(resources.router)
router.include_router(chat.router)
