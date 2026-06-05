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


def _configure_stream_encoding(stream):
    """尽量把控制台/重定向日志输出调整为 UTF-8，并兜底替换不可编码字符。

    Windows 下 stdout 被 bat 重定向到日志文件时，Python 可能会使用 GBK 编码；
    日志中出现 emoji 等字符时会触发 UnicodeEncodeError，进而造成 Loguru
    handler 自身报错。这里不改变文件日志，只保护控制台/重定向输出。
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return

    try:
        reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        try:
            reconfigure(errors="backslashreplace")
        except Exception:
            pass


class SafeStreamSink:
    """Loguru 控制台 sink，避免非 UTF-8 环境下因单条日志编码失败中断输出。"""

    def __init__(self, stream):
        self.stream = stream

    def write(self, message: str) -> None:
        try:
            self.stream.write(message)
        except UnicodeEncodeError:
            encoding = getattr(self.stream, "encoding", None) or "utf-8"
            safe_message = message.encode(encoding, errors="backslashreplace").decode(
                encoding,
                errors="replace",
            )
            self.stream.write(safe_message)

        flush = getattr(self.stream, "flush", None)
        if callable(flush):
            flush()


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

    _configure_stream_encoding(sys.stdout)
    _configure_stream_encoding(sys.stderr)

    # 确保日志目录存在
    log_path = Path(settings.LOG_PATH)
    log_path.mkdir(parents=True, exist_ok=True)

    # 控制台输出（开发环境）
    logger.add(
        SafeStreamSink(sys.stdout),
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=bool(getattr(sys.stdout, "isatty", lambda: False)()),
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
