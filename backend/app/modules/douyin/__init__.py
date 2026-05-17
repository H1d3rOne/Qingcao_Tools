"""
抖音模块
包含视频解析和直播监听功能
"""
from app.modules.douyin.common import DouyinAuth, auth, BaseSpider
from app.modules.douyin.video import DouyinSpider, WorkService, UserService, SearchService
from app.modules.douyin.live import DouyinLiveSpider, LiveService

__all__ = [
    # 共享组件
    'DouyinAuth', 'auth', 'BaseSpider',
    # 视频模块
    'DouyinSpider', 'WorkService', 'UserService', 'SearchService',
    # 直播模块
    'DouyinLiveSpider', 'LiveService',
]
