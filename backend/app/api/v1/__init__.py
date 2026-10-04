from fastapi import APIRouter
from app.api.v1 import auth, users
from app.api.v1 import teaching_assistants

router = APIRouter()
router.include_router(auth.router, tags=["authentication"])
router.include_router(users.router, tags=["users"])
router.include_router(teaching_assistants.router, tags=["teaching-assistants"])