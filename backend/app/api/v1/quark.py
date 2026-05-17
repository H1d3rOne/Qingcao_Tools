"""
夸克工具 API
"""
from fastapi import APIRouter

from app.modules.quark.api.router import router as quark_router

router = APIRouter(prefix="/quark", tags=["夸克工具"])
router.include_router(quark_router)
