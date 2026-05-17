"""
直播服务
"""
import asyncio
from typing import Dict, Optional, Callable, Any
from loguru import logger

from app.modules.douyin.common.auth import DouyinAuth
from app.modules.douyin.live.spiders.live import DouyinLiveSpider


class LiveService:
    """直播服务"""
    
    # 存储活跃的直播监听
    _active_monitors: Dict[str, DouyinLiveSpider] = {}
    _message_callbacks: Dict[str, Callable] = {}
    
    def __init__(self, auth: DouyinAuth):
        self.auth = auth
    
    async def start_monitor(self, live_id: str) -> bool:
        """启动直播监听"""
        if live_id in self._active_monitors:
            logger.warning(f"直播间 {live_id} 已在监听中")
            return False
        
        try:
            spider = DouyinLiveSpider(live_id, self.auth)
            room_info = await spider.get_room_info()
            
            # 设置消息回调
            def on_message(msg):
                if live_id in self._message_callbacks:
                    self._message_callbacks[live_id](msg)
            
            spider.set_message_callback(on_message)
            
            # 保存实例
            self._active_monitors[live_id] = spider
            
            # 在后台线程启动 WebSocket
            import threading
            thread = threading.Thread(target=spider.start_ws, args=(room_info,), daemon=True)
            thread.start()
            
            logger.info(f"已启动直播间 {live_id} 监听")
            return True
        
        except Exception as e:
            logger.error(f"启动直播监听失败: {e}")
            return False
    
    async def stop_monitor(self, live_id: str) -> bool:
        """停止直播监听"""
        if live_id not in self._active_monitors:
            return False
        
        try:
            spider = self._active_monitors.pop(live_id)
            spider.stop()
            
            if live_id in self._message_callbacks:
                del self._message_callbacks[live_id]
            
            logger.info(f"已停止直播间 {live_id} 监听")
            return True
        
        except Exception as e:
            logger.error(f"停止直播监听失败: {e}")
            return False
    
    def set_message_callback(self, live_id: str, callback: Callable[[Dict[str, Any]], None]):
        """设置消息回调"""
        self._message_callbacks[live_id] = callback
    
    @classmethod
    def get_active_monitors(cls) -> Dict[str, bool]:
        """获取所有活跃的监听"""
        return {
            live_id: spider.is_running 
            for live_id, spider in cls._active_monitors.items()
        }
    
    @classmethod
    def is_monitoring(cls, live_id: str) -> bool:
        """检查是否正在监听"""
        return live_id in cls._active_monitors and cls._active_monitors[live_id].is_running
