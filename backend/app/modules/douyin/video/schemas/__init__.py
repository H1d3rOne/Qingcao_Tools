"""
视频模块数据模型
"""
from app.modules.douyin.video.schemas.work import (
    WorkBase, WorkCreate, WorkResponse,
    WorkInfoRequest, WorkCommentsRequest, WorkDownloadRequest,
    DownloadResult
)
from app.modules.douyin.video.schemas.user import (
    UserBase, UserResponse, UserInfoRequest, UserWorksRequest
)
from app.modules.douyin.video.schemas.search import (
    SearchWorkRequest, SearchUserRequest, SearchLiveRequest, SearchResult
)

__all__ = [
    # Work
    'WorkBase', 'WorkCreate', 'WorkResponse',
    'WorkInfoRequest', 'WorkCommentsRequest', 'WorkDownloadRequest', 'DownloadResult',
    # User
    'UserBase', 'UserResponse', 'UserInfoRequest', 'UserWorksRequest',
    # Search
    'SearchWorkRequest', 'SearchUserRequest', 'SearchLiveRequest', 'SearchResult',
]
