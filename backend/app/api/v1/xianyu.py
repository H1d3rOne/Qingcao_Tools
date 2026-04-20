"""
闲鱼相关 API
"""
import asyncio
import contextlib

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, WebSocket, WebSocketDisconnect
from loguru import logger

from app.api.deps import get_xianyu_service
from app.modules.base.schemas import ApiResponse
from app.modules.xianyu import (
    XianyuAuthCheckLoginRequest,
    XianyuAuthCheckLoginResponse,
    XianyuAuthLoginRequest,
    XianyuAuthLoginResponse,
    XianyuAuthLogoutResponse,
    XianyuAuthStatusResponse,
    XianyuChatClearRequest,
    XianyuChatClearResult,
    XianyuChatConversationPage,
    XianyuChatCreateSessionRequest,
    XianyuChatImageSendRequest,
    XianyuChatMarkReadRequest,
    XianyuChatMessagePage,
    XianyuChatMessagesQuery,
    XianyuChatOpenSessionRequest,
    XianyuChatOpenSessionResponse,
    XianyuChatProfile,
    XianyuChatRecallRequest,
    XianyuChatSendRequest,
    XianyuChatSendResult,
    XianyuItemDetail,
    XianyuMonitorHit,
    XianyuMonitorTask,
    XianyuMonitorTaskCreate,
    XianyuMonitorTaskUpdate,
    XianyuSearchRequest,
    XianyuSearchResult,
    XianyuService,
    XianyuUserProfile,
)

router = APIRouter(prefix="/xianyu", tags=["闲鱼"])


@router.get("/auth/qrcode", response_model=XianyuAuthLoginResponse)
async def get_xianyu_auth_qrcode(
    service: XianyuService = Depends(get_xianyu_service),
):
    result = service.get_login_qrcode()
    return XianyuAuthLoginResponse(**result)


@router.post("/auth/check-login", response_model=XianyuAuthCheckLoginResponse)
async def check_xianyu_auth_login(
    request: XianyuAuthCheckLoginRequest,
    service: XianyuService = Depends(get_xianyu_service),
):
    result = service.check_login_status(request.qrcode_token)
    return XianyuAuthCheckLoginResponse(**result)


@router.post("/auth/login", response_model=XianyuAuthLoginResponse)
async def login_xianyu(
    request: XianyuAuthLoginRequest,
    service: XianyuService = Depends(get_xianyu_service),
):
    result = service.login(method=request.method, cookies=request.cookies)
    return XianyuAuthLoginResponse(
        success=result["success"],
        message=result["message"],
        login_token=result.get("cookies"),
        qrcode_url=result.get("qrcode_url"),
        qrcode_token=result.get("qrcode_token"),
        qrcode_image=result.get("qrcode_image"),
    )


@router.get("/auth/status", response_model=XianyuAuthStatusResponse)
async def get_xianyu_auth_status(
    service: XianyuService = Depends(get_xianyu_service),
):
    return XianyuAuthStatusResponse(**(await service.get_auth_status()))


@router.post("/auth/logout", response_model=XianyuAuthLogoutResponse)
async def logout_xianyu(
    service: XianyuService = Depends(get_xianyu_service),
):
    return XianyuAuthLogoutResponse(**service.logout())


