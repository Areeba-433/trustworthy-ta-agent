from fastapi import APIRouter
from app.api.v1 import auth, users, courses, resources, chat

router = APIRouter()
router.include_router(auth.router, tags=["authentication"])
router.include_router(users.router, tags=["users"])
router.include_router(courses.router, tags=["courses"])
router.include_router(resources.router, tags=["resources"])
router.include_router(chat.router, tags=["chat"])