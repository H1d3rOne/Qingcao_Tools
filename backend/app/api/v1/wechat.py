from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import get_wechat_service
from app.modules.base.schemas import ApiResponse
from app.modules.wechat import (
    ClearWechatDownloadTasksRequest,
    DownloadWechatVideoRequest,
    ListenerStatus,
    QueueWechatDownloadRequest,
    UpdateWechatProxyConfigRequest,
    UpdateWechatDownloadDirRequest,
    WechatCertificateStatus,
    WechatDownloadTaskItem,
    WechatDownloadTaskListResponse,
    WechatProxyConfig,
    WechatService,
    WechatVideoListResponse,
)

router = APIRouter(prefix="/wechat", tags=["视频号下载"])


@router.post("/listener/start", response_model=ApiResponse[ListenerStatus])
async def start_listener(service: WechatService = Depends(get_wechat_service)):
    try:
        status = await service.start_listener()
        return ApiResponse(data=status, message="监听已开启")
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.post("/listener/stop", response_model=ApiResponse[ListenerStatus])
async def stop_listener(service: WechatService = Depends(get_wechat_service)):
    try:
        status = await service.stop_listener()
        return ApiResponse(data=status, message="监听已关闭")
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.get("/listener/status", response_model=ApiResponse[ListenerStatus])
async def get_listener_status(service: WechatService = Depends(get_wechat_service)):
    try:
        status = await service.get_listener_status()
        return ApiResponse(data=status)
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.get("/config", response_model=ApiResponse[WechatProxyConfig])
async def get_proxy_config(service: WechatService = Depends(get_wechat_service)):
    try:
        config = await service.get_proxy_config()
        return ApiResponse(data=config)
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.post("/config", response_model=ApiResponse[WechatProxyConfig])
async def update_proxy_config(
    request: UpdateWechatProxyConfigRequest,
    service: WechatService = Depends(get_wechat_service),
):
    try:
        config = await service.update_proxy_config(request.proxy_port, request.local_server_port)
        return ApiResponse(data=config, message="端口配置已保存")
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.get("/certificate/status", response_model=ApiResponse[WechatCertificateStatus])
async def get_certificate_status(service: WechatService = Depends(get_wechat_service)):
    try:
        status = await service.get_certificate_status()
        return ApiResponse(data=status)
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.post("/certificate/install", response_model=ApiResponse[WechatCertificateStatus])
async def install_certificate(service: WechatService = Depends(get_wechat_service)):
    try:
        status = await service.install_certificate()
        return ApiResponse(data=status, message=status.message or "证书安装完成")
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.get("/videos", response_model=ApiResponse[WechatVideoListResponse])
async def get_videos(service: WechatService = Depends(get_wechat_service)):
    try:
        videos = await service.get_video_list()
        return ApiResponse(data=videos)
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.post("/videos/clear", response_model=ApiResponse[dict])
async def clear_videos(service: WechatService = Depends(get_wechat_service)):
    try:
        result = await service.clear_video_list()
        return ApiResponse(data=result, message=f"已清空 {result['cleared_count']} 条视频记录")
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.get("/download/tasks", response_model=ApiResponse[WechatDownloadTaskListResponse])
async def get_download_tasks(service: WechatService = Depends(get_wechat_service)):
    try:
        tasks = await service.get_download_task_list()
        return ApiResponse(data=tasks)
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.post("/download/dir", response_model=ApiResponse[ListenerStatus])
async def update_download_dir(
    request: UpdateWechatDownloadDirRequest,
    service: WechatService = Depends(get_wechat_service),
):
    try:
        status = await service.set_download_dir(request.path)
        return ApiResponse(data=status, message="下载目录已更新")
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.post("/download/dir/select", response_model=ApiResponse[ListenerStatus])
async def select_download_dir(service: WechatService = Depends(get_wechat_service)):
    try:
        status, selected = await service.select_download_dir()
        return ApiResponse(data=status, message="下载目录已更新" if selected else "已取消选择")
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.post("/download/tasks/clear", response_model=ApiResponse[dict])
async def clear_download_tasks(
    request: ClearWechatDownloadTasksRequest,
    service: WechatService = Depends(get_wechat_service),
):
    try:
        result = await service.clear_download_tasks(request.statuses)
        return ApiResponse(data=result, message=f"已清空 {result['cleared_count']} 条任务")
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.post("/download/tasks", response_model=ApiResponse[WechatDownloadTaskItem])
async def queue_download_task(
    request: QueueWechatDownloadRequest,
    service: WechatService = Depends(get_wechat_service),
):
    try:
        task, action = await service.queue_download(request.video_id)

        if action == "existing":
            message = "下载任务已在列表中"
        elif action == "requeued":
            message = "任务已重新加入下载队列"
        else:
            message = "已加入下载任务列表，后台已开始下载"

        return ApiResponse(data=WechatDownloadTaskItem(**task), message=message)
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.post("/download/tasks/{task_id}/retry", response_model=ApiResponse[WechatDownloadTaskItem])
async def retry_download_task(task_id: str, service: WechatService = Depends(get_wechat_service)):
    try:
        task = await service.retry_download_task(task_id)
        return ApiResponse(data=WechatDownloadTaskItem(**task), message="任务已重新加入下载队列")
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.post("/download/tasks/{task_id}/cancel", response_model=ApiResponse[dict])
async def cancel_download_task(task_id: str, service: WechatService = Depends(get_wechat_service)):
    try:
        result = await service.cancel_download_task(task_id)
        message = "已发送取消请求" if result.get("status") == "cancelling" else "任务已取消"
        return ApiResponse(data=result, message=message)
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.post("/download/tasks/{task_id}/open-dir", response_model=ApiResponse[dict])
async def open_download_task_dir(task_id: str, service: WechatService = Depends(get_wechat_service)):
    try:
        result = await service.open_download_directory(task_id)
        return ApiResponse(data=result, message="已打开下载目录")
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.get("/download/tasks/{task_id}/preview")
async def preview_download_task(task_id: str, service: WechatService = Depends(get_wechat_service)):
    try:
        file_path = await service.get_download_preview_path(task_id)
        return FileResponse(file_path, media_type="video/mp4", filename=None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/download/tasks/{task_id}", response_model=ApiResponse[dict])
async def delete_download_task(task_id: str, service: WechatService = Depends(get_wechat_service)):
    try:
        result = await service.delete_download_task(task_id)
        return ApiResponse(data=result, message="任务已删除")
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))


@router.post("/download", response_model=ApiResponse[dict])
async def download_video(
    request: DownloadWechatVideoRequest,
    service: WechatService = Depends(get_wechat_service),
):
    try:
        result = await service.download_video(request.video_id)
        return ApiResponse(data=result, message="下载并解密完成")
    except Exception as exc:
        return ApiResponse(success=False, error=str(exc))
