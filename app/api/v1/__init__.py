"""API v1 router."""
from fastapi import APIRouter
from app.api.v1 import chat, documents, health

router = APIRouter(prefix="/v1")

router.include_router(chat.router)
router.include_router(documents.router)
router.include_router(health.router)

