"""
作品相关 API
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger
import httpx

from app.modules.base.schemas import ApiResponse
from app.modules.douyin.video.schemas.work import (
    WorkInfoRequest, WorkCommentsRequest,
    WorkDownloadRequest, WorkResponse, DownloadResult
)
from app.modules.douyin.video.services.work_service import WorkService
from app.modules.douyin.video.services.stats_service import stats_tracker
from app.api.deps import get_douyin_cookie_missing_response, get_work_service

router = APIRouter(prefix="/work", tags=["作品"])


@router.post("/info", response_model=ApiResponse[WorkResponse])
async def get_work_info(
    request: WorkInfoRequest,
    service: WorkService = Depends(get_work_service)
):
    """获取作品信息"""
    missing_cookie = get_douyin_cookie_missing_response()
    if missing_cookie:
        return missing_cookie

    try:
        # 支持 url 或 aweme_id 参数
        if request.url:
            work = await service.get_work_info(request.url)
        elif request.aweme_id:
            # 构建 URL
            url = f"https://www.douyin.com/video/{request.aweme_id}"
            work = await service.get_work_info(url)
        else:
            return ApiResponse(success=False, error="请提供 url 或 aweme_id 参数")
        stats_tracker.record_success()
        return ApiResponse(data=work)
    except Exception as e:
        stats_tracker.record_fail()
        return ApiResponse(success=False, error=str(e))


@router.post("/comments", response_model=ApiResponse[dict])
async def get_work_comments(
    request: WorkCommentsRequest,
    service: WorkService = Depends(get_work_service)
):
    """获取作品评论"""
    missing_cookie = get_douyin_cookie_missing_response()
    if missing_cookie:
        return missing_cookie

    try:
        # 支持 url 或 aweme_id 参数
        if request.url:
            url = request.url
        elif request.aweme_id:
            url = f"https://www.douyin.com/video/{request.aweme_id}"
        else:
            return ApiResponse(success=False, error="请提供 url 或 aweme_id 参数")
        
        count = request.count or request.limit
        comments = await service.get_work_comments(url, count, request.cursor)
        return ApiResponse(data=comments)
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.post("/download", response_model=ApiResponse[DownloadResult])
async def download_work(
    request: WorkDownloadRequest,
    service: WorkService = Depends(get_work_service)
):
    """下载作品 - 返回下载链接"""
    missing_cookie = get_douyin_cookie_missing_response()
    if missing_cookie:
        return missing_cookie

    try:
        # 支持 url 或 aweme_id 参数
        if request.url:
            url = request.url
        elif request.aweme_id:
            url = f"https://www.douyin.com/video/{request.aweme_id}"
        else:
            return ApiResponse(success=False, error="请提供 url 或 aweme_id 参数")
        
        result = await service.download_work(url, request.save_type, request.quality)
        stats_tracker.record_success()
        return ApiResponse(data=result, message="获取下载链接成功")
    except Exception as e:
        stats_tracker.record_fail()
        return ApiResponse(success=False, error=str(e))


@router.get("/proxy")
async def proxy_video(url: str, request: Request):
    """代理视频流 - 用于绕过防盗链"""
    try:
        logger.info(f"代理视频请求: {url[:100]}...")
        
        range_header = request.headers.get("range")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Referer": "https://www.douyin.com/",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
        }
        
        if range_header:
            headers["Range"] = range_header
        
        client = httpx.AsyncClient(timeout=60, follow_redirects=True)
        
        req = client.build_request("GET", url, headers=headers)
        response = await client.send(req, stream=True)
        
        logger.info(f"视频响应状态: {response.status_code}")
        logger.info(f"视频响应头: {dict(response.headers)}")
        
        if response.status_code >= 400:
            error_body = await response.aread()
            logger.error(f"视频请求失败: {response.status_code}, body: {error_body[:500]}")
            await response.aclose()
            await client.aclose()
            raise HTTPException(status_code=response.status_code, detail=f"视频源返回错误: {response.status_code}")
        
        response_headers = dict(response.headers)
        
        def filter_headers(h: dict) -> dict:
            skip = {"transfer-encoding", "content-encoding", "connection", "keep-alive"}
            return {k: v for k, v in h.items() if k.lower() not in skip}
        
        async def stream_generator():
            try:
                async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()
        
        return StreamingResponse(
            stream_generator(),
            status_code=response.status_code,
            media_type=response_headers.get("content-type", "video/mp4"),
            headers={
                **filter_headers(response_headers),
                "Accept-Ranges": "bytes",
                "Access-Control-Allow-Origin": "*",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"视频代理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
