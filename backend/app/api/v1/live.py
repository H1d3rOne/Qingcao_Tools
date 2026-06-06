"""
直播 API 路由
"""
import asyncio
import json
import threading
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from loguru import logger

from app.api.deps import (
    DOUYIN_COOKIE_MISSING_MESSAGE,
    get_current_live_auth,
    get_douyin_cookie_missing_response,
    is_douyin_live_cookie_configured,
)
from app.modules.douyin.common.auth import DouyinAuth
from app.modules.douyin.live.spiders.live import DouyinLiveSpider, live_stream_cache
from app.modules.douyin.live.schemas.live import (
    LiveRoomInfo, LiveInfoRequest
)
from app.modules.base.schemas import ApiResponse

router = APIRouter(prefix="/live", tags=["直播"])


# 存储活跃的 WebSocket 连接
active_connections: dict[str, list[WebSocket]] = {}


@router.post("/info", response_model=ApiResponse[LiveRoomInfo])
async def get_live_room_info(
    request: LiveInfoRequest,
    auth: DouyinAuth = Depends(get_current_live_auth)
):
    """获取直播间信息 - 只支持直播链接
    
    Args:
        request.input: 抖音直播链接，如 https://live.douyin.com/802236344116
    """
    missing_cookie = get_douyin_cookie_missing_response(live=True)
    if missing_cookie:
        return missing_cookie

    spider = DouyinLiveSpider(request.input, auth)
    try:
        room_info = await spider.get_room_info()
        
        data = LiveRoomInfo(
            web_rid=room_info.get('web_rid', ''),
            room_id=room_info.get('room_id', ''),
            user_id=room_info.get('user_id', ''),
            title=room_info.get('title', ''),
            owner=room_info.get('owner', {}),
            stream_url=room_info.get('stream_url', {}),
            user_count=room_info.get('user_count', 0),
            status=room_info.get('status', 0),
        )
        return ApiResponse(data=data)
    except Exception as e:
        logger.error(f"获取直播间信息失败: {e}")
        return ApiResponse(success=False, error=str(e))