@router.get("/monitor/tasks", response_model=ApiResponse[list[XianyuMonitorTask]])
async def list_xianyu_monitor_tasks(
    service: XianyuService = Depends(get_xianyu_service),
):
    """获取闲鱼关键词监控任务列表"""
    try:
        await service.ensure_monitor_runner()
        return ApiResponse(data=service.list_monitor_tasks())
    except Exception as exc:
        logger.error(f"获取闲鱼监控任务失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.post("/monitor/tasks", response_model=ApiResponse[XianyuMonitorTask])
async def create_xianyu_monitor_task(
    request: XianyuMonitorTaskCreate,
    service: XianyuService = Depends(get_xianyu_service),
):
    """创建闲鱼关键词监控任务"""
    try:
        task = service.create_monitor_task(request)
        await service.ensure_monitor_runner()
        return ApiResponse(data=task)
    except Exception as exc:
        logger.error(f"创建闲鱼监控任务失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.put("/monitor/tasks/{task_id}", response_model=ApiResponse[XianyuMonitorTask])
async def update_xianyu_monitor_task(
    task_id: str,
    request: XianyuMonitorTaskUpdate,
    service: XianyuService = Depends(get_xianyu_service),
):
    """更新闲鱼关键词监控任务"""
    try:
        return ApiResponse(data=service.update_monitor_task(task_id, request))
    except Exception as exc:
        logger.error(f"更新闲鱼监控任务失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.delete("/monitor/tasks/{task_id}", response_model=ApiResponse[dict])
async def delete_xianyu_monitor_task(
    task_id: str,
    service: XianyuService = Depends(get_xianyu_service),
):
    """删除闲鱼关键词监控任务"""
    try:
        deleted = service.delete_monitor_task(task_id)
        return ApiResponse(data={"deleted": deleted})
    except Exception as exc:
        logger.error(f"删除闲鱼监控任务失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.post("/monitor/tasks/{task_id}/toggle", response_model=ApiResponse[XianyuMonitorTask])
async def toggle_xianyu_monitor_task(
    task_id: str,
    service: XianyuService = Depends(get_xianyu_service),
):
    """切换闲鱼关键词监控任务启用状态"""
    try:
        return ApiResponse(data=service.toggle_monitor_task(task_id))
    except Exception as exc:
        logger.error(f"切换闲鱼监控任务失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.post("/monitor/tasks/{task_id}/run", response_model=ApiResponse[XianyuMonitorTask])
async def run_xianyu_monitor_task(
    task_id: str,
    service: XianyuService = Depends(get_xianyu_service),
):
    """立即执行闲鱼关键词监控任务"""
    try:
        return ApiResponse(data=await service.run_monitor_task(task_id))
    except Exception as exc:
        logger.error(f"执行闲鱼监控任务失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.get("/monitor/tasks/{task_id}/hits", response_model=ApiResponse[list[XianyuMonitorHit]])
async def get_xianyu_monitor_hits(
    task_id: str,
    service: XianyuService = Depends(get_xianyu_service),
):
    """获取闲鱼关键词监控任务最近命中"""
    try:
        return ApiResponse(data=service.get_monitor_hits(task_id))
    except Exception as exc:
        logger.error(f"获取闲鱼监控命中失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.post("/search", response_model=ApiResponse[XianyuSearchResult])
async def search_xianyu(
    request: XianyuSearchRequest,
    service: XianyuService = Depends(get_xianyu_service),
):
    """闲鱼搜索"""
    try:
        result = await service.search(request)
        return ApiResponse(data=result)
    except Exception as exc:
        logger.error(f"闲鱼搜索失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.get("/detail", response_model=ApiResponse[XianyuItemDetail])
async def get_xianyu_item_detail(
    item_id: str = Query(..., min_length=1, description="宝贝 ID"),
    service: XianyuService = Depends(get_xianyu_service),
):
    """获取闲鱼宝贝详情"""
    try:
        result = await service.get_item_detail(item_id)
        return ApiResponse(data=result)
    except Exception as exc:
        logger.error(f"获取闲鱼宝贝详情失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.get("/user/profile", response_model=ApiResponse[XianyuUserProfile])
async def get_xianyu_user_profile(
    service: XianyuService = Depends(get_xianyu_service),
):
    """获取闲鱼登录用户信息"""
    try:
        result = await service.get_user_profile()
        return ApiResponse(data=result)
    except Exception as exc:
        logger.error(f"获取闲鱼用户信息失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.get("/chat/profile", response_model=ApiResponse[XianyuChatProfile])
async def get_xianyu_chat_profile(
    service: XianyuService = Depends(get_xianyu_service),
):
    """获取闲鱼聊天当前账号信息"""
    try:
        result = await service.get_chat_profile()
        return ApiResponse(data=result)
    except Exception as exc:
        logger.error(f"获取闲鱼聊天账号信息失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.get("/chat/conversations", response_model=ApiResponse[XianyuChatConversationPage])
async def get_xianyu_chat_conversations(
    offset: int = Query(0, ge=0, description="偏移"),
    limit: int = Query(20, ge=1, le=50, description="数量"),
    service: XianyuService = Depends(get_xianyu_service),
):
    """获取闲鱼聊天会话列表"""
    try:
        result = await service.list_chat_conversations(offset=offset, limit=limit)
        return ApiResponse(data=result)
    except Exception as exc:
        logger.error(f"获取闲鱼聊天会话列表失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.get("/chat/user-info", response_model=ApiResponse[dict])
async def get_xianyu_user_info(
    user_id: str = Query(..., description="用户ID"),
    service: XianyuService = Depends(get_xianyu_service),
):
    """获取闲鱼用户信息（昵称、头像等）"""
    try:
        result = await service.get_peer_user_info(user_id)
        return ApiResponse(data=result)
    except Exception as exc:
        logger.error(f"获取闲鱼用户信息失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.post("/chat/open-session", response_model=XianyuChatOpenSessionResponse)
async def open_xianyu_chat_session(
    request: XianyuChatOpenSessionRequest,
    service: XianyuService = Depends(get_xianyu_service),
):
    """在项目内打开聊天会话"""
    try:
        result = await service.open_chat_session(
            item_id=request.item_id,
            peer_user_id=request.peer_user_id,
        )
        return XianyuChatOpenSessionResponse(**result)
    except Exception as exc:
        logger.error(f"打开闲鱼聊天会话失败: {exc}")
        return XianyuChatOpenSessionResponse(success=False, message=str(exc))


@router.get("/chat/messages", response_model=ApiResponse[XianyuChatMessagePage])
async def get_xianyu_chat_messages(
    cid: str = Query(..., min_length=1, description="会话 CID"),
    cursor: str | None = Query(None, description="消息游标"),
    limit: int = Query(20, ge=1, le=50, description="数量"),
    direction: str = Query("prev", description="方向 prev/next"),
    service: XianyuService = Depends(get_xianyu_service),
):
    """获取闲鱼聊天消息"""
    try:
        result = await service.list_chat_messages(
            cid=cid,
            cursor=cursor,
            limit=limit,
            direction=direction,
        )
        return ApiResponse(data=result)
    except Exception as exc:
        logger.error(f"获取闲鱼聊天消息失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.post("/chat/send", response_model=ApiResponse[XianyuChatSendResult])
async def send_xianyu_chat_message(
    request: XianyuChatSendRequest,
    service: XianyuService = Depends(get_xianyu_service),
):
    """发送闲鱼聊天文本消息"""
    try:
        result = await service.send_chat_text(cid=request.cid, text=request.text)
        return ApiResponse(data=result)
    except Exception as exc:
        logger.error(f"发送闲鱼聊天消息失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.post("/chat/clear-red-point", response_model=ApiResponse[XianyuChatClearResult])
async def clear_xianyu_chat_red_point(
    request: XianyuChatClearRequest,
    service: XianyuService = Depends(get_xianyu_service),
):
    """清理闲鱼聊天会话红点"""
    try:
        result = await service.clear_chat_red_point(request.cids)
        return ApiResponse(data=result)
    except Exception as exc:
        logger.error(f"清理闲鱼聊天红点失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.post("/chat/send-image", response_model=ApiResponse[XianyuChatSendResult])
async def send_xianyu_chat_image(
    request: XianyuChatImageSendRequest,
    service: XianyuService = Depends(get_xianyu_service),
):
    """发送闲鱼聊天图片消息"""
    try:
        result = await service.send_chat_image(
            cid=request.cid,
            image_url=request.image_url,
            width=request.width,
            height=request.height,
        )
        return ApiResponse(data=result)
    except Exception as exc:
        logger.error(f"发送闲鱼图片消息失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.post("/chat/recall", response_model=ApiResponse[dict])
async def recall_xianyu_chat_message(
    request: XianyuChatRecallRequest,
    service: XianyuService = Depends(get_xianyu_service),
):
    """撤回闲鱼聊天消息"""
    try:
        result = await service.recall_chat_message(request.message_id)
        return ApiResponse(data={"success": result})
    except Exception as exc:
        logger.error(f"撤回闲鱼聊天消息失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.post("/chat/mark-read", response_model=ApiResponse[dict])
async def mark_xianyu_chat_read(
    request: XianyuChatMarkReadRequest,
    service: XianyuService = Depends(get_xianyu_service),
):
    """标记闲鱼聊天消息已读"""
    try:
        result = await service.mark_chat_read(request.cid)
        return ApiResponse(data={"success": result})
    except Exception as exc:
        logger.error(f"标记闲鱼聊天已读失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.post("/chat/create-session", response_model=ApiResponse[dict])
async def create_xianyu_chat_session(
    request: XianyuChatCreateSessionRequest,
    service: XianyuService = Depends(get_xianyu_service),
):
    """创建闲鱼聊天会话"""
    try:
        result = await service.create_chat_session(
            peer_user_id=request.peer_user_id,
            item_id=request.item_id,
        )
        return ApiResponse(data=result)
    except Exception as exc:
        logger.error(f"创建闲鱼聊天会话失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.post("/chat/upload-and-send-image", response_model=ApiResponse[XianyuChatSendResult])
async def upload_and_send_xianyu_chat_image(
    cid: str = Form(..., description="会话 CID"),
    file: UploadFile = File(..., description="图片文件"),
    service: XianyuService = Depends(get_xianyu_service),
):
    """上传图片并发送闲鱼聊天消息"""
    try:
        content = await file.read()
        result = await service.upload_and_send_chat_image(
            cid=cid,
            filename=file.filename or "image.png",
            content=content,
            content_type=file.content_type or "image/png",
        )
        return ApiResponse(data=result)
    except Exception as exc:
        logger.error(f"上传并发送闲鱼图片消息失败: {exc}")
        return ApiResponse(success=False, error=str(exc))


@router.websocket("/chat/ws")
async def websocket_xianyu_chat_proxy(
    websocket: WebSocket,
):
    """闲鱼聊天实时推送代理"""
    service = get_xianyu_service()
    await websocket.accept()
    chat_client = None
    relay_task: asyncio.Task | None = None
    token_refresh_task: asyncio.Task | None = None

    try:
        chat_client = await service.open_chat_ws_client()
        await websocket.send_json({"type": "connected"})

        async def relay_pushes():
            while True:
                payload = await chat_client.next_push()
                decoded = service.decode_chat_push(payload)
                await websocket.send_json(
                    {
                        "type": "push",
                        "lwp": payload.get("lwp"),
                        "headers": payload.get("headers"),
                        "body": payload.get("body"),
                        "decoded": decoded,
                    }
                )
                try:
                    await service.maybe_auto_reply_from_decoded_push(chat_client.profile, decoded)
                except Exception as exc:
                    logger.warning(f"闲鱼聊天 AI 自动回复失败: {exc}")

        async def token_refresh_loop():
            """定时刷新 token，参照 XianYuApis 的 _token_refresh_loop（600 秒间隔）"""
            while True:
                await asyncio.sleep(600)
                try:
                    cookie = service._require_xianyu_cookie()
                    async with service._create_http_client(cookie) as client:
                        await service._refresh_login_state(client)
                    logger.debug("闲鱼聊天 token 定时刷新成功")
                except Exception as exc:
                    logger.warning(f"闲鱼聊天 token 定时刷新失败: {exc}")

        relay_task = asyncio.create_task(relay_pushes())
        token_refresh_task = asyncio.create_task(token_refresh_loop())

        while True:
            try:
                payload = await websocket.receive_json()
            except RuntimeError:
                payload = {"action": "ping"}

            action = str(payload.get("action") or "ping")
            if action == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if action == "close":
                break
    except WebSocketDisconnect:
        logger.info("闲鱼聊天代理 WebSocket 已断开")
    except Exception as exc:
        logger.error(f"闲鱼聊天代理 WebSocket 失败: {exc}")
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        if token_refresh_task:
            token_refresh_task.cancel()
            with contextlib.suppress(Exception):
                await token_refresh_task
        if relay_task:
            relay_task.cancel()
            with contextlib.suppress(Exception):
                await relay_task
        if chat_client:
            await chat_client.close()
        with contextlib.suppress(Exception):
            await websocket.send_json({"type": "disconnected"})
