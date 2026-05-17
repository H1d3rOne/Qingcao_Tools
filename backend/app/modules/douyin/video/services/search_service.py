"""
搜索服务
"""
import hashlib
from typing import Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.douyin.video.schemas.search import SearchResult
from app.modules.douyin.video.spiders.douyin import DouyinSpider


class SearchCache:
    """简单的内存缓存"""
    
    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, tuple[datetime, any]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
    
    def _make_key(self, *args, **kwargs) -> str:
        """生成缓存键"""
        key_str = f"{args}_{sorted(kwargs.items())}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[any]:
        """获取缓存"""
        if key in self._cache:
            created_at, value = self._cache[key]
            if datetime.now() - created_at < self._ttl:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: any):
        """设置缓存"""
        self._cache[key] = (datetime.now(), value)
    
    def clear_expired(self):
        """清理过期缓存"""
        now = datetime.now()
        expired_keys = [
            k for k, (created_at, _) in self._cache.items()
            if now - created_at >= self._ttl
        ]
        for k in expired_keys:
            del self._cache[k]


# 全局缓存实例（5分钟过期）
_search_cache = SearchCache(ttl_seconds=300)


class SearchService:
    """搜索服务"""
    
    def __init__(self, db: AsyncSession, spider: DouyinSpider):
        self.db = db
        self.spider = spider
        self.cache = _search_cache
    
    async def search_works(
        self,
        keyword: str,
        limit: int = 20,
        sort_type: str = "0",
        publish_time: str = "0",
        filter_duration: str = "",
        content_type: str = ""
    ) -> SearchResult:
        """搜索作品"""
        # 检查缓存
        cache_key = self.cache._make_key("works", keyword, limit, sort_type, publish_time, filter_duration, content_type)
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        works = await self.spider.search_works(
            keyword, limit, sort_type, publish_time, filter_duration, content_type=content_type
        )
        # 直接返回字典数据
        items = [w for w in works]
        
        result = SearchResult(
            keyword=keyword,
            total=len(items),
            items=items
        )
        
        # 缓存结果
        self.cache.set(cache_key, result)
        
        return result
    
    async def search_videos(
        self,
        keyword: str,
        limit: int = 20,
        sort_type: str = "0",
        publish_time: str = "0",
        filter_duration: str = "",
        search_range: str = "0"
    ) -> SearchResult:
        """搜索视频"""
        cache_key = self.cache._make_key("videos", keyword, limit, sort_type, publish_time, filter_duration, search_range)
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        videos = await self.spider.search_videos(
            keyword, limit, sort_type, publish_time, filter_duration, search_range
        )
        items = [v for v in videos]

        result = SearchResult(
            keyword=keyword,
            total=len(items),
            items=items
        )

        self.cache.set(cache_key, result)
        return result

    async def search_users(self, keyword: str, limit: int = 20) -> SearchResult:
        """搜索用户"""
        # 检查缓存
        cache_key = self.cache._make_key("users", keyword, limit)
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        users = await self.spider.search_users(keyword, limit)
        # 直接返回字典数据
        items = [u for u in users]
        
        result = SearchResult(
            keyword=keyword,
            total=len(items),
            items=items
        )
        
        # 缓存结果
        self.cache.set(cache_key, result)
        
        return result
    
    async def search_live(self, keyword: str, limit: int = 20) -> SearchResult:
        """搜索直播"""
        # 检查缓存
        cache_key = self.cache._make_key("live", keyword, limit)
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        lives = await self.spider.search_live(keyword, limit)
        items = lives
        
        result = SearchResult(
            keyword=keyword,
            total=len(items),
            items=items
        )
        
        # 缓存结果
        self.cache.set(cache_key, result)
        
        return result