@router.websocket("/ws/{live_url:path}")
async def websocket_live_danmaku(websocket: WebSocket, live_url: str):
    """WebSocket 实时弹幕推送
    
    连接流程：
    1. 前端连接 WebSocket
    2. 后端获取直播间信息（room_id, ttwid 等）
    3. 后端连接抖音弹幕服务器
    4. 实时推送弹幕消息到前端
    
    消息格式：
    - connected: {'type': 'connected', 'room_info': {...}}
    - chat: {'type': 'chat', 'user': {...}, 'content': '...'}
    - gift: {'type': 'gift', 'user': {...}, 'gift': {...}, 'count': 1}
    - like: {'type': 'like', 'user': {...}, 'count': 1}
    - follow: {'type': 'follow', 'user': {...}}
    - member: {'type': 'member', 'user': {...}}
    - error: {'type': 'error', 'message': '...'}
    - disconnected: {'type': 'disconnected'}
    """
    from urllib.parse import unquote
    
    # 解码 URL
    live_url = unquote(live_url)
    logger.info(f"WebSocket 连接请求: {live_url}")
    
    await websocket.accept()

    if not is_douyin_live_cookie_configured():
        await websocket.send_json({
            'type': 'error',
            'message': DOUYIN_COOKIE_MISSING_MESSAGE
        })
        await websocket.close()
        return
    
    spider: Optional[DouyinLiveSpider] = None
    message_queue: list = []
    is_running = True
    
    def on_message(msg: dict):
        """消息回调 - 将消息放入队列"""
        if is_running:
            message_queue.append(msg)
    
    try:
        # 1. 获取房间信息
        spider = DouyinLiveSpider(live_url, get_current_live_auth())
        spider.set_message_callback(on_message)
        
        room_info = await spider.get_room_info()
        logger.info(f"WebSocket: 获取房间信息成功, room_id={room_info.get('room_id')}")
        
        # 2. 发送连接成功消息
        await websocket.send_json({
            'type': 'connected',
            'room_info': room_info
        })
        
        # 3. 检查是否有必要的参数
        if not room_info.get('room_id'):
            logger.error("WebSocket: 缺少 room_id，无法建立弹幕连接")
            await websocket.send_json({
                'type': 'error',
                'message': '无法获取房间ID'
            })
            return
        
        # 4. 启动弹幕采集（后台线程）
        ws_thread = threading.Thread(
            target=spider.start_ws,
            args=(room_info,),
            daemon=True
        )
        ws_thread.start()
        logger.info("WebSocket: 弹幕采集线程已启动")
        
        # 5. 等待连接建立
        # 真实浏览器弹幕监听需要启动浏览器、打开直播页并等待页面自己的
        # WebSocket。给 Windows/低配置机器更充足的启动时间，避免后端
        # 还在打开页面时前端先收到泛化的“弹幕连接超时”。
        max_wait = 60
        wait_count = 0
        startup_error = None
        while not spider.is_running and wait_count < max_wait * 10:
            # start_ws 在线程内启动失败时会通过 message_callback 推送 error。
            # 这里先把明确错误转发给前端，不再让前端等到“弹幕连接超时”。
            while message_queue:
                msg = message_queue.pop(0)
                await websocket.send_json(msg)
                if msg.get('type') == 'error':
                    startup_error = msg.get('message') or '弹幕连接失败'
                    break
            if startup_error:
                logger.warning(f"WebSocket: 弹幕启动失败: {startup_error}")
                return
            await asyncio.sleep(0.1)
            wait_count += 1
        
        if not spider.is_running:
            logger.warning("WebSocket: 弹幕连接超时")
            await websocket.send_json({
                'type': 'error',
                'message': '弹幕连接超时：真实浏览器未在 60 秒内捕获到抖音直播弹幕 WebSocket，请确认浏览器可正常打开、直播间正在直播且抖音直播 Cookie 有效'
            })
            return
        
        logger.info("WebSocket: 弹幕连接成功，开始接收消息")
        await websocket.send_json({
            'type': 'ready',
            'message': '弹幕连接成功'
        })
        
        # 6. 双向消息处理
        async def receive_from_client():
            """接收客户端消息"""
            try:
                while is_running and spider.is_running:
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=30.0
                    )
                    # 处理心跳
                    if data == 'ping':
                        await websocket.send_json({'type': 'pong'})
                        logger.debug("已响应心跳")
                    elif data == 'stop':
                        logger.info("WebSocket: 收到停止命令")
                        break
            except asyncio.TimeoutError:
                # 超时也继续，保持连接
                logger.debug("等待客户端消息超时，继续监听...")
                pass
            except WebSocketDisconnect:
                logger.info("WebSocket: 客户端断开连接")
            except Exception as e:
                logger.error(f"WebSocket: 接收消息错误: {e}")
        
        async def send_to_client():
            """发送消息到客户端"""
            try:
                msg_count = 0
                while is_running and (spider.is_running or message_queue):
                    # 发送队列中的消息
                    while message_queue:
                        msg = message_queue.pop(0)
                        await websocket.send_json(msg)
                        msg_count += 1
                        logger.info(f"✓ 已发送第 {msg_count} 条消息到前端: type={msg.get('type')}, nickname={msg.get('nickname')}")
                    if not spider.is_running:
                        break
                    await asyncio.sleep(0.02)  # 20ms 检查一次
            except WebSocketDisconnect:
                logger.info("WebSocket: 客户端断开连接")
            except Exception as e:
                logger.error(f"WebSocket: 发送消息错误: {e}")
        
        # 并行运行收发任务
        receive_task = asyncio.create_task(receive_from_client())
        send_task = asyncio.create_task(send_to_client())
        
        # 等待任一任务完成
        done, pending = await asyncio.wait(
            [receive_task, send_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # 取消未完成的任务
        for task in pending:
            task.cancel()
        
    except WebSocketDisconnect:
        logger.info("WebSocket: 客户端断开连接")
    except Exception as e:
        logger.error(f"WebSocket: 连接错误: {e}")
        try:
            await websocket.send_json({
                'type': 'error',
                'message': str(e)
            })
        except:
            pass
    finally:
        is_running = False
        # 停止弹幕采集
        if spider:
            spider.stop()
        logger.info("WebSocket: 连接结束")
        try:
            await websocket.send_json({'type': 'disconnected'})
        except:
            pass


@router.get("/cache/info")
async def get_cache_info():
    """获取视频流缓存信息"""
    cache_info = live_stream_cache.get_cache_info()
    return ApiResponse(data=cache_info)


@router.delete("/cache")
async def clear_all_cache():
    """清除所有视频流缓存"""
    live_stream_cache.clear()
    return ApiResponse(data={"message": "已清除所有缓存"})
