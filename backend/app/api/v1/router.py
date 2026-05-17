"""
API 路由聚合
"""
from fastapi import APIRouter

from app.api.v1 import work, user, search, live, settings, quark, notify, wechat, xianyu

api_router = APIRouter()

# 抖音解析模块
api_router.include_router(work.router, prefix="/douyin", tags=["抖音-作品"])
api_router.include_router(user.router, prefix="/douyin", tags=["抖音-用户"])
api_router.include_router(search.router, prefix="/douyin", tags=["抖音-搜索"])
api_router.include_router(live.router, prefix="/douyin", tags=["抖音-直播"])

# 夸克工具模块
api_router.include_router(quark.router, tags=["夸克工具"])

# 视频号下载
api_router.include_router(wechat.router)

# 闲鱼工具
api_router.include_router(xianyu.router)

# 消息推送
api_router.include_router(notify.router)

# 系统设置
api_router.include_router(settings.router)
