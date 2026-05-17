"""
爬虫基类
"""
import re
from typing import Optional
from abc import ABC, abstractmethod

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

from app.core.config import settings


class BaseSpider(ABC):
    """爬虫基类"""
    
    # 默认请求头
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    
    def __init__(self, timeout: int = None):
        self.timeout = timeout or settings.REQUEST_TIMEOUT
        self.client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        await self.init_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def init_client(self):
        """初始化 HTTP 客户端"""
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            http2=False
        )
    
    async def close(self):
        """关闭客户端"""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def request(
        self,
        method: str,
        url: str,
        raise_for_status: bool = True,
        **kwargs
    ) -> httpx.Response:
        """发送请求（带重试）"""
        if not self.client:
            await self.init_client()
        
        logger.debug(f"Request: {method} {url}")
        response = await self.client.request(method, url, **kwargs)
        
        # 默认检查状态码，但对于某些接口可能需要处理错误响应
        if raise_for_status:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP 错误: {e.response.status_code} - {e.response.text[:200]}")
                raise
        
        return response
    
    @staticmethod
    def extract_aweme_id(url: str) -> Optional[str]:
        """从 URL 提取作品 ID"""
        # 匹配多种 URL 格式
        patterns = [
            r'video/(\d+)',
            r'aweme_id=(\d+)',
            r'/(\d{19})',
            r'modal_id=(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    async def resolve_short_url(url: str) -> str:
        """解析短链接，获取重定向后的真实 URL"""
        # 检查是否是短链接格式
        short_url_patterns = [
            r'https?://v\.douyin\.com/',
            r'https?://vm\.douyin\.com/',
        ]
        is_short_url = any(re.match(pattern, url) for pattern in short_url_patterns)

        if not is_short_url:
            return url

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                response = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
                })
                final_url = str(response.url)
                logger.info(f"短链接解析: {url} -> {final_url}")
                return final_url
        except Exception as e:
            logger.error(f"短链接解析失败: {url}, 错误: {e}")
            return url
    
    @staticmethod
    def extract_sec_uid(url: str) -> Optional[str]:
        """从 URL 提取用户 sec_uid"""
        patterns = [
            r'user/([^?/]+)',
            r'sec_user_id=([^&]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
