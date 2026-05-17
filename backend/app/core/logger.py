"""
日志配置模块
使用 loguru 进行日志管理，支持文件存储和定期回滚
"""
import inspect
import logging
import sys
from pathlib import Path
from loguru import logger
from app.core.config import settings


class InterceptHandler(logging.Handler):
    """把标准库 logging 的日志转给 loguru，避免使用 logging.getLogger 的模块被静默。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logger():
    """配置日志系统"""
    # 移除默认的处理器
    logger.remove()

    # 确保日志目录存在
    log_path = Path(settings.LOG_PATH)
    log_path.mkdir(parents=True, exist_ok=True)

    # 控制台输出（开发环境）
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # 文件输出 - 所有日志
    logger.add(
        f"{settings.LOG_PATH}/app.log",
        level=settings.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation=settings.LOG_ROTATION,  # 文件大小达到 10MB 时轮转
        retention=settings.LOG_RETENTION,  # 保留 7 天的日志
        compression="zip",  # 压缩旧日志文件
        encoding="utf-8",
        enqueue=True,  # 异步写入
    )

    # 文件输出 - 错误日志单独存储
    logger.add(
        f"{settings.LOG_PATH}/error.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        encoding="utf-8",
        enqueue=True,
    )

    # 把标准库 logging 统一转发给 loguru（包括第三方库 & xianyu.service 自己）
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "httpx", "websockets"):
        std_logger = logging.getLogger(noisy)
        std_logger.handlers = [InterceptHandler()]
        std_logger.propagate = False

    logger.info("日志系统初始化完成")
    return logger
