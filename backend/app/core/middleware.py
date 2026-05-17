"""
中间件模块
"""
import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""
    
    async def dispatch(self, request: Request, call_next):
        # 记录请求开始时间
        start_time = time.time()
        
        # 处理请求
        response: Response = await call_next(request)
        
        # 计算处理时间
        process_time = (time.time() - start_time) * 1000
        
        # 记录日志 - 使用完整URL路径
        logger.info(
            f"{request.method} {request.url} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.2f}ms"
        )
        
        # 添加处理时间到响应头
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        
        return response


class CORSMiddleware:
    """CORS 中间件配置"""
    
    @staticmethod
    def get_config():
        return {
            "allow_origins": ["*"],
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
        }
