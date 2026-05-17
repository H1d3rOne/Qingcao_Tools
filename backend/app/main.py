"""
FastAPI 主入口
Qingcao_Tools API 服务
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.config import settings
from app.core.logger import setup_logger
from app.api.v1.router import api_router
from app.db.database import init_db, close_db
from app.core.exceptions import AppException
from app.core.middleware import LoggingMiddleware

# 初始化日志
setup_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("🚀 启动 Qingcao_Tools...")
    await init_db()
    logger.info("✅ 数据库初始化完成")

    try:
        from app.api.deps import get_xianyu_service

        started = await get_xianyu_service().ensure_chat_ai_listener()
        logger.info(f"闲鱼聊天 AI 监听启动: {started}")
    except Exception as exc:
        logger.warning(f"闲鱼聊天 AI 监听启动失败: {exc}")

    yield

    # 关闭时
    logger.info("👋 关闭服务...")
    try:
        from app.api.deps import get_xianyu_service

        await get_xianyu_service().stop_chat_ai_listener()
    except Exception as exc:
        logger.warning(f"闲鱼聊天 AI 监听停止失败: {exc}")
    await close_db()
    logger.info("✅ 数据库连接已关闭")


# 创建应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Qingcao_Tools - 提供抖音解析、夸克网盘等多种实用工具",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 日志中间件
app.add_middleware(LoggingMiddleware)


# 全局异常处理
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "message": str(exc.detail)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理的异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "服务器内部错误",
            "message": str(exc) if settings.DEBUG else "服务器内部错误"
        }
    )


# 注册路由
app.include_router(api_router, prefix=settings.API_PREFIX)


# 健康检查
@app.get("/health", tags=["健康检查"])
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "name": settings.APP_NAME
    }


# 根路径
@app.get("/", tags=["根路径"])
async def root():
    """根路径"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
