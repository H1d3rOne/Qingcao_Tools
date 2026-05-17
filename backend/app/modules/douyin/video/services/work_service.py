"""
作品服务
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work import Work
from app.modules.douyin.video.schemas.work import WorkCreate, WorkResponse, DownloadResult
from app.db.repositories.work_repo import WorkRepository
from app.modules.douyin.video.spiders.douyin import DouyinSpider
from app.core.config import settings
from app.utils.download import download_file

import os
import aiofiles
import json


class WorkService:
    """作品服务"""
    
    def __init__(self, db: AsyncSession, spider: DouyinSpider):
        self.db = db
        self.spider = spider
        self.repo = WorkRepository(db)
    
    async def get_work_info(self, url: str) -> WorkResponse:
        """获取作品信息"""
        # 从爬虫获取
        work_data = await self.spider.get_work_info(url)
        
        # 保存到数据库 - 只保存数据库支持的字段
        db_fields = {
            'aweme_id', 'title', 'desc', 'author_uid', 'author_nickname', 
            'author_avatar', 'author_sec_uid', 'cover_url', 'video_url', 
            'images', 'duration', 'music_title', 'digg_count', 'comment_count',
            'share_count', 'collect_count', 'play_count', 'is_video', 
            'create_time', 'work_url'
        }
        db_data = {k: v for k, v in work_data.items() if k in db_fields}
        work = await self.repo.create_or_update(db_data)
        
        # 返回完整数据（包含 video_qualities）
        return WorkResponse(
            **{k: v for k, v in work_data.items() if k in db_fields},
            id=work.id,
            created_at=work.created_at,
            updated_at=work.updated_at,
        )
    
    async def get_work_comments(self, url: str, limit: int = 20, cursor: int = 0) -> dict:
        """获取作品评论"""
        comments = await self.spider.get_work_comments(url, limit, cursor)
        # 返回带分页信息的结构
        return {
            "data": comments,
            "has_more": len(comments) >= limit,
            "cursor": cursor + len(comments)
        }
    
    async def download_work(self, url: str, save_type: str = "media", quality: str = "super") -> DownloadResult:
        """下载作品 - 返回下载链接供前端使用"""
        work_data = await self.spider.get_work_info(url)
        
        aweme_id = work_data.get("aweme_id", "")
        author = work_data.get("author_nickname", "未知作者")
        title = work_data.get("title", "")
        
        # 获取不同质量的视频链接
        video_qualities = work_data.get("video_qualities")
        
        # 根据选择的质量获取视频URL
        selected_video_url = None
        if video_qualities and quality in video_qualities:
            selected_video_url = video_qualities[quality]["url"]
        else:
            # 如果没有指定质量或质量不存在，使用默认视频URL
            selected_video_url = work_data.get("video_url")
        
        # 获取图片列表
        images = work_data.get("images")
        
        # 生成文件名
        filename = f"{aweme_id}.mp4" if selected_video_url else None
        
        # 保存数据到数据库 - 只保存数据库支持的字段
        db_fields = {
            'aweme_id', 'title', 'desc', 'author_uid', 'author_nickname', 
            'author_avatar', 'author_sec_uid', 'cover_url', 'video_url', 
            'images', 'duration', 'music_title', 'digg_count', 'comment_count',
            'share_count', 'collect_count', 'play_count', 'is_video', 
            'create_time', 'work_url'
        }
        db_data = {k: v for k, v in work_data.items() if k in db_fields}
        await self.repo.create_or_update(db_data)
        
        return DownloadResult(
            title=title,
            author=author,
            aweme_id=aweme_id,
            video_url=selected_video_url,
            video_qualities=video_qualities,
            images=images,
            filename=filename,
            selected_quality=quality
        )
    
    async def get_works_by_author(self, author_uid: str, limit: int = 20) -> List[WorkResponse]:
        """获取作者的作品列表"""
        works = await self.repo.get_by_author(author_uid, limit)
        return [WorkResponse.from_orm(w) for w in works]
