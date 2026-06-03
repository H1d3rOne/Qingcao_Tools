"""
搜索服务
"""
from app.modules.douyin.video.schemas.search import SearchPageResult
from app.modules.douyin.video.spiders.douyin import DouyinSpider


class SearchService:
    """搜索服务"""

    def __init__(self, db, spider: DouyinSpider):
        self.db = db
        self.spider = spider

    async def search_works(
        self,
        keyword: str,
        offset: str = "0",
        count: int = 25,
        search_id: str = "",
        sort_type: str = "0",
        publish_time: str = "0",
        filter_duration: str = "",
        search_range: str = "",
        content_type: str = ""
    ) -> SearchPageResult:
        result = await self.spider.search_works(
            keyword, offset, count, search_id, sort_type, publish_time,
            filter_duration, search_range, content_type
        )
        return SearchPageResult(
            keyword=keyword,
            items=result["items"],
            has_more=result["has_more"],
            next_offset=result["next_offset"],
            search_id=result.get("search_id", "")
        )

    async def search_videos(
        self,
        keyword: str,
        offset: str = "0",
        count: int = 25,
        search_id: str = "",
        sort_type: str = "0",
        publish_time: str = "0",
        filter_duration: str = "",
        search_range: str = "0"
    ) -> SearchPageResult:
        result = await self.spider.search_videos(
            keyword, offset, count, search_id, sort_type,
            publish_time, filter_duration, search_range
        )
        return SearchPageResult(
            keyword=keyword,
            items=result["items"],
            has_more=result["has_more"],
            next_offset=result["next_offset"],
            search_id=result.get("search_id", "")
        )

    async def search_users(
        self,
        keyword: str,
        offset: str = "0",
        count: int = 25,
        search_id: str = ""
    ) -> SearchPageResult:
        result = await self.spider.search_users(keyword, offset, count, search_id)
        return SearchPageResult(
            keyword=keyword,
            items=result["items"],
            has_more=result["has_more"],
            next_offset=result["next_offset"],
            search_id=result.get("search_id", "")
        )

    async def search_live(self, keyword: str, offset: str = "0", count: int = 25) -> SearchPageResult:
        result = await self.spider.search_live(keyword, offset, count)
        return SearchPageResult(
            keyword=keyword,
            items=result["items"],
            has_more=result["has_more"],
            next_offset=result["next_offset"]
        )
