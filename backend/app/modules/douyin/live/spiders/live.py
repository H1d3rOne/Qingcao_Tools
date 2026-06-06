"""
抖音直播爬虫模块
参考: 项目根目录/test3.py

获取视频流流程:
1. 从直播间链接获取 web_rid
2. 从网页中提取 19 位 room_id
3. 通过 API 获取 FLV 和 HLS 视频流链接
4. 返回给前端
"""
import gzip
import re
import socket
import ssl
import threading
import time
import random
from datetime import datetime, timedelta
from urllib.parse import urlencode
from typing import Optional, Callable, Dict, Any

import requests
from requests.exceptions import Timeout, RequestException
import websocket as websocket_client
from websocket import WebSocketApp
from loguru import logger

from app.modules.douyin.common.auth import DouyinAuth
from app.modules.douyin.common.header import HeaderBuilder, HeaderType
from app.modules.douyin.common.params import Params
from app.utils.dy_util import generate_signature
from app.modules.douyin.scripts import Live_pb2
from app.core.config import settings


class LiveStreamCache:
    """直播视频流缓存管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._cache: Dict[str, Dict] = {}
                    cls._instance._expire_time = 300  # 缓存过期时间：5分钟
        return cls._instance
    
    def get(self, room_id: str) -> Optional[Dict]:
        """获取缓存的视频流信息"""
        if room_id in self._cache:
            cached = self._cache[room_id]
            if datetime.now() < cached['expire_at']:
                logger.info(f"使用缓存的视频流: room_id={room_id}")
                return cached['data']
            else:
                logger.info(f"缓存已过期: room_id={room_id}")
                del self._cache[room_id]
        return None
    
    def set(self, room_id: str, data: Dict):
        """设置缓存"""
        self._cache[room_id] = {
            'data': data,
            'expire_at': datetime.now() + timedelta(seconds=self._expire_time),
            'created_at': datetime.now()
        }
        logger.info(f"缓存视频流: room_id={room_id}, 过期时间={self._expire_time}秒")
    
    def clear(self, room_id: str = None):
        """清除缓存"""
        if room_id:
            if room_id in self._cache:
                del self._cache[room_id]
                logger.info(f"清除缓存: room_id={room_id}")
        else:
            self._cache.clear()
            logger.info("清除所有缓存")
    
    def get_cache_info(self) -> Dict:
        """获取缓存信息"""
        return {
            'count': len(self._cache),
            'rooms': list(self._cache.keys()),
            'expire_time': self._expire_time
        }


# 全局缓存实例
live_stream_cache = LiveStreamCache()


class DouyinLiveSpider:
    """抖音直播爬虫
    
    参考 test3.py 的实现:
    1. get_room_id(url) - 从直播间网页中提取 19 位 room_id
    2. get_real_url(room_id) - 通过 webcast.amemv.com API 获取视频流链接
    
    使用方式:
        spider = DouyinLiveSpider('https://live.douyin.com/802236344116', auth)
        room_info = await spider.get_room_info()
    """
    
    # 默认请求头
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    
    def __init__(self, live_url: str, auth: DouyinAuth, timeout: int = 30):
        """初始化直播爬虫
        
        Args:
            live_url: 抖音直播链接，如 https://live.douyin.com/802236344116
            auth: 抖音认证对象
            timeout: 超时时间（秒）
        """
        self.auth = auth
        self.live_url = live_url
        self.timeout = timeout
        self.ws: Optional[WebSocketApp] = None
        self.is_running = False
        self.startup_stage = "初始化"
        self.startup_error: Optional[str] = None
        self._opened_once = False
        self._defer_startup_errors = False
        self._last_startup_error: Optional[str] = None
        self.message_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._room_info: Optional[Dict] = None
    
    def set_message_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """设置消息回调函数"""
        self.message_callback = callback

    def _set_startup_stage(self, stage: str):
        """记录弹幕启动阶段，方便前端展示真实卡点而不是笼统超时。"""
        self.startup_stage = stage
        logger.info(f"直播弹幕启动阶段: {stage}")
    
    def _get_web_rid(self, input_str: str) -> str:
        """从输入中提取 web_rid
        
        支持的输入格式:
        - 纯数字: 802236344116
        - 直播链接: https://live.douyin.com/802236344116
        - 带参数链接: https://live.douyin.com/802236344116?xxx=yyy
        """
        input_str = input_str.strip()
        
        # 如果是纯数字，直接返回
        if re.match(r'^\d+$', input_str):
            return input_str
        
        # 从 URL 中提取
        match = re.search(r'live\.douyin\.com/(\d+)', input_str)
        if match:
            return match.group(1)
        
        # 尝试提取任意长数字
        match = re.search(r'(\d{10,})', input_str)
        if match:
            return match.group(1)
        
        return input_str
    
    def _get_room_id(self, url: str) -> str:
        """从网页中提取 19 位 room_id
        
        参考 test3.py: 使用正则 `"roomId":"(\d+)"` 从网页响应中提取
        """
        cookies = {}
        
        # 优先使用配置中的直播 cookies，其次使用视频 cookies
        cookie_str = settings.DY_LIVE_COOKIES or settings.DY_COOKIES
        if cookie_str:
            for item in cookie_str.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookies[key.strip()] = value.strip()
            logger.info(f"使用配置文件中的 {'直播' if settings.DY_LIVE_COOKIES else '视频'} cookies 获取 room_id")
        
        try:
            response = requests.get(url, headers=self.DEFAULT_HEADERS, cookies=cookies, timeout=10)
            html = response.text
            
            # 检查验证码
            if '验证码' in html or 'captcha' in html.lower():
                logger.warning("遇到验证码页面，可能需要更新 cookies")
            
            # 参考 test3.py 的核心正则
            patterns = [
                r'&quot;roomId&quot;:&quot;(\d+)&quot;',  # HTML 编码格式 (test3.py 使用)
                r'roomId\\":\\"(\d+)',                   # 转义 JSON 格式
                r'"roomId":"(\d+)"',                     # 标准 JSON 格式
                r'"roomId"\s*:\s*"(\d+)"',               # 宽松 JSON 格式
                r'"roomId"\s*:\s*(\d+)',                 # 无引号格式
            ]
            
            for pattern in patterns:
                result = re.search(pattern, html)
                if result:
                    room_id = result.group(1)
                    logger.info(f"从网页提取到 room_id: {room_id}")
                    return room_id
            
            logger.warning("未从网页中匹配到 room_id")
            
        except Timeout:
            logger.error(f"获取网页超时: {url}")
        except RequestException as e:
            logger.error(f"网络请求失败: {e}")
        except Exception as e:
            logger.error(f"从网页获取 room_id 失败: {e}")
        
        return ''
    
    def _get_stream_url(self, room_id: str) -> Dict:
        """通过 API 获取直播间视频流地址
        
        参考 test3.py: 使用 webcast.amemv.com API 获取 FLV 和 HLS 流地址
        """
        headers = {
            'authority': 'webcast.amemv.com',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
        }

        cookie_str = (getattr(self.auth, 'cookie_str', '') or settings.DY_LIVE_COOKIES or settings.DY_COOKIES).strip()
        if cookie_str:
            headers['cookie'] = cookie_str
        
        params = {
            'type_id': '0',
            'live_id': '1',
            'room_id': room_id,
            'app_id': '1128',
        }
        
        try:
            response = requests.get(
                'https://webcast.amemv.com/webcast/room/reflow/info/',
                headers=headers,
                params=params,
                timeout=10
            )
            data = response.json()
            logger.info(f"视频流 API 响应 status_code: {data.get('status_code')}")
            
            if data.get('status_code') != 0:
                logger.warning(f"API 返回错误: status_code={data.get('status_code')}")
                return {}
            
            room = data.get('data', {}).get('room')
            if not room:
                logger.warning("API 返回数据中没有 room")
                return {}
            
            stream_url = room.get('stream_url', {})
            
            # 参考 test3.py: 直接获取 rtmp_pull_url 和 hls_pull_url
            rtmp_url = stream_url.get('rtmp_pull_url', '')
            hls_url = stream_url.get('hls_pull_url', '')
            
            # flv_pull_url 可能是字典（多清晰度）或字符串
            flv_pull_url = stream_url.get('flv_pull_url', {})
            if isinstance(flv_pull_url, dict):
                # 优先选择最高清晰度 FULL_HD1，其次 HD1，最后 SD1
                flv_url = flv_pull_url.get('FULL_HD1') or flv_pull_url.get('HD1') or flv_pull_url.get('SD1') or ''
            else:
                flv_url = flv_pull_url if flv_pull_url else ''
            
            # 获取主播信息
            owner = room.get('owner', {})
            owner_info = {
                'nickname': owner.get('nickname', ''),
                'avatar': owner.get('avatar_thumb', {}).get('url_list', [''])[0] if owner.get('avatar_thumb', {}).get('url_list') else '',
                'sec_uid': owner.get('sec_uid', ''),
                'uid': str(owner.get('id', '')),
                'follow_count': owner.get('follow_count', 0),
                'follower_count': owner.get('follower_count', 0),
                'total_likes': owner.get('total_likes', 0),
                'signature': owner.get('signature', ''),
                'verified': owner.get('verified', False),
                'verify_type': owner.get('verify_type', -1),
                'city': owner.get('city', ''),
                'province': owner.get('province', ''),
                'country': owner.get('country', ''),
                'location': owner.get('location', ''),
                'age': owner.get('age', 0),
                'gender': owner.get('gender', 0),
            }
            
            result = {
                'room_id': str(room.get('room_id', '')),
                'owner': owner_info,
                'stream_url': {
                    'rtmp': rtmp_url,
                    'hls': hls_url,
                    'flv': flv_url,
                },
                'title': room.get('title', ''),
                'user_count': room.get('user_count', 0),
                'status': room.get('status', 0),  # 2=直播中, 4=未开播
            }
            
            logger.info(f"获取视频流成功: flv={bool(flv_url)}, hls={bool(hls_url)}, rtmp={bool(rtmp_url)}")
            return result
            
        except Timeout:
            logger.error(f"获取视频流 API 超时: room_id={room_id}")
        except RequestException as e:
            logger.error(f"获取视频流网络请求失败: {e}")
        except Exception as e:
            logger.error(f"获取视频流失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return {}
    
    async def get_room_info(self) -> Dict:
        """获取直播间信息
        
        流程（参考 test3.py）:
        1. 从直播间链接获取 web_rid
        2. 从网页中提取 19 位 room_id
        3. 通过 API 获取 FLV 和 HLS 视频流链接
        
        返回:
            Dict: 包含 room_id, web_rid, stream_url, title, owner 等信息
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            room_info = await loop.run_in_executor(executor, self._get_room_info_sync)
        return room_info
    
    def _get_room_info_sync(self) -> Dict:
        """同步获取直播间信息
        
        两种方案:
        1. 优先使用 Web API（使用已配置 Cookie）
        2. 如果失败，从网页解析 room_id（使用已配置 Cookie）
        """
        # Step 1: 提取 web_rid
        web_rid = self._get_web_rid(self.live_url)
        logger.info(f"提取的 web_rid: {web_rid}")
        
        # 方案1: 使用 Web API 获取（推荐，更稳定）
        room_info = self._get_room_info_via_api(web_rid)
        if room_info and room_info.get('room_id'):
            return room_info
        
        # 方案2: 从网页解析 room_id
        logger.warning("Web API 获取失败，尝试从网页解析 room_id")
        live_url = f"https://live.douyin.com/{web_rid}"
        room_id = self._get_room_id(live_url)
        
        if room_id:
            stream_info = self._get_stream_url(room_id)
            if stream_info:
                result = {
                    'room_id': room_id,
                    'web_rid': web_rid,
                    'owner': stream_info.get('owner', {}),
                    'stream_url': stream_info.get('stream_url', {}),
                    'title': stream_info.get('title', ''),
                    'user_count': stream_info.get('user_count', 0),
                    'status': stream_info.get('status', 0),
                }
                return result
        
        return self._build_empty_result(web_rid)
    
    def _get_room_info_via_api(self, web_rid: str) -> Dict:
        """通过 Web API 直接获取直播间信息（推荐方式）
        
        使用 live.douyin.com/webcast/room/web/enter/ API
        使用已配置 Cookie，不再使用硬编码 ttwid 兜底
        """
        api_url = "https://live.douyin.com/webcast/room/web/enter/"
        
        params = {
            'aid': '6383',
            'app_name': 'douyin_web',
            'live_id': '1',
            'device_platform': 'web',
            'language': 'zh-CN',
            'enter_from': 'web_live',
            'cookie_enabled': 'true',
            'screen_width': '1920',
            'screen_height': '1080',
            'browser_language': 'zh-CN',
            'browser_platform': 'MacIntel',
            'browser_name': 'Chrome',
            'browser_version': '145.0.0.0',
            'web_rid': web_rid,
            'Room-Enter-User-Login-Ab': '0',
            'is_need_double_stream': 'false',
            'support_wrds': '1',
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'Referer': f'https://live.douyin.com/{web_rid}',
            'Accept': 'application/json',
        }
        
        cookies = {}
        if hasattr(self.auth, 'cookie') and self.auth.cookie:
            cookies.update(self.auth.cookie)
        
        if not cookies:
            logger.warning("未配置抖音 Cookie，无法请求直播 Web API")
            return {}

        if 'ttwid' not in cookies:
            logger.warning("Cookie 中缺少 ttwid，继续使用已有 Cookie 请求直播 Web API")
        
        try:
            response = requests.get(api_url, params=params, headers=headers, cookies=cookies, timeout=10)
            data = response.json()
            logger.info(f"Web API 响应 status_code: {data.get('status_code')}")
            
            if data.get('status_code') != 0:
                logger.warning(f"Web API 返回错误: status_code={data.get('status_code')}")
                return {}
            
            room_data = data.get('data', {}).get('data', [])
            if not room_data:
                logger.warning("Web API 返回数据中没有房间信息")
                return {}
            
            room = room_data[0]
            user = data.get('data', {}).get('user', {})
            
            # 解析视频流
            stream_url = room.get('stream_url', {})
            
            flv_pull_url = stream_url.get('flv_pull_url', {})
            if isinstance(flv_pull_url, dict):
                flv_url = flv_pull_url.get('FULL_HD1') or flv_pull_url.get('HD1') or flv_pull_url.get('SD1') or ''
            else:
                flv_url = flv_pull_url if flv_pull_url else ''
            
            hls_pull_url_map = stream_url.get('hls_pull_url_map', {})
            if isinstance(hls_pull_url_map, dict):
                hls_url = hls_pull_url_map.get('FULL_HD1') or hls_pull_url_map.get('HD1') or hls_pull_url_map.get('SD1') or ''
            else:
                hls_url = stream_url.get('hls_pull_url', '')
            
            # 主播信息
            owner_info = {
                'nickname': user.get('nickname', ''),
                'avatar': user.get('avatar_thumb', {}).get('url_list', [''])[0] if user.get('avatar_thumb', {}).get('url_list') else '',
                'sec_uid': user.get('sec_uid', ''),
                'uid': str(user.get('id_str', '')),
                'follow_count': user.get('follow_info', {}).get('follow_status', 0),
                'follower_count': 0,
                'total_likes': 0,
                'signature': '',
                'verified': False,
                'verify_type': -1,
                'city': '',
                'province': '',
                'country': '',
                'location': '',
                'age': 0,
                'gender': 0,
            }
            
            # 观看人数
            user_count_str = room.get('user_count_str', '0') or '0'
            try:
                user_count = int(user_count_str.replace('+', '').replace('w', '0000').replace('万', '0000'))
            except ValueError:
                user_count = 0
            
            result = {
                'room_id': str(room.get('id_str', '')),
                'web_rid': web_rid,
                'owner': owner_info,
                'stream_url': {
                    'rtmp': '',
                    'hls': hls_url,
                    'flv': flv_url,
                },
                'title': room.get('title', ''),
                'user_count': user_count,
                'status': room.get('status', 0),
            }
            
            logger.info(f"Web API 获取成功: room_id={result['room_id']}, flv={bool(flv_url)}, hls={bool(hls_url)}")
            return result
            
        except Exception as e:
            logger.error(f"Web API 请求失败: {e}")
            return {}
    
    def _build_empty_result(self, web_rid: str, room_id: str = '') -> Dict:
        """构建空的返回结果"""
        return {
            'room_id': room_id or web_rid,
            'web_rid': web_rid,
            'owner': {
                'nickname': None,
                'avatar': None,
                'sec_uid': None,
                'uid': None,
                'follow_count': 0,
                'follower_count': 0,
                'total_likes': 0,
                'signature': None,
                'verified': False,
                'verify_type': -1,
                'city': None,
                'province': None,
                'country': None,
                'location': None,
                'age': 0,
                'gender': 0,
            },
            'stream_url': {
                'rtmp': None,
                'hls': None,
                'flv': None,
            },
            'title': '',
            'user_count': 0,
            'status': 0,
        }

    def _cookie_dict(self) -> Dict[str, str]:
        """获取当前直播请求使用的 Cookie 字典。"""
        cookies = {}
        if hasattr(self.auth, 'cookie') and self.auth.cookie:
            cookies.update(self.auth.cookie)
        return cookies

    def _cookie_header(self) -> str:
        """获取完整 Cookie 字符串，WebSocket 握手必须尽量保持真实浏览器 Cookie。"""
        return (getattr(self.auth, 'cookie_str', '') or '').strip()

    def _get_live_page_context(self, web_rid: str) -> Dict[str, str]:
        """从直播间 HTML 中补齐 room_id/user_unique_id/ttwid。

        抖音直播弹幕的 user_unique_id 与 ttwid 都属于浏览器设备态。
        只用随机 user_id 或只带 ttwid 建连时，Windows 上更容易被卡住或被风控拒绝。
        """
        context: Dict[str, str] = {}
        if not web_rid:
            return context

        url = f"https://live.douyin.com/{web_rid}"
        try:
            headers = HeaderBuilder.build(HeaderType.DOC, self.auth).get()
            response = requests.get(
                url,
                headers=headers,
                cookies=self._cookie_dict(),
                timeout=10,
            )
            html = response.text or ""
            ttwid = response.cookies.get_dict().get('ttwid') or self._cookie_dict().get('ttwid', '')
            if ttwid:
                context['ttwid'] = ttwid

            patterns = {
                'room_id': [
                    r'\\"roomId\\":\\"(\d+)\\"',
                    r'"roomId":"(\d+)"',
                    r'&quot;roomId&quot;:&quot;(\d+)&quot;',
                ],
                'user_unique_id': [
                    r'\\"user_unique_id\\":\\"(\d+)\\"',
                    r'"user_unique_id":"(\d+)"',
                    r'&quot;user_unique_id&quot;:&quot;(\d+)&quot;',
                ],
            }
            for key, key_patterns in patterns.items():
                for pattern in key_patterns:
                    match = re.search(pattern, html)
                    if match:
                        context[key] = match.group(1)
                        break

            logger.info(
                "直播页面上下文: "
                f"room_id={bool(context.get('room_id'))}, "
                f"user_unique_id={bool(context.get('user_unique_id'))}, "
                f"ttwid={bool(context.get('ttwid'))}"
            )
        except Exception as e:
            logger.warning(f"获取直播页面上下文失败，继续使用已有信息: {e}")
        return context

    def _resolve_user_unique_id(self, room_info: Dict, page_context: Dict[str, str]) -> str:
        """解析弹幕连接使用的 user_unique_id，缺失时才随机兜底。"""
        candidates = [
            page_context.get('user_unique_id'),
            room_info.get('user_unique_id'),
        ]
        for value in candidates:
            value = str(value or '').strip()
            if re.fullmatch(r'\d{10,}', value):
                return value

        fallback = ''.join([str(random.randint(0, 9)) for _ in range(19)])
        logger.warning("未获取到真实 user_unique_id，使用随机值兜底")
        return fallback

    def _fetch_initial_live_response(self, room_id: str, user_unique_id: str, web_rid: str) -> Optional[Any]:
        """先请求 /webcast/im/fetch/ 获取 cursor/internal_ext。

        新版直播 WebSocket 建连时带上 cursor/internal_ext 更接近真实页面流程；
        如果该请求失败，仍继续尝试 WebSocket，避免影响直播播放。
        """
        try:
            self._set_startup_stage("获取弹幕初始游标")
            referer = f"https://live.douyin.com/{web_rid or room_id}"
            headers = HeaderBuilder.build(HeaderType.FORM, self.auth).get()
            headers.update({
                'origin': 'https://live.douyin.com',
                'referer': referer,
                'accept': '*/*',
            })

            params = Params()
            (params
             .add_param('resp_content_type', 'protobuf')
             .add_param('did_rule', '3')
             .add_param('device_id', '')
             .add_param('app_name', 'douyin_web')
             .add_param('endpoint', 'live_pc')
             .add_param('support_wrds', '1')
             .add_param('user_unique_id', str(user_unique_id))
             .add_param('identity', 'audience')
             .add_param('need_persist_msg_count', '15')
             .add_param('insert_task_id', '')
             .add_param('live_reason', '')
             .add_param('room_id', room_id)
             .add_param('version_code', '180800')
             .add_param('last_rtt', '0')
             .add_param('live_id', '1')
             .add_param('aid', '6383')
             .add_param('fetch_rule', '1')
             .add_param('cursor', '')
             .add_param('internal_ext', '')
             .add_param('device_platform', 'web')
             .add_param('cookie_enabled', 'true')
             .add_param('screen_width', '1707')
             .add_param('screen_height', '960')
             .add_param('browser_language', 'zh-CN')
             .add_param('browser_platform', 'Win32')
             .add_param('browser_name', 'Mozilla')
             .add_param('browser_version', HeaderBuilder.ua)
             .add_param('browser_online', 'true')
             .add_param('tz_name', 'Asia/Shanghai')
            )

            response = requests.get(
                'https://live.douyin.com/webcast/im/fetch/',
                params=params.get(),
                headers=headers,
                cookies=self._cookie_dict(),
                timeout=10,
            )
            if response.status_code != 200:
                logger.warning(f"弹幕初始游标请求失败: HTTP {response.status_code}")
                return None

            frame = Live_pb2.LiveResponse()
            frame.ParseFromString(response.content)
            logger.info(
                f"弹幕初始游标获取成功: cursor={bool(frame.cursor)}, "
                f"internal_ext={bool(frame.internalExt)}, messages={len(frame.messagesList)}"
            )
            return frame
        except Exception as e:
            logger.warning(f"获取弹幕初始游标失败，继续直接连接 WebSocket: {e}")
            return None

    def _resolve_ws_addresses(self, host: str, port: int) -> list:
        """解析弹幕域名地址，优先 IPv4。

        websocket-client 在 Windows 上会顺序尝试 getaddrinfo 返回的地址；
        如果 IPv6 地址排在前面但当前网络 IPv6 不通，容易卡到前端超时。
        这里自己解析并控制尝试顺序/总耗时。
        """
        addrinfo_list = []
        errors = []

        for family in (socket.AF_INET, socket.AF_UNSPEC):
            try:
                infos = socket.getaddrinfo(
                    host,
                    port,
                    family,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                )
                addrinfo_list.extend(infos)
            except socket.gaierror as e:
                errors.append(str(e))

        # 去重，并确保 IPv4 排在 IPv6 前面。
        unique = []
        seen = set()
        for info in addrinfo_list:
            family, socktype, proto, _canonname, address = info
            key = (family, address[0], address[1])
            if key in seen:
                continue
            seen.add(key)
            unique.append((family, socktype, proto, address))

        unique.sort(key=lambda item: 0 if item[0] == socket.AF_INET else 1)
        if not unique:
            raise OSError(f"解析弹幕服务器失败: {host}; {'; '.join(errors) or '无可用地址'}")
        return unique

    def _open_direct_tls_socket(self, host: str, port: int, timeout: int):
        """直连并建立 TLS socket，绕开 websocket-client 的环境代理探测。

        websocket-client 的 http_no_proxy 在未显式传 http_proxy_host 时不会阻止它读取
        HTTPS_PROXY/HTTP_PROXY 环境变量。Windows 上视频号监听/mitm 或系统环境里残留
        代理时，就会表现为抖音弹幕 WebSocket 建连超时。预先创建直连 TLS socket 后再
        交给 WebSocketApp，可同时规避残留代理和 IPv6 顺序连接卡住的问题。
        """
        self._set_startup_stage(f"解析弹幕服务器 {host}")
        addrinfo_list = self._resolve_ws_addresses(host, port)
        deadline = time.monotonic() + max(3, timeout)
        last_error = None
        context = ssl.create_default_context()

        for index, (family, socktype, proto, address) in enumerate(addrinfo_list, start=1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            # 单个 IP 不要吃完整个 host 的超时预算，避免多 IP 域名在 Windows 上卡太久。
            per_address_timeout = max(1.0, min(5.0, remaining))
            raw_sock = None
            try:
                self._set_startup_stage(
                    f"直连弹幕服务器 {host} [{index}/{len(addrinfo_list)}] {address[0]}"
                )
                raw_sock = socket.socket(family, socktype, proto)
                raw_sock.settimeout(per_address_timeout)
                raw_sock.connect(address)

                self._set_startup_stage(f"建立弹幕 TLS 连接 {host}")
                tls_sock = context.wrap_socket(raw_sock, server_hostname=host)
                tls_sock.settimeout(timeout)
                logger.info(f"弹幕服务器直连成功: host={host}, remote={address[0]}:{address[1]}")
                return tls_sock
            except Exception as e:
                last_error = e
                logger.warning(f"弹幕服务器直连失败: host={host}, address={address}, error={e}")
                try:
                    if raw_sock:
                        raw_sock.close()
                except Exception:
                    pass

        raise TimeoutError(f"{host} 直连失败或超时: {last_error or '无可用地址'}")
    
    # ==================== WebSocket 弹幕相关 ====================
    
    def _ping(self, ws):
        """心跳线程"""
        while self.is_running:
            frame = Live_pb2.PushFrame()
            frame.payloadType = "hb"
            try:
                ws.send(frame.SerializeToString(), opcode=0x02)
                time.sleep(5)
            except Exception as e:
                logger.error(f"直播心跳失败: {e}")
                break
    
    def _on_open(self, ws):
        """WebSocket 打开回调"""
        logger.info(f"✓ 直播间 {self.live_url} WebSocket 连接成功!")
        logger.info(f"✓ 设置 is_running = True")
        self._set_startup_stage("WebSocket 已连接")
        self.startup_error = None
        self._opened_once = True
        self.is_running = True
        # setdefaulttimeout 只用于限制建连阶段，连接成功后恢复为阻塞读取，
        # 避免低弹幕直播间长时间无消息时被 socket timeout 误关闭。
        try:
            if getattr(ws, "sock", None):
                ws.sock.settimeout(None)
        except Exception as e:
            logger.debug(f"恢复直播 WebSocket 读取超时失败: {e}")
        logger.info(f"✓ is_running 状态: {self.is_running}")
        
        # 启动心跳线程
        threading.Thread(target=self._ping, args=(ws,), daemon=True).start()
        logger.info("✓ 心跳线程已启动")
        
        # 测试消息
        if self.message_callback:
            logger.info("✓ message_callback 已设置")
        else:
            logger.error("❌ message_callback 未设置!")
    
    def _on_message(self, ws, message):
        """WebSocket 消息回调"""
        try:
            logger.info(f"收到 WebSocket 消息, 长度: {len(message)}")
            
            frame = Live_pb2.PushFrame()
            frame.ParseFromString(message)
            logger.info(f"PushFrame 解析成功, payloadType: {frame.payloadType}")
            
            origin_bytes = gzip.decompress(frame.payload)
            logger.info(f"解压后数据长度: {len(origin_bytes)}")
            
            response = Live_pb2.LiveResponse()
            response.ParseFromString(origin_bytes)
            logger.info(f"LiveResponse 解析成功, needAck: {response.needAck}")
            
            # 发送 ACK
            if response.needAck:
                s = Live_pb2.PushFrame()
                s.payloadType = "ack"
                s.payload = response.internalExt.encode('utf-8')
                s.logId = frame.logId
                ws.send(s.SerializeToString(), opcode=0x02)
                logger.info("已发送 ACK")
            
            # 解析消息
            msg_count = len(response.messagesList)
            logger.info(f"消息列表长度: {msg_count}")
            
            if msg_count > 0:
                logger.info(f"准备解析 {msg_count} 条消息")
            
            for idx, item in enumerate(response.messagesList):
                logger.info(f"消息 {idx+1}/{msg_count}, method: {item.method}, payload长度: {len(item.payload)}")
                
                msg_data = self._parse_message(item)
                if msg_data:
                    logger.info(f"✓ 消息解析成功: type={msg_data.get('type')}, nickname={msg_data.get('nickname')}, display_type={msg_data.get('display_type')}")
                    
                    if self.message_callback:
                        logger.info(f"调用 message_callback...")
                        self.message_callback(msg_data)
                        logger.info(f"✓ 消息已通过 callback 发送")
                    else:
                        logger.error("❌ message_callback 未设置!")
                else:
                    logger.warning(f"⚠ 消息解析返回 None, method: {item.method}")
        
        except Exception as e:
            logger.error(f"❌ 解析直播消息失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _get_badge_image_list(self, user) -> list:
        """获取用户的徽章图片列表
        
        参考 test4.py: message.user.badge_image_list[0]
        """
        badge_list = []
        try:
            for badge in user.badge_image_list:
                badge_info = {
                    'name': badge.content.name if badge.content else '',
                    'url': '',  # Image 结构中没有直接的 url 字段
                    'level': badge.content.level if badge.content else 0,
                    'alternative_text': badge.content.alternative_text if badge.content else '',
                }
                badge_list.append(badge_info)
        except Exception as e:
            logger.debug(f"获取徽章图片失败: {e}")
        return badge_list
    
    def _parse_message(self, item) -> Optional[Dict[str, Any]]:
        """解析直播消息
        
        消息类型和前端显示方式:
        
        聊天消息 (chat):
            badge_image_list, nickname, content
            显示在消息窗口，从上往下滚动
            
        进入直播间消息 (member):
            badge_image_list, nickname来了
            更新在线人数 (member_count)
            显示在输入框上方，出现后消失
            
        点赞消息 (like):
            badge_image_list, nickname给主播点赞了
            显示在输入框上方，出现后消失
            
        关注消息 (follow):
            badge_image_list, nickname给主播点关注了
            显示在输入框上方，出现后消失
            
        房间信息消息 (room_stats):
            total: 更新直播间在线人数
            
        礼物消息 (gift):
            badge_image_list, nickname送出gift.name x comboCount
            或 user.nickname 给 toUser.nickname送出gift.name x comboCount
            显示在消息窗口，从上往下滚动
        """
        try:
            if item.method == 'WebcastGiftMessage':
                # 礼物消息
                msg = Live_pb2.GiftMessage()
                msg.ParseFromString(item.payload)
                
                user = msg.user
                to_user = msg.toUser
                gift = msg.gift
                
                return {
                    "type": "gift",
                    "display_type": "message",  # 显示在消息窗口
                    "badge_image_list": self._get_badge_image_list(user),
                    "nickname": user.nickname,
                    "gift_name": gift.name if gift else "",
                    "combo_count": msg.comboCount,
                    "to_user_nickname": to_user.nickname if to_user else "",
                }
            
            elif item.method == "WebcastChatMessage":
                # 聊天消息
                msg = Live_pb2.ChatMessage()
                msg.ParseFromString(item.payload)
                
                user = msg.user
                
                return {
                    "type": "chat",
                    "display_type": "message",  # 显示在消息窗口
                    "badge_image_list": self._get_badge_image_list(user),
                    "nickname": user.nickname,
                    "content": msg.content,
                }
            
            elif item.method == "WebcastMemberMessage":
                # 进入直播间消息
                msg = Live_pb2.MemberMessage()
                msg.ParseFromString(item.payload)
                
                user = msg.user
                
                return {
                    "type": "member",
                    "display_type": "notification",  # 显示在输入框上方
                    "badge_image_list": self._get_badge_image_list(user),
                    "nickname": user.nickname,
                    "member_count": msg.memberCount,  # 用于更新在线人数
                }
            
            elif item.method == "WebcastLikeMessage":
                # 点赞消息
                msg = Live_pb2.LikeMessage()
                msg.ParseFromString(item.payload)
                
                user = msg.user
                
                return {
                    "type": "like",
                    "display_type": "notification",  # 显示在输入框上方
                    "badge_image_list": self._get_badge_image_list(user),
                    "nickname": user.nickname,
                }
            
            elif item.method == "WebcastSocialMessage":
                # 关注消息
                msg = Live_pb2.SocialMessage()
                msg.ParseFromString(item.payload)
                
                if msg.action == 1:  # 关注
                    user = msg.user
                    
                    return {
                        "type": "follow",
                        "display_type": "notification",  # 显示在输入框上方
                        "badge_image_list": self._get_badge_image_list(user),
                        "nickname": user.nickname,
                    }
            
            elif item.method == "WebcastRoomStatsMessage":
                # 房间信息消息
                msg = Live_pb2.RoomStatsMessage()
                msg.ParseFromString(item.payload)
                
                return {
                    "type": "room_stats",
                    "display_type": "stats",  # 用于更新统计
                    "total": msg.total,  # 在线人数
                }
        
        except Exception as e:
            logger.error(f"解析消息失败: {e}")
        
        return None
    
    def _on_error(self, ws, error):
        """WebSocket 错误回调"""
        logger.error(f"直播 WebSocket 错误: {error}")
        self.is_running = False
        message = f"直播弹幕连接失败: {error}"
        if self._defer_startup_errors and not self._opened_once:
            self._last_startup_error = message
            return
        self._emit_error(message)

    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket 关闭回调"""
        logger.warning(f"直播间 {self.live_url} 连接关闭: {close_status_code}, {close_msg}")
        if not self.is_running and not self.startup_error:
            message = f"直播弹幕连接关闭: {close_status_code or ''} {close_msg or ''}".strip()
            if self._defer_startup_errors and not self._opened_once:
                self._last_startup_error = self._last_startup_error or message
            else:
                self.startup_error = message
        self.is_running = False

    def _emit_error(self, message: str):
        """向前端推送弹幕错误，避免启动失败时只显示超时。"""
        self.startup_error = message
        logger.error(message)
        if self.message_callback:
            self.message_callback({'type': 'error', 'message': message})
    
    def start_ws(self, room_info: Dict = None):
        """启动 WebSocket 连接"""
        logger.info(f"start_ws 被调用, room_info: {room_info is not None}")
        self.startup_error = None
        self._last_startup_error = None
        self._opened_once = False
        self._set_startup_stage("准备启动")
        
        if room_info:
            self._room_info = room_info
        
        if not self._room_info:
            logger.error("未获取直播间信息")
            raise ValueError("未获取直播间信息，请先调用 get_room_info()")
        
        web_rid = self._room_info.get('web_rid') or self._get_web_rid(self.live_url)
        page_context = self._get_live_page_context(web_rid)

        room_id = self._room_info.get('room_id') or page_context.get('room_id') or ''
        logger.info(f"room_id: {room_id}")
        
        if not room_id:
            self._emit_error("无法获取 room_id，无法建立弹幕连接")
            return
        
        user_id = self._resolve_user_unique_id(self._room_info, page_context)
        
        # 获取 ttwid，并在握手中携带完整 Cookie，而不是只带 ttwid。
        cookies = self._cookie_dict()
        ttwid = cookies.get('ttwid') or page_context.get('ttwid', '')
        if not ttwid:
            self._emit_error("Cookie 中缺少 ttwid，无法建立弹幕连接")
            return
        cookie_header = self._cookie_header()
        if not cookie_header:
            cookie_header = f"ttwid={ttwid};"
        elif 'ttwid=' not in cookie_header:
            cookie_header = f"{cookie_header}; ttwid={ttwid}"

        try:
            self._set_startup_stage("生成弹幕签名")
            signature = generate_signature(room_id, user_id)
        except Exception as e:
            message = str(e) or "抖音直播弹幕签名生成失败"
            self._emit_error(message)
            return

        initial_response = self._fetch_initial_live_response(room_id, user_id, web_rid)
        cursor = getattr(initial_response, 'cursor', '') if initial_response else ''
        internal_ext = getattr(initial_response, 'internalExt', '') if initial_response else ''
        
        # 构建参数
        params = Params()
        (params
         .add_param('app_name', 'douyin_web')
         .add_param('version_code', '180800')
         .add_param('webcast_sdk_version', '1.0.14-beta.0')
         .add_param('update_version_code', '1.0.14-beta.0')
         .add_param('compress', 'gzip')
         .add_param('device_platform', 'web')
         .add_param('cookie_enabled', 'true')
         .add_param('screen_width', '1707')
         .add_param('screen_height', '960')
         .add_param('browser_language', 'zh-CN')
         .add_param('browser_platform', 'Win32')
         .add_param('browser_name', 'Mozilla')
         .add_param('browser_version', HeaderBuilder.ua.split('Mozilla/')[-1] if 'Mozilla/' in HeaderBuilder.ua else '125.0.0.0')
         .add_param('browser_online', 'true')
         .add_param('tz_name', 'Etc/GMT-8')
         .add_param('cursor', str(cursor or ''))
         .add_param('internal_ext', internal_ext or '')
         .add_param('host', 'https://live.douyin.com')
         .add_param('aid', '6383')
         .add_param('live_id', '1')
         .add_param('did_rule', '3')
         .add_param('endpoint', 'live_pc')
         .add_param('support_wrds', '1')
         .add_param('user_unique_id', str(user_id))
         .add_param('im_path', '/webcast/im/fetch/')
         .add_param('identity', 'audience')
         .add_param('need_persist_msg_count', '15')
         .add_param('insert_task_id', '')
         .add_param('live_reason', '')
         .add_param('room_id', room_id)
         .add_param('heartbeatDuration', '0')
         .add_param('signature', signature)
        )

        ws_hosts = [
            'webcast100-ws-web-hl.douyin.com',
            'webcast5-ws-web-hl.douyin.com',
            'webcast5-ws-web-lf.douyin.com',
        ]
        
        # 单个弹幕域名的建连超时不要太长；Windows 上某个域名/DNS 卡住时
        # 需要尽快切到备用域名，整体等待由 API 层控制。
        connect_timeout = max(8, min(int(self.timeout or 15), 15))
        old_timeout = websocket_client.getdefaulttimeout()
        try:
            # websocket-client 默认 socket timeout 为 None。Windows 上网络/DNS/握手异常时
            # 可能一直卡在建连阶段，前端只能看到“弹幕连接超时”。这里给建连阶段设置
            # 明确超时，并由 _on_error/_emit_error 把真实错误转发给前端。
            websocket_client.setdefaulttimeout(connect_timeout)
            self._defer_startup_errors = True
            for index, host in enumerate(ws_hosts, start=1):
                self.startup_error = None
                self._last_startup_error = None
                prepared_socket = None
                wss_url = f"wss://{host}/webcast/im/push/v2/?{urlencode(params.get())}"
                logger.info(f"WebSocket URL({index}/{len(ws_hosts)}): {wss_url[:100]}...")
                self._set_startup_stage(f"创建 WebSocket（{host}）")

                try:
                    prepared_socket = self._open_direct_tls_socket(host, 443, connect_timeout)
                except Exception as e:
                    self._last_startup_error = f"直播弹幕直连失败: {e}"
                    logger.warning(f"弹幕 WebSocket 主机 {host} 直连失败: {self._last_startup_error}")
                    if index < len(ws_hosts):
                        logger.info("尝试下一个抖音弹幕 WebSocket 主机")
                    continue

                self.ws = WebSocketApp(
                    url=wss_url,
                    header={
                        'Pragma': 'no-cache',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
                        'User-Agent': HeaderBuilder.ua,
                        'Upgrade': 'websocket',
                        'Cache-Control': 'no-cache',
                        'Connection': 'Upgrade',
                    },
                    cookie=cookie_header,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_open=self._on_open,
                    socket=prepared_socket,
                )

                logger.info("WebSocket 实例已创建，准备连接...")
                self._set_startup_stage(f"连接抖音弹幕服务器 {host}（超时 {connect_timeout} 秒）")
                logger.info("调用 run_forever()...")
                try:
                    self.ws.run_forever(
                        origin='https://live.douyin.com',
                        http_proxy_timeout=connect_timeout,
                        # 已传入预连接的直连 TLS socket；这里仍保留 no_proxy，
                        # 兼容未来 websocket-client 修复代理绕过逻辑后的行为。
                        http_no_proxy=["*"],
                    )
                except Exception as e:
                    self._last_startup_error = f"直播弹幕连接失败: {e}"
                    logger.error(self._last_startup_error)
                    import traceback
                    logger.error(traceback.format_exc())
                    if self.ws:
                        self.ws.close()
                logger.info("run_forever() 已返回")

                if self.is_running or self._opened_once:
                    return
                if self._last_startup_error:
                    logger.warning(f"弹幕 WebSocket 主机 {host} 启动失败: {self._last_startup_error}")
                if index < len(ws_hosts):
                    logger.info("尝试下一个抖音弹幕 WebSocket 主机")
        except Exception as e:
            if self._defer_startup_errors and not self._opened_once:
                self._last_startup_error = f"直播弹幕连接失败: {e}"
                logger.error(self._last_startup_error)
            else:
                self._emit_error(f"直播弹幕连接失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            if self.ws:
                self.ws.close()
        finally:
            self._defer_startup_errors = False
            websocket_client.setdefaulttimeout(old_timeout)

        if not self.is_running:
            if self._last_startup_error:
                self._emit_error(self._last_startup_error)
            elif not self.startup_error:
                self._emit_error("直播弹幕连接失败：所有抖音弹幕服务器均未连接成功")
    
    def stop(self):
        """停止 WebSocket 连接"""
        self.is_running = False
        if self.ws:
            self.ws.close()
