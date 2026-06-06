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
import html as html_lib
import re
import threading
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode
from typing import Optional, Callable, Dict, Any

import requests
from requests.exceptions import Timeout, RequestException
from websocket import WebSocketApp
from loguru import logger

from app.modules.douyin.common.auth import DouyinAuth
from app.modules.douyin.common.header import HeaderBuilder, HeaderType
from app.modules.douyin.common.params import Params
from app.utils.dy_util import (
    DOUYIN_LIVE_WEBCAST_SDK_VERSION,
    generate_signature,
    get_douyin_browser_profile,
)
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
        self.message_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._room_info: Optional[Dict] = None
    
    def set_message_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """设置消息回调函数"""
        self.message_callback = callback
    
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

    @staticmethod
    def _first_match(text: str, patterns: list[str]) -> str:
        """按顺序返回第一个正则分组结果。"""
        for pattern in patterns:
            match = re.search(pattern, text, re.S)
            if match:
                return match.group(1)
        return ''

    @staticmethod
    def _html_variants(text: str) -> list[str]:
        """生成几种常见的直播页转义形态，便于用同一组正则解析。"""
        variants: list[str] = []
        for candidate in (
            text or '',
            html_lib.unescape(text or ''),
        ):
            if candidate and candidate not in variants:
                variants.append(candidate)
            unescaped = (
                candidate
                .replace(r'\\"', '"')
                .replace(r'\"', '"')
                .replace(r'\\/', '/')
                .replace(r'\/', '/')
            )
            if unescaped and unescaped not in variants:
                variants.append(unescaped)
        return variants

    @staticmethod
    def _cookie_dict_to_string(cookies: Dict[str, str]) -> str:
        return "; ".join(
            f"{key}={value}"
            for key, value in cookies.items()
            if key and value is not None and value != ''
        )

    def _sync_auth_cookie(self, cookies: Dict[str, str]):
        """把页面响应补发的 ttwid 等 Cookie 合并到当前认证对象。"""
        if not cookies:
            return
        if not hasattr(self.auth, 'cookie') or self.auth.cookie is None:
            self.auth.cookie = {}
        changed = False
        for key, value in cookies.items():
            if value and self.auth.cookie.get(key) != value:
                self.auth.cookie[key] = value
                changed = True
        if changed:
            self.auth.cookie_str = self._cookie_dict_to_string(self.auth.cookie)

    def _build_cookie_header(self, *, ttwid: str = '') -> str:
        """构建给 WebSocket / 直播接口使用的完整 Cookie 字符串。"""
        cookies = {}
        if getattr(self.auth, 'cookie', None):
            cookies.update(self.auth.cookie)
        if ttwid and not cookies.get('ttwid'):
            cookies['ttwid'] = ttwid
        if cookies:
            return self._cookie_dict_to_string(cookies)
        return (getattr(self.auth, 'cookie_str', '') or '').strip()

    def _parse_live_page_html(self, html: str) -> Dict[str, str]:
        """从直播页 HTML 中提取弹幕连接需要的 room_id/user_unique_id。

        Douyin_Spider 的弹幕实现不是使用随机 user_id，而是从直播页脚本中
        提取 `user_unique_id` 后参与 X-Bogus 签名；这里也按这个路径解析。
        """
        result = {
            'room_id': '',
            'user_id': '',
            'user_unique_id': '',
            'anchor_id': '',
            'sec_uid': '',
            'title': '',
            'status': '',
        }

        for candidate in self._html_variants(html):
            if not result['room_id']:
                result['room_id'] = self._first_match(candidate, [
                    r'"roomId"\s*:\s*"(\d+)"',
                    r'"room_id"\s*:\s*"(\d+)"',
                    r'"room"\s*:\s*\{[^{}]*"id_str"\s*:\s*"(\d{10,})"',
                    r'&quot;roomId&quot;:&quot;(\d+)&quot;',
                ])
            if not result['user_unique_id']:
                result['user_unique_id'] = self._first_match(candidate, [
                    r'"user_unique_id"\s*:\s*"(\d+)"',
                    r'&quot;user_unique_id&quot;:&quot;(\d+)&quot;',
                ])
                result['user_id'] = result['user_unique_id']
            if not result['anchor_id']:
                result['anchor_id'] = self._first_match(candidate, [
                    r'"anchor"\s*:\s*\{[^{}]*"id_str"\s*:\s*"(\d+)"',
                    r'"owner"\s*:\s*\{[^{}]*"id_str"\s*:\s*"(\d+)"',
                    r'"owner"\s*:\s*\{[^{}]*"id"\s*:\s*(\d+)',
                ])
            if not result['sec_uid']:
                result['sec_uid'] = self._first_match(candidate, [
                    r'"sec_uid"\s*:\s*"([^"]+)"',
                ])
            if not result['title']:
                result['title'] = self._first_match(candidate, [
                    r'"title"\s*:\s*"([^"]*)"',
                ])
            if not result['status']:
                result['status'] = self._first_match(candidate, [
                    r'"status"\s*:\s*(\d+)',
                    r'"room_status"\s*:\s*(\d+)',
                ])

        return result

    def _get_live_page_info(self, web_rid: str) -> Dict[str, str]:
        """请求直播页并提取 room_id、user_unique_id、ttwid 等信息。"""
        url = f"https://live.douyin.com/{web_rid}"
        try:
            headers = HeaderBuilder.build(HeaderType.DOC, auth=self.auth).get()
            headers['referer'] = 'https://live.douyin.com/?from_nav=1'
            response = requests.get(
                url,
                headers=headers,
                cookies=getattr(self.auth, 'cookie', {}) or None,
                timeout=10,
            )
            response_cookies = response.cookies.get_dict()
            self._sync_auth_cookie(response_cookies)

            page_info = self._parse_live_page_html(response.text)
            page_info['ttwid'] = (
                response_cookies.get('ttwid')
                or getattr(self.auth, 'cookie', {}).get('ttwid', '')
            )
            if page_info.get('room_id'):
                logger.info(
                    "直播页解析成功: room_id={}, user_unique_id={}, ttwid={}",
                    page_info.get('room_id'),
                    bool(page_info.get('user_unique_id')),
                    bool(page_info.get('ttwid')),
                )
            else:
                logger.warning("直播页未解析到 room_id")
            return page_info
        except Timeout:
            logger.error(f"获取直播页超时: {url}")
        except RequestException as e:
            logger.error(f"获取直播页网络请求失败: {e}")
        except Exception as e:
            logger.error(f"解析直播页失败: {e}")
        return {}

    @staticmethod
    def _merge_live_metadata(room_info: Dict, page_info: Dict) -> Dict:
        """把直播页解析结果补到 API 房间信息里。"""
        if not room_info:
            return room_info
        if not page_info:
            return room_info

        for key in ('room_id', 'web_rid', 'user_id', 'user_unique_id', 'ttwid', 'anchor_id', 'sec_uid'):
            if page_info.get(key) and not room_info.get(key):
                room_info[key] = page_info[key]

        if page_info.get('title') and not room_info.get('title'):
            room_info['title'] = page_info['title']
        if page_info.get('status') and not room_info.get('status'):
            try:
                room_info['status'] = int(page_info['status'])
            except ValueError:
                room_info['status'] = page_info['status']

        owner = room_info.get('owner') or {}
        if page_info.get('anchor_id') and not owner.get('uid'):
            owner['uid'] = page_info['anchor_id']
        if page_info.get('sec_uid') and not owner.get('sec_uid'):
            owner['sec_uid'] = page_info['sec_uid']
        room_info['owner'] = owner
        return room_info
    
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

        # 先请求直播页。弹幕 WebSocket 的签名需要页面里的 user_unique_id，
        # 不能再使用随机 user_id，否则容易表现为连接超时。
        page_info = self._get_live_page_info(web_rid)
        if page_info:
            page_info['web_rid'] = web_rid
        
        # 方案1: 使用 Web API 获取（推荐，更稳定）
        room_info = self._get_room_info_via_api(web_rid)
        if room_info and room_info.get('room_id'):
            return self._merge_live_metadata(room_info, page_info)
        
        # 方案2: 从网页解析 room_id
        logger.warning("Web API 获取失败，尝试从网页解析 room_id")
        live_url = f"https://live.douyin.com/{web_rid}"
        room_id = page_info.get('room_id') or self._get_room_id(live_url)
        
        if room_id:
            stream_info = self._get_stream_url(room_id)
            if stream_info:
                result = {
                    'room_id': room_id,
                    'web_rid': web_rid,
                    'user_id': page_info.get('user_id', ''),
                    'user_unique_id': page_info.get('user_unique_id', ''),
                    'ttwid': page_info.get('ttwid', ''),
                    'owner': stream_info.get('owner', {}),
                    'stream_url': stream_info.get('stream_url', {}),
                    'title': stream_info.get('title', ''),
                    'user_count': stream_info.get('user_count', 0),
                    'status': stream_info.get('status', 0),
                }
                return self._merge_live_metadata(result, page_info)
        
        return self._merge_live_metadata(self._build_empty_result(web_rid), page_info)
    
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
            self._sync_auth_cookie(response.cookies.get_dict())
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
            # 注意：data.user 多数情况下是主播/房间用户，不一定是当前访问者。
            # 弹幕签名需要的是页面里的 viewer user_unique_id，API 只取显式字段。
            user_unique_id = str(
                data.get('data', {}).get('user_unique_id')
                or data.get('data', {}).get('web_user_id')
                or ''
            )
            ttwid = (
                response.cookies.get_dict().get('ttwid')
                or cookies.get('ttwid', '')
            )
            
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
                'user_id': user_unique_id,
                'user_unique_id': user_unique_id,
                'ttwid': ttwid,
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
            'user_id': '',
            'user_unique_id': '',
            'ttwid': '',
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
        self.is_running = True
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
        self._emit_error(f"直播弹幕连接失败: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket 关闭回调"""
        logger.warning(f"直播间 {self.live_url} 连接关闭: {close_status_code}, {close_msg}")
        self.is_running = False

    def _emit_error(self, message: str):
        """向前端推送弹幕错误，避免启动失败时只显示超时。"""
        logger.error(message)
        if self.message_callback:
            self.message_callback({'type': 'error', 'message': message})

    def _get_webcast_initial_response(self, room_id: str, user_id: str, web_rid: str) -> Dict[str, str]:
        """预取 `/webcast/im/fetch/`，拿到 cursor/internal_ext。

        Douyin_Spider 的可用链路会先请求一次 protobuf fetch，再把返回的
        cursor/internalExt 带入 WebSocket。缺少这一步时，签名即使能生成，
        也可能出现 WebSocket 长时间无响应/超时。
        """
        api_url = "https://live.douyin.com/webcast/im/fetch/"
        page_url = f"https://live.douyin.com/{web_rid or self._get_web_rid(self.live_url)}"
        profile = get_douyin_browser_profile(self.auth)
        headers = HeaderBuilder.build(HeaderType.FORM, auth=self.auth, profile=profile).get()
        headers['origin'] = 'https://live.douyin.com'
        headers['referer'] = page_url

        params = Params()
        (params
         .add_param("resp_content_type", "protobuf")
         .add_param("did_rule", "3")
         .add_param("device_id", "")
         .add_param("app_name", "douyin_web")
         .add_param("endpoint", "live_pc")
         .add_param("support_wrds", "1")
         .add_param("user_unique_id", str(user_id))
         .add_param("identity", "audience")
         .add_param("need_persist_msg_count", "15")
         .add_param("insert_task_id", "")
         .add_param("live_reason", "")
         .add_param("room_id", str(room_id))
         .add_param("version_code", "180800")
         .add_param("last_rtt", "0")
         .add_param("live_id", "1")
         .add_param("aid", "6383")
         .add_param("fetch_rule", "1")
         .add_param("cursor", "")
         .add_param("internal_ext", "")
         .add_param("device_platform", "web")
         .add_param("cookie_enabled", profile.get("cookie_enabled", "true"))
         .add_param("screen_width", profile.get("screen_width", "1707"))
         .add_param("screen_height", profile.get("screen_height", "960"))
         .add_param("browser_language", profile.get("browser_language", "zh-CN"))
         .add_param("browser_platform", profile.get("browser_platform", "Win32"))
         .add_param("browser_name", "Mozilla")
         .add_param("browser_version", profile.get("user_agent") or HeaderBuilder.ua)
         .add_param("browser_online", profile.get("browser_online", "true"))
         .add_param("tz_name", "Asia/Shanghai")
         .add_param("msToken", getattr(self.auth, "msToken", "") or profile.get("msToken", ""))
        )
        params.with_a_bogus(
            auth=self.auth,
            user_agent=profile.get("user_agent") or HeaderBuilder.ua,
            env=profile,
            page_url=page_url,
            url=api_url,
        )

        response = requests.get(
            api_url,
            headers=headers,
            params=params.get(),
            cookies=getattr(self.auth, 'cookie', {}) or None,
            timeout=10,
        )
        self._sync_auth_cookie(response.cookies.get_dict())
        if response.status_code != 200:
            raise RuntimeError(f"弹幕初始化接口返回 HTTP {response.status_code}")

        frame = Live_pb2.LiveResponse()
        try:
            frame.ParseFromString(response.content)
        except Exception as exc:
            preview = response.text[:120] if response.text else ''
            raise RuntimeError(f"弹幕初始化接口返回非 protobuf 数据: {preview}") from exc

        result = {
            "cursor": str(frame.cursor or ""),
            "internal_ext": frame.internalExt or "",
        }
        if not result["cursor"] and not result["internal_ext"]:
            raise RuntimeError("弹幕初始化接口未返回 cursor/internal_ext，请检查抖音直播 Cookie 是否有效")
        logger.info(
            "弹幕初始化成功: cursor={}, internal_ext={}",
            bool(result["cursor"]),
            bool(result["internal_ext"]),
        )
        return result
    
    def start_ws(self, room_info: Dict = None):
        """启动 WebSocket 连接"""
        logger.info(f"start_ws 被调用, room_info: {room_info is not None}")
        
        if room_info:
            self._room_info = room_info
        
        if not self._room_info:
            logger.error("未获取直播间信息")
            raise ValueError("未获取直播间信息，请先调用 get_room_info()")
        
        room_id = self._room_info.get('room_id', '')
        logger.info(f"room_id: {room_id}")
        
        if not room_id:
            self._emit_error("无法获取 room_id，无法建立弹幕连接")
            return
        
        user_id = (
            self._room_info.get('user_unique_id')
            or self._room_info.get('user_id')
            or ''
        )
        if not user_id:
            self._emit_error("无法获取 user_unique_id，无法建立弹幕连接；请更新抖音直播 Cookie 后重试")
            return
        
        # 获取 ttwid
        cookies = {}
        if hasattr(self.auth, 'cookie') and self.auth.cookie:
            cookies.update(self.auth.cookie)
        ttwid = self._room_info.get('ttwid') or cookies.get('ttwid', '')
        if not ttwid:
            self._emit_error("Cookie 中缺少 ttwid，无法建立弹幕连接")
            return
        self._sync_auth_cookie({'ttwid': ttwid})
        cookie_header = self._build_cookie_header(ttwid=ttwid)

        web_rid = self._room_info.get('web_rid') or self._get_web_rid(self.live_url)

        try:
            initial_response = self._get_webcast_initial_response(room_id, user_id, web_rid)
        except Exception as e:
            message = str(e) or "抖音直播弹幕初始化失败"
            self._emit_error(message)
            return

        try:
            signature = generate_signature(room_id, user_id)
        except Exception as e:
            message = str(e) or "抖音直播弹幕签名生成失败"
            self._emit_error(message)
            return

        profile = get_douyin_browser_profile(self.auth)
        user_agent = profile.get('user_agent') or HeaderBuilder.ua
        
        # 构建参数
        params = Params()
        (params
         .add_param('app_name', 'douyin_web')
         .add_param('version_code', '180800')
         .add_param('webcast_sdk_version', DOUYIN_LIVE_WEBCAST_SDK_VERSION)
         .add_param('update_version_code', DOUYIN_LIVE_WEBCAST_SDK_VERSION)
         .add_param('compress', 'gzip')
         .add_param('device_platform', 'web')
         .add_param('cookie_enabled', 'true')
         .add_param('screen_width', '1707')
         .add_param('screen_height', '960')
         .add_param('browser_language', 'zh-CN')
         .add_param('browser_platform', profile.get('browser_platform', 'Win32'))
         .add_param('browser_name', 'Mozilla')
         .add_param('browser_version', user_agent.split('Mozilla/')[-1] if 'Mozilla/' in user_agent else user_agent)
         .add_param('browser_online', 'true')
         .add_param('tz_name', 'Etc/GMT-8')
         .add_param('cursor', initial_response.get('cursor', ''))
         .add_param('internal_ext', initial_response.get('internal_ext', ''))
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
        
        wss_url = f"wss://webcast100-ws-web-hl.douyin.com/webcast/im/push/v2/?{urlencode(params.get())}"
        logger.info(f"WebSocket URL: {wss_url[:100]}...")
        
        self.ws = WebSocketApp(
            url=wss_url,
            header={
                'Pragma': 'no-cache',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
                'User-Agent': user_agent,
                'Upgrade': 'websocket',
                'Cache-Control': 'no-cache',
                'Connection': 'Upgrade',
            },
            cookie=cookie_header,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        logger.info("WebSocket 实例已创建，准备连接...")
        
        try:
            logger.info("调用 run_forever()...")
            self.ws.run_forever(origin='https://live.douyin.com')
            logger.info("run_forever() 已返回")
        except Exception as e:
            self._emit_error(f"直播弹幕连接失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            if self.ws:
                self.ws.close()
    
    def stop(self):
        """停止 WebSocket 连接"""
        self.is_running = False
        if self.ws:
            self.ws.close()
