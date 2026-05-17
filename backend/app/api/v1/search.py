"""
搜索相关 API
"""
from fastapi import APIRouter, Depends
from loguru import logger

from app.modules.base.schemas import ApiResponse
from app.modules.douyin.video.schemas.search import (
    SearchWorkRequest, SearchVideoRequest, SearchUserRequest, SearchLiveRequest, SearchResult
)
from app.modules.douyin.video.services.search_service import SearchService
from app.api.deps import get_search_service
from app.modules.douyin.common.auth import auth

router = APIRouter(prefix="/search", tags=["搜索"])


@router.post("/work", response_model=ApiResponse[SearchResult])
async def search_works(
    request: SearchWorkRequest,
    service: SearchService = Depends(get_search_service)
):
    """搜索作品"""
    try:
        logger.info(f"=== 搜索作品请求 ===")
        logger.info(f"  keyword: {request.keyword}")
        logger.info(f"  limit: {request.limit}")
        logger.info(f"  sort_type: {request.sort_type}")
        logger.info(f"  publish_time: {request.publish_time}")
        logger.info(f"  filter_duration: {request.filter_duration}")
        logger.info(f"  content_type: {request.content_type}")
        logger.info(f"  Cookie已配置: {auth.is_configured()}")

        result = await service.search_works(
            request.keyword,
            request.limit,
            request.sort_type,
            request.publish_time,
            request.filter_duration,
            request.content_type,
        )
        logger.info(f"  返回结果数量: {result.total}")
        return ApiResponse(data=result)
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return ApiResponse(success=False, error=str(e))


@router.post("/video", response_model=ApiResponse[SearchResult])
async def search_videos(
    request: SearchVideoRequest,
    service: SearchService = Depends(get_search_service)
):
    """搜索视频"""
    try:
        logger.info(f"=== 搜索视频请求 ===")
        logger.info(f"  keyword: {request.keyword}")
        logger.info(f"  limit: {request.limit}")
        logger.info(f"  sort_type: {request.sort_type}")
        logger.info(f"  publish_time: {request.publish_time}")
        logger.info(f"  filter_duration: {request.filter_duration}")
        logger.info(f"  search_range: {request.search_range}")

        result = await service.search_videos(
            request.keyword,
            request.limit,
            request.sort_type,
            request.publish_time,
            request.filter_duration,
            request.search_range,
        )
        logger.info(f"  返回结果数量: {result.total}")
        return ApiResponse(data=result)
    except Exception as e:
        logger.error(f"搜索视频失败: {e}")
        import traceback
        traceback.print_exc()
        return ApiResponse(success=False, error=str(e))


@router.post("/user", response_model=ApiResponse[SearchResult])
async def search_users(
    request: SearchUserRequest,
    service: SearchService = Depends(get_search_service)
):
    """搜索用户"""
    try:
        result = await service.search_users(request.keyword, request.limit)
        return ApiResponse(data=result)
    except Exception as e:
        logger.error(f"搜索用户失败: {e}")
        return ApiResponse(success=False, error=str(e))


@router.post("/live", response_model=ApiResponse[SearchResult])
async def search_live(
    request: SearchLiveRequest,
    service: SearchService = Depends(get_search_service)
):
    """搜索直播"""
    try:
        logger.info(f"=== 搜索直播请求 ===")
        logger.info(f"  keyword: {request.keyword}")
        logger.info(f"  limit: {request.limit}")
        result = await service.search_live(request.keyword, request.limit)
        logger.info(f"  返回结果数量: {result.total}")
        return ApiResponse(data=result)
    except Exception as e:
        logger.error(f"搜索直播失败: {e}")
        import traceback
        traceback.print_exc()
        return ApiResponse(success=False, error=str(e))
