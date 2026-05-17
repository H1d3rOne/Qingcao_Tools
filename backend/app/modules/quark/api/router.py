from fastapi import APIRouter

from .auth import router as auth_router
from .files import router as files_router

router = APIRouter()


@router.get("/test")
async def test_endpoint():
    """测试接口"""
    return {"message": "API is working"}


@router.get("/health")
async def api_health_check():
    """API 健康检查"""
    return {"status": "ok", "service": "api"}


# 注册子路由
router.include_router(auth_router)
router.include_router(files_router)
