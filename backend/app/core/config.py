"""
应用配置管理
使用 YAML 进行配置管理
"""
import os
import yaml
from pathlib import Path
from functools import lru_cache
from typing import Optional, Any
from pydantic import BaseModel

from app.core.config_bootstrap import (
    DEFAULT_BACKEND_CONFIG,
    ensure_runtime_config,
    get_runtime_config_dir,
)


# 启动早期先准备统一运行态配置目录：
# - backend/config/：本地私有配置与运行态数据，gitignore；
# - backend/config.example/：可提交模板；
# - backend/app/config/：旧版配置位置，仅作为迁移兜底。
RUNTIME_CONFIG_DIR = ensure_runtime_config()


class AppConfig(BaseModel):
    """应用配置"""
    name: str = "青草工具箱 API"
    version: str = "1.0.0"
    debug: bool = False
    api_prefix: str = "/api/v1"


class ServerConfig(BaseModel):
    """服务器配置"""
    host: str = "0.0.0.0"
    port: int = 5000


class DatabaseConfig(BaseModel):
    """数据库配置"""
    url: str = "sqlite+aiosqlite:///./data.db"


class RedisConfig(BaseModel):
    """Redis 配置"""
    url: str = "redis://localhost:6379/0"
    enabled: bool = False


class CookiesConfig(BaseModel):
    """Cookie 配置"""
    douyin: str = ""
    douyin_live: str = ""
    quark: str = ""
    xianyu: str = ""


class DownloadConfig(BaseModel):
    """下载配置"""
    path: str = "./datas/media"
    excel_path: str = "./datas/excel"


class SecurityConfig(BaseModel):
    """安全配置"""
    secret_key: str = "your-secret-key-please-change-in-production"
    access_token_expire_minutes: int = 1440


class RequestConfig(BaseModel):
    """请求配置"""
    timeout: int = 30
    max_retries: int = 3


class LogConfig(BaseModel):
    """日志配置"""
    path: str = "./logs"
    level: str = "INFO"
    rotation: str = "10 MB"
    retention: str = "7 days"
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"


class Settings(BaseModel):
    """应用配置"""
    app: AppConfig = AppConfig()
    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    cookies: CookiesConfig = CookiesConfig()
    download: DownloadConfig = DownloadConfig()
    security: SecurityConfig = SecurityConfig()
    request: RequestConfig = RequestConfig()
    log: LogConfig = LogConfig()

    # 兼容旧代码的属性访问
    @property
    def APP_NAME(self) -> str:
        return self.app.name

    @property
    def APP_VERSION(self) -> str:
        return self.app.version

    @property
    def DEBUG(self) -> bool:
        return self.app.debug

    @property
    def API_PREFIX(self) -> str:
        return self.app.api_prefix

    @property
    def HOST(self) -> str:
        return self.server.host

    @property
    def PORT(self) -> int:
        return self.server.port

    @property
    def DATABASE_URL(self) -> str:
        return self.database.url

    @property
    def REDIS_URL(self) -> str:
        return self.redis.url

    @property
    def REDIS_ENABLED(self) -> bool:
        return self.redis.enabled

    @property
    def DY_COOKIES(self) -> str:
        return self.cookies.douyin

    @DY_COOKIES.setter
    def DY_COOKIES(self, value: str):
        self.cookies.douyin = value

    @property
    def DY_LIVE_COOKIES(self) -> str:
        return self.cookies.douyin_live

    @DY_LIVE_COOKIES.setter
    def DY_LIVE_COOKIES(self, value: str):
        self.cookies.douyin_live = value

    @property
    def QUARK_COOKIES(self) -> str:
        return self.cookies.quark

    @QUARK_COOKIES.setter
    def QUARK_COOKIES(self, value: str):
        self.cookies.quark = value

    @property
    def XIANYU_COOKIES(self) -> str:
        return self.cookies.xianyu

    @XIANYU_COOKIES.setter
    def XIANYU_COOKIES(self, value: str):
        self.cookies.xianyu = value

    @property
    def DOWNLOAD_PATH(self) -> str:
        return self.download.path

    @property
    def EXCEL_PATH(self) -> str:
        return self.download.excel_path

    @property
    def SECRET_KEY(self) -> str:
        return self.security.secret_key

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return self.security.access_token_expire_minutes

    @property
    def REQUEST_TIMEOUT(self) -> int:
        return self.request.timeout

    @property
    def MAX_RETRIES(self) -> int:
        return self.request.max_retries

    @property
    def LOG_PATH(self) -> str:
        return self.log.path

    @property
    def LOG_LEVEL(self) -> str:
        return self.log.level

    @property
    def LOG_ROTATION(self) -> str:
        return self.log.rotation

    @property
    def LOG_RETENTION(self) -> str:
        return self.log.retention


def _find_config_file() -> Path:
    """查找配置文件"""
    # 按优先级查找配置文件
    runtime_dir = get_runtime_config_dir()
    config_paths = [
        runtime_dir / "config.yaml",
        runtime_dir / "config.yml",
        Path.cwd() / "config" / "config.yaml",
        Path.cwd() / "config" / "config.yml",
        Path(__file__).parent.parent / "config" / "config.yaml",
        Path(__file__).parent.parent / "config" / "config.yml",
        Path.cwd() / "config.yaml",
        Path.cwd() / "config.yml",
    ]
    
    for path in config_paths:
        if path.exists():
            return path
    
    # 返回默认路径
    return runtime_dir / "config.yaml"


def _load_yaml_config() -> dict:
    """加载 YAML 配置文件"""
    config_path = _find_config_file()
    
    if not config_path.exists():
        # 创建默认配置文件
        default_config = DEFAULT_BACKEND_CONFIG
        
        # 确保目录存在
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)
        
        return default_config
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    
    return config


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    config_data = _load_yaml_config()
    return Settings(**config_data)


# 全局配置实例
settings = get_settings()
