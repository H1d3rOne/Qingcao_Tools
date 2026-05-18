"""
抖音爬虫模块 - 视频相关
"""
import json
import asyncio
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode

from loguru import logger
import httpx
import requests as req_lib
req_lib.packages.urllib3.disable_warnings()

from app.modules.douyin.common.base import BaseSpider
from app.modules.douyin.common.auth import DouyinAuth
from app.modules.douyin.common.params import Params
from app.modules.douyin.common.header import HeaderBuilder, HeaderType
from app.core.config import settings


class DouyinSpider(BaseSpider):
    """抖音爬虫"""
    
    BASE_URL = "https://www.douyin.com"
    
    def __init__(self, auth: DouyinAuth, timeout: int = None):
        super().__init__(timeout)
        self.auth = auth
    
    def _get_headers(self, referer: str = None) -> dict:
        """获取请求头 - 使用HeaderBuilder构建完整headers"""
        header = HeaderBuilder.build(HeaderType.GET)
        header.set_header('cookie', self.auth.cookie_str)
        if referer:
            header.set_referer(referer)
        return header.get()
    
    async def _search_get(self, url: str, params: dict, headers: dict) -> dict:
        """使用 requests 库发送搜索请求（与 DouYin_Spider 一致），避免 httpx TLS 指纹差异"""
        def _do_request():
            resp = req_lib.get(
                url,
                headers=headers,
                cookies=self.auth.cookie,
                params=params,
                verify=False
            )
            return json.loads(resp.text)
        return await asyncio.to_thread(_do_request)

    def _safe_json_parse(self, response: httpx.Response) -> dict:
        """安全解析 JSON 响应"""
        try:
            # 尝试直接解析JSON
            try:
                data = response.json()
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                # 如果直接解析失败，尝试读取文本内容
                logger.warning(f"JSON直接解析失败: {e}, 尝试读取文本")
                text = response.text
                data = json.loads(text)
            
            # 检查抖音API返回的状态码
            status_code = data.get("status_code", 0)
            status_msg = data.get("status_msg", "")
            
            if status_code != 0:
                error_msg = status_msg or f"抖音API错误: status_code={status_code}"
                logger.error(f"抖音API返回错误: {error_msg}, 完整响应: {data}")
                
                # 常见错误码处理
                if status_code == 5:
                    raise ValueError("请求参数错误或缺少必要参数(verifyFp/fp)，请检查请求参数或更新Cookie")
                elif status_code == 8:
                    raise ValueError("请求被拦截(blocked)，请检查Cookie是否有效或是否需要验证码")
                elif status_code == 9:
                    raise ValueError("请求频率过高，请稍后重试")
                elif "blocked" in str(data).lower():
                    raise ValueError("请求被抖音反爬机制拦截，请更新Cookie或降低请求频率")
                else:
                    raise ValueError(error_msg)
            
            return data
            
        except json.JSONDecodeError as e:
            # 检查是否是 HTML 响应（通常是因为需要登录或被封禁）
            content_type = response.headers.get("content-type", "")
            text_preview = response.text[:500] if response.text else "(empty)"
            logger.error(f"JSON 解析失败: {e}, Content-Type: {content_type}, Response: {text_preview}")
            
            if "html" in content_type or (response.text and "<!DOCTYPE" in response.text[:100]):
                raise ValueError("抖音 API 返回了非 JSON 响应，可能需要配置有效的 Cookie 或遇到验证码")
            
            # 检查是否包含 blocked 关键字
            if response.text and "blocked" in response.text.lower():
                raise ValueError("请求被抖音反爬机制拦截(blocked)，请更新Cookie或检查请求参数")
            
            raise ValueError(f"解析响应失败: {text_preview}")
    
    async def get_work_info(self, url: str) -> dict:
        """获取作品信息"""
        # 解析短链接
        url = await self.resolve_short_url(url)
        aweme_id = self.extract_aweme_id(url)
        if not aweme_id:
            raise ValueError("无法从 URL 提取作品 ID")
        
        api_url = f"{self.BASE_URL}/aweme/v1/web/aweme/detail/"
        
        # 构建完整参数
        params_builder = Params()
        params_builder.with_platform().with_web_id(auth=self.auth, url=url).with_ms_token()
        params_builder.with_verify_fp(self.auth.verifyFp)  # 添加 verifyFp 参数
        params_builder.update_params({
            "aweme_id": aweme_id,
        })
        params_builder.with_a_bogus()
        params = params_builder.get()
        
        headers = self._get_headers(f"{self.BASE_URL}/video/{aweme_id}")
        
        logger.info(f"获取作品信息: aweme_id={aweme_id}")
        
        response = await self.request("GET", api_url, params=params, headers=headers)
        data = self._safe_json_parse(response)
        
        if "aweme_detail" not in data:
            logger.error(f"获取作品信息失败: {data}")
            raise ValueError(f"获取作品信息失败: {data.get('status_msg', '未知错误')}")
        
        return self._parse_work_info(data["aweme_detail"])
    
    def _parse_work_info(self, data: dict) -> dict:
        """解析作品信息"""
        author = data.get("author", {})
        statistics = data.get("statistics", {})
        video = data.get("video", {})
        music = data.get("music", {})
        images = data.get("images", [])
        
        # 判断是否为视频作品（图文作品的 images 列表不为空）
        is_video_work = not images or data.get("aweme_type") == 0
        
        # 从 video.play_addr.url_list 获取视频URL，优先选择 https://v11 开头的
        default_video_url = None
        video_qualities = {}
        
        play_addr = video.get("play_addr", {})
        url_list = play_addr.get("url_list", [])
        
        # 打印所有URL用于调试
        if url_list:
            for i, url in enumerate(url_list[:3]):  # 只打印前3个
                logger.debug(f"URL[{i}]: {url[:100]}..." if len(url) > 100 else f"URL[{i}]: {url}")
        
        # 优先选择 https://v11 开头的URL
        for url in url_list:
            if url and url.startswith("https://v11"):
                default_video_url = url
                break
        
        # 如果没有 v11 开头的，选择第一个非 mp3 的 URL
        if not default_video_url and url_list:
            for url in url_list:
                if url and not url.endswith('.mp3'):
                    default_video_url = url
                    break
            # 如果全是mp3，取第一个（可能是视频链接带mp3后缀的特殊情况）
            if not default_video_url and url_list:
                default_video_url = url_list[0]
        
        # 解析不同质量的视频链接（如果有 bit_rate）
        bit_rate_list = video.get("bit_rate", [])
        if bit_rate_list:
            for bit_rate in bit_rate_list:
                quality_type = bit_rate.get("quality_type")
                bit_rate_play_addr = bit_rate.get("play_addr", {})
                bit_rate_url_list = bit_rate_play_addr.get("url_list", [])

                # 优先选择 https://v11 开头的
                quality_url = None
                for url in bit_rate_url_list:
                    if url and url.startswith("https://v11"):
                        quality_url = url
                        break
                if not quality_url and bit_rate_url_list:
                    quality_url = bit_rate_url_list[0]

                if not quality_url:
                    continue

                quality_name_map = {
                    7: "hd2k",
                    1: "super",
                    10: "high",
                    24: "standard",
                }
                quality_name = quality_name_map.get(quality_type)

                if not quality_name:
                    w = bit_rate_play_addr.get("width", 0)
                    h = bit_rate_play_addr.get("height", 0)
                    short_side = min(w, h) if w and h else max(w, h)
                    if short_side >= 1440:
                        quality_name = "hd2k"
                    elif short_side >= 1080:
                        quality_name = "super"
                    elif short_side >= 720:
                        quality_name = "high"
                    else:
                        quality_name = "standard"

                # 同名质量只保留第一个（通常码率最高）
                if quality_name in video_qualities:
                    continue

                video_qualities[quality_name] = {
                    "quality_type": quality_type,
                    "url": quality_url,
                    "width": bit_rate_play_addr.get("width"),
                    "height": bit_rate_play_addr.get("height"),
                }

        # 如果没有解析到任何质量但有默认视频URL，用默认URL作为 super 质量
        if not video_qualities and default_video_url:
            video_qualities["super"] = {
                "quality_type": 1,
                "url": default_video_url,
                "width": play_addr.get("width"),
                "height": play_addr.get("height"),
            }
        
        # 图文作品不返回视频URL
        if not is_video_work:
            default_video_url = None
        
        # 获取音乐URL（图文作品需要）
        music_url = None
        if music:
            play_url = music.get("play_url", {})
            music_url_list = play_url.get("url_list", [])
            if music_url_list:
                music_url = music_url_list[0]
        
        logger.info(f"解析作品完成: aweme_id={data.get('aweme_id')}, is_video={is_video_work}, "
                   f"video_url={default_video_url[:80] if default_video_url else 'None'}, "
                   f"music_url={music_url[:60] if music_url else 'None'}, "
                   f"images_count={len(images) if images else 0}")
        
        return {
            "aweme_id": data.get("aweme_id"),
            "title": data.get("desc", "")[:500],
            "desc": data.get("desc", ""),
            "author_uid": author.get("uid"),
            "author_nickname": author.get("nickname"),
            "author_avatar": author.get("avatar_thumb", {}).get("url_list", [""])[0],
            "author_sec_uid": author.get("sec_uid"),
            "cover_url": video.get("cover", {}).get("url_list", [""])[0],
            "video_url": default_video_url,
            "video_qualities": video_qualities if video_qualities else None,
            "images": [img.get("url_list", [""])[0] for img in images] if images else None,
            "duration": video.get("duration", 0),
            "music_title": music.get("title"),
            "music_url": music_url,
            "digg_count": statistics.get("digg_count", 0),
            "comment_count": statistics.get("comment_count", 0),
            "share_count": statistics.get("share_count", 0),
            "collect_count": statistics.get("collect_count", 0),
            "play_count": statistics.get("play_count", 0),
            "is_video": is_video_work,
            "create_time": data.get("create_time"),
            "work_url": f"https://www.douyin.com/video/{data.get('aweme_id')}"
        }
    
    async def get_work_comments(self, url: str, limit: int = 20, cursor: int = 0) -> List[dict]:
        """获取作品评论"""
        # 解析短链接
        url = await self.resolve_short_url(url)
        aweme_id = self.extract_aweme_id(url)
        if not aweme_id:
            raise ValueError("无法从 URL 提取作品 ID")
        
        api_url = f"{self.BASE_URL}/aweme/v1/web/comment/list/"
        
        comments = []
        cursor_str = str(cursor)
        
        while len(comments) < limit:
            # 构建完整参数
            params_builder = Params()
            params_builder.with_platform().with_web_id(auth=self.auth, url=url).with_ms_token()
            params_builder.with_verify_fp(self.auth.verifyFp)  # 添加 verifyFp 参数
            params_builder.update_params({
                "aweme_id": aweme_id,
                "cursor": cursor_str,
                "count": min(20, limit - len(comments)),
            })
            params_builder.with_a_bogus()
            params = params_builder.get()
            
            headers = self._get_headers(f"{self.BASE_URL}/video/{aweme_id}")
            
            response = await self.request("GET", api_url, params=params, headers=headers)
            data = self._safe_json_parse(response)
            
            comment_list = data.get("comments", [])
            if not comment_list:
                break
            
            for item in comment_list:
                comments.append(self._parse_comment(item))
            
            cursor = str(data.get("cursor", "0"))
            if data.get("has_more") != 1:
                break
        
        return comments[:limit]
    
    def _parse_comment(self, data: dict) -> dict:
        """解析评论"""
        user = data.get("user", {})
        return {
            "cid": data.get("cid"),
            "aweme_id": data.get("aweme_id"),
            "text": data.get("text"),
            "digg_count": data.get("digg_count", 0),
            "user_uid": user.get("uid"),
            "user_nickname": user.get("nickname"),
            "user_avatar": user.get("avatar_thumb", {}).get("url_list", [""])[0],
            "create_time": data.get("create_time"),
        }
    
    async def get_user_info(self, url: str) -> dict:
        """获取用户信息"""
        sec_uid = self.extract_sec_uid(url)
        if not sec_uid:
            raise ValueError("无法从 URL 提取用户 sec_uid")
        return await self.get_user_info_by_sec_uid(sec_uid)
    
    async def get_user_info_by_sec_uid(self, sec_uid: str) -> dict:
        """通过 sec_uid 获取用户信息"""
        api_url = f"{self.BASE_URL}/aweme/v1/web/user/profile/other/"
        
        # 构建完整参数
        params_builder = Params()
        params_builder.with_platform().with_web_id(auth=self.auth, url=f"{self.BASE_URL}/user/{sec_uid}").with_ms_token()
        params_builder.with_verify_fp(self.auth.verifyFp)  # 添加 verifyFp 参数
        params_builder.update_params({
            "sec_user_id": sec_uid,
        })
        params_builder.with_a_bogus()
        params = params_builder.get()
        
        headers = self._get_headers(f"{self.BASE_URL}/user/{sec_uid}")
        
        response = await self.request("GET", api_url, params=params, headers=headers)
        data = self._safe_json_parse(response)
        
        if "user" not in data:
            raise ValueError(f"获取用户信息失败: {data}")
        
        # 记录原始用户数据，用于调试
        logger.debug(f"抖音用户信息原始数据: {data.get('user', {})}")
        
        return self._parse_user_info(data["user"])
    
    def _parse_user_info(self, data: dict) -> dict:
        """解析用户信息"""
        # 尝试多种可能的字段名
        ip_location = (
            data.get("ip_location") or 
            data.get("location") or 
            data.get("province") or 
            ""
        )
        
        # 尝试多种可能的年龄字段
        user_age = data.get("user_age") or data.get("age")
        
        # 尝试多种可能的国家字段
        country = data.get("country") or data.get("region")
        
        return {
            "uid": data.get("uid"),
            "sec_uid": data.get("sec_uid"),
            "unique_id": data.get("unique_id"),
            "nickname": data.get("nickname"),
            "gender": data.get("gender"),
            "user_age": user_age,
            "ip_location": ip_location,
            "country": country,
            "signature": data.get("signature"),
            "avatar": data.get("avatar_thumb", {}).get("url_list", [""])[0],
            "follower_count": data.get("follower_count", 0),
            "following_count": data.get("following_count", 0),
            "aweme_count": data.get("aweme_count", 0),
            "favoriting_count": data.get("favoriting_count", 0),
        }
    
    async def get_user_works(self, url: str, limit: int = 20) -> List[dict]:
        """获取用户作品列表"""
        sec_uid = self.extract_sec_uid(url)
        if not sec_uid:
            raise ValueError("无法从 URL 提取用户 sec_uid")
        return await self.get_user_works_by_sec_uid(sec_uid, limit)
    
    async def get_user_works_by_sec_uid(self, sec_uid: str, limit: int = 20, cursor: int = 0) -> List[dict]:
        """通过 sec_uid 获取用户作品列表"""
        api_url = f"{self.BASE_URL}/aweme/v1/web/aweme/post/"
        headers = self._get_headers(f"{self.BASE_URL}/user/{sec_uid}")

        works = []
        max_cursor = str(cursor)

        while len(works) < limit:
            # 构建完整参数
            params_builder = Params()
            params_builder.with_platform().with_web_id(auth=self.auth, url=f"{self.BASE_URL}/user/{sec_uid}").with_ms_token()
            params_builder.with_verify_fp(self.auth.verifyFp)  # 添加 verifyFp 参数
            params_builder.update_params({
                "sec_user_id": sec_uid,
                "max_cursor": max_cursor,
                "count": min(18, limit - len(works)),
                "publish_video_strategy_type": "2",
                "locate_query": "false",
                "show_live_replay_strategy": "1",
                "need_time_list": "1" if max_cursor == "0" else "0",
                "time_list_query": "0",
                "whale_cut_token": "",
                "cut_version": "1",
            })
            params_builder.with_a_bogus()
            params = params_builder.get()

            response = await self.request("GET", api_url, params=params, headers=headers)
            data = self._safe_json_parse(response)

            # 检查API错误状态码
            status_code = data.get("status_code") if data else None
            if status_code and status_code != 0:
                error_msg = data.get("status_msg", f"抖音API错误: {status_code}")
                logger.error(f"获取用户作品失败: {error_msg}")
                break

            # 检查数据格式
            if not data or "aweme_list" not in data:
                logger.error(f"获取用户作品失败: API返回数据格式错误 - keys={list(data.keys()) if data else None}")
                break

            aweme_list = data.get("aweme_list", [])
            logger.info(f"获取到 {len(aweme_list)} 个作品, has_more={data.get('has_more')}, max_cursor={data.get('max_cursor')}")
            if not aweme_list:
                break

            for item in aweme_list:
                works.append(self._parse_work_info(item))

            max_cursor = str(data.get("max_cursor", "0"))
            if data.get("has_more") != 1:
                break

        return works[:limit]
    
    async def search_works(
        self,
        keyword: str,
        offset: str = "0",
        count: int = 25,
        sort_type: str = "0",
        publish_time: str = "0",
        filter_duration: str = "",
        search_range: str = "",
        content_type: str = ""
    ) -> dict:
        """搜索作品（单页模式）"""
        import uuid
        import urllib.parse

        api = "/aweme/v1/web/general/search/single/"
        refer = f"{self.BASE_URL}/search/{urllib.parse.quote(keyword)}?aid={uuid.uuid4()}&type=general"

        filter_selected = ('{"sort_type":"%s","publish_time":"%s","filter_duration":"%s",'
                           '"search_range":"%s","content_type":"%s"}') % (
                           sort_type, publish_time, filter_duration, search_range, content_type)

        params = Params()
        params.add_param("device_platform", "webapp")
        params.add_param("aid", "6383")
        params.add_param("channel", "channel_pc_web")
        params.add_param("search_channel", "aweme_general")
        params.add_param("enable_history", "1")
        params.add_param("filter_selected", filter_selected)
        params.add_param("keyword", keyword)
        params.add_param("search_source", "tab_search")
        params.add_param("query_correct_type", "1")
        params.add_param("is_filter_search", "1")
        params.add_param("from_group_id", "")
        params.add_param("offset", offset)
        params.add_param("count", str(count))
        params.add_param("need_filter_settings", "1" if offset == "0" else "0")
        params.add_param("list_type", "single")
        params.add_param("update_version_code", "170400")
        params.add_param("pc_client_type", "1")
        params.add_param("version_code", "190600")
        params.add_param("version_name", "19.6.0")
        params.add_param("cookie_enabled", "true")
        params.add_param("screen_width", "1707")
        params.add_param("screen_height", "960")
        params.add_param("browser_language", "zh-CN")
        params.add_param("browser_platform", "Win32")
        params.add_param("browser_name", "Edge")
        params.add_param("browser_version", "125.0.0.0")
        params.add_param("browser_online", "true")
        params.add_param("engine_name", "Blink")
        params.add_param("engine_version", "125.0.0.0")
        params.add_param("os_name", "Windows")
        params.add_param("os_version", "10")
        params.add_param("cpu_core_num", "32")
        params.add_param("device_memory", "8")
        params.add_param("platform", "PC")
        params.add_param("downlink", "10")
        params.add_param("effective_type", "4g")
        params.add_param("round_trip_time", "50")
        params.with_web_id(self.auth, refer)
        params.add_param("msToken", self.auth.msToken)
        params.with_a_bogus()

        headers = HeaderBuilder.build(HeaderType.GET)
        headers.set_referer(refer)

        logger.info(f"搜索作品请求: keyword={keyword}, offset={offset}")
        data = await self._search_get(f"{self.BASE_URL}{api}", params=params.get(), headers=headers.get())
        logger.info(f"搜索响应: status_code={data.get('status_code')}, has_more={data.get('has_more')}")

        search_nil_info = data.get("search_nil_info", {})
        if search_nil_info and search_nil_info.get("search_nil_type") == "verify_check":
            raise ValueError("抖音需要验证码验证，请在浏览器中访问抖音网站完成验证后更新Cookie配置")

        items = data.get("data", [])
        works = []
        for item in items:
            aweme_info = item.get("aweme_info", item)
            if aweme_info:
                works.append(self._parse_work_info(aweme_info))

        has_more = data.get("has_more") == 1
        next_offset = str(int(offset) + len(items))

        return {"items": works, "has_more": has_more, "next_offset": next_offset}

    async def search_videos(
        self,
        keyword: str,
        offset: str = "0",
        count: int = 25,
        search_id: str = "",
        sort_type: str = "0",
        publish_time: str = "0",
        filter_duration: str = "",
        search_range: str = "0"
    ) -> dict:
        """搜索视频频道（单页模式）"""
        import uuid
        import urllib.parse

        api = "/aweme/v1/web/search/item/"
        refer = f"{self.BASE_URL}/search/{urllib.parse.quote(keyword)}?aid={uuid.uuid4()}&type=video"

        params = Params()
        params.add_param("device_platform", "webapp")
        params.add_param("aid", "6383")
        params.add_param("channel", "channel_pc_web")
        params.add_param("search_channel", "aweme_video_web")
        params.add_param("enable_history", "1")
        params.add_param("sort_type", sort_type)
        params.add_param("publish_time", publish_time)
        params.add_param("filter_duration", filter_duration)
        params.add_param("search_range", search_range)
        params.add_param("keyword", keyword)
        params.add_param("search_source", "normal_search")
        params.add_param("query_correct_type", "1")
        params.add_param("is_filter_search", "1")
        params.add_param("from_group_id", "")
        params.add_param("offset", offset)
        params.add_param("count", str(count))
        params.add_param("need_filter_settings", "1" if offset == "0" else "0")
        if search_id:
            params.add_param("search_id", search_id)
        params.add_param("list_type", "single")
        params.add_param("update_version_code", "170400")
        params.add_param("pc_client_type", "1")
        params.add_param("version_code", "170400")
        params.add_param("version_name", "17.4.0")
        params.add_param("cookie_enabled", "true")
        params.add_param("screen_width", "1707")
        params.add_param("screen_height", "960")
        params.add_param("browser_language", "zh-CN")
        params.add_param("browser_platform", "Win32")
        params.add_param("browser_name", "Edge")
        params.add_param("browser_version", "125.0.0.0")
        params.add_param("browser_online", "true")
        params.add_param("engine_name", "Blink")
        params.add_param("engine_version", "125.0.0.0")
        params.add_param("os_name", "Windows")
        params.add_param("os_version", "10")
        params.add_param("cpu_core_num", "32")
        params.add_param("device_memory", "8")
        params.add_param("platform", "PC")
        params.add_param("downlink", "10")
        params.add_param("effective_type", "4g")
        params.add_param("round_trip_time", "50")
        params.with_web_id(self.auth, refer)
        params.add_param("msToken", self.auth.msToken)
        params.with_a_bogus()

        headers = HeaderBuilder.build(HeaderType.GET)
        headers.set_referer(refer)

        logger.info(f"搜索视频请求: keyword={keyword}, offset={offset}")
        data = await self._search_get(f"{self.BASE_URL}{api}", params=params.get(), headers=headers.get())

        search_nil_info = data.get("search_nil_info", {})
        if search_nil_info and search_nil_info.get("search_nil_type") == "verify_check":
            raise ValueError("抖音需要验证码验证，请在浏览器中访问抖音网站完成验证后更新Cookie配置")

        new_search_id = data.get("log_pb", {}).get("impr_id", search_id)

        items = data.get("data", [])
        works = []
        for item in items:
            aweme_info = item.get("aweme_info", item)
            if aweme_info:
                works.append(self._parse_work_info(aweme_info))

        has_more = data.get("has_more") == 1
        next_offset = str(int(offset) + len(items))

        return {"items": works, "has_more": has_more, "next_offset": next_offset, "search_id": new_search_id}

    async def search_users(self, keyword: str, offset: str = "0", count: int = 25) -> dict:
        """搜索用户（单页模式）"""
        import uuid
        import urllib.parse

        api = "/aweme/v1/web/discover/search"
        refer = f"{self.BASE_URL}/search/{urllib.parse.quote(keyword)}?aid={uuid.uuid4()}&type=general"

        params = Params()
        params.add_param("device_platform", "webapp")
        params.add_param("aid", "6383")
        params.add_param("channel", "channel_pc_web")
        params.add_param("search_channel", "aweme_user_web")
        params.add_param("search_filter_value", '{"douyin_user_fans":[""],"douyin_user_type":[""]}')
        params.add_param("keyword", keyword)
        params.add_param("search_source", "switch_tab")
        params.add_param("query_correct_type", "1")
        params.add_param("is_filter_search", "1")
        params.add_param("offset", offset)
        params.add_param("count", str(count))
        params.add_param("need_filter_settings", "1" if offset == "0" else "0")
        params.add_param("list_type", "single")
        params.add_param("update_version_code", "170400")
        params.add_param("pc_client_type", "1")
        params.add_param("version_code", "190600")
        params.add_param("version_name", "19.6.0")
        params.add_param("cookie_enabled", "true")
        params.add_param("screen_width", "1707")
        params.add_param("screen_height", "960")
        params.add_param("browser_language", "zh-CN")
        params.add_param("browser_platform", "Win32")
        params.add_param("browser_name", "Edge")
        params.add_param("browser_version", "125.0.0.0")
        params.add_param("browser_online", "true")
        params.add_param("engine_name", "Blink")
        params.add_param("engine_version", "125.0.0.0")
        params.add_param("os_name", "Windows")
        params.add_param("os_version", "10")
        params.add_param("cpu_core_num", "32")
        params.add_param("device_memory", "8")
        params.add_param("platform", "PC")
        params.add_param("downlink", "10")
        params.add_param("effective_type", "4g")
        params.add_param("round_trip_time", "50")
        params.with_web_id(self.auth, refer)
        params.add_param("msToken", self.auth.msToken)
        params.with_a_bogus()

        headers = HeaderBuilder.build(HeaderType.GET)
        headers.set_referer(refer)

        logger.info(f"搜索用户请求: keyword={keyword}, offset={offset}")
        response = await self.request("GET", f"{self.BASE_URL}{api}", params=params.get(), headers=headers.get(), cookies=self.auth.cookie)
        data = self._safe_json_parse(response)

        search_nil_info = data.get("search_nil_info", {})
        if search_nil_info and search_nil_info.get("search_nil_type") == "verify_check":
            raise ValueError("抖音需要验证码验证，请在浏览器中访问抖音网站完成验证后更新Cookie配置")

        user_list = data.get("user_list", [])
        users = []
        for item in user_list:
            user_info = item.get("user_info", {})
            users.append(self._parse_user_info(user_info))

        has_more = data.get("has_more") == 1
        next_offset = str(int(offset) + len(user_list))

        return {"items": users, "has_more": has_more, "next_offset": next_offset}
    
    async def search_live(self, keyword: str, offset: str = "0", count: int = 25) -> dict:
        """搜索直播（单页模式）"""
        import uuid
        import urllib.parse

        api = "/aweme/v1/web/live/search/"
        refer = f"{self.BASE_URL}/search/{urllib.parse.quote(keyword)}?aid={uuid.uuid4()}&type=live"

        params = Params()
        params.add_param("device_platform", "webapp")
        params.add_param("aid", "6383")
        params.add_param("channel", "channel_pc_web")
        params.add_param("search_channel", "aweme_live")
        params.add_param("keyword", keyword)
        params.add_param("search_source", "normal_search")
        params.add_param("query_correct_type", "1")
        params.add_param("is_filter_search", "0")
        params.add_param("from_group_id", "")
        params.add_param("offset", offset)
        params.add_param("count", str(count))
        params.add_param("need_filter_settings", "1" if offset == "0" else "0")
        params.add_param("list_type", "single")
        params.add_param("update_version_code", "170400")
        params.add_param("pc_client_type", "1")
        params.add_param("version_code", "190600")
        params.add_param("version_name", "19.6.0")
        params.add_param("cookie_enabled", "true")
        params.add_param("screen_width", "1707")
        params.add_param("screen_height", "960")
        params.add_param("browser_language", "zh-CN")
        params.add_param("browser_platform", "Win32")
        params.add_param("browser_name", "Edge")
        params.add_param("browser_version", "125.0.0.0")
        params.add_param("browser_online", "true")
        params.add_param("engine_name", "Blink")
        params.add_param("engine_version", "125.0.0.0")
        params.add_param("os_name", "Windows")
        params.add_param("os_version", "10")
        params.add_param("cpu_core_num", "32")
        params.add_param("device_memory", "8")
        params.add_param("platform", "PC")
        params.add_param("downlink", "10")
        params.add_param("effective_type", "4g")
        params.add_param("round_trip_time", "50")
        params.with_web_id(self.auth, refer)
        params.add_param("msToken", self.auth.msToken)
        params.with_a_bogus()

        headers = HeaderBuilder.build(HeaderType.GET)
        headers.set_referer(refer)

        logger.info(f"搜索直播请求: keyword={keyword}, offset={offset}")
        response = await self.request("GET", f"{self.BASE_URL}{api}", params=params.get(), headers=headers.get(), cookies=self.auth.cookie)
        data = self._safe_json_parse(response)

        search_nil_info = data.get("search_nil_info", {})
        if search_nil_info and search_nil_info.get("search_nil_type") == "verify_check":
            raise ValueError("抖音需要验证码验证，请在浏览器中访问抖音网站完成验证后更新Cookie配置")

        live_list = data.get("data", [])
        if not live_list:
            if "live_list" in data:
                live_list = data.get("live_list", [])
            elif "lives" in data:
                live_list = data.get("lives", [])

        lives = []
        for item in live_list:
            lives_data = item.get("lives", {})
            if not lives_data or not isinstance(lives_data, dict):
                continue
            author = lives_data.get("author", {})
            rawdata = lives_data.get("rawdata", {})
            if isinstance(rawdata, str):
                try:
                    rawdata = json.loads(rawdata)
                except:
                    rawdata = {}
            if not rawdata or not isinstance(rawdata, dict):
                continue
            live_info = self._parse_live_info_v3(rawdata, author)
            if live_info:
                lives.append(live_info)

        has_more = data.get("has_more") == 1
        next_offset = str(int(offset) + len(live_list))

        return {"items": lives, "has_more": has_more, "next_offset": next_offset}
    
    def _parse_live_info(self, data: dict) -> dict:
        """解析直播信息 - 旧格式"""
        owner = data.get("owner", {})
        return {
            "room_id": data.get("room_id"),
            "title": data.get("title", ""),
            "user_count": data.get("user_count", 0),
            "author_nickname": owner.get("nickname", ""),
            "author_avatar": owner.get("avatar_thumb", {}).get("url_list", [""])[0],
            "cover": data.get("cover", {}).get("url_list", [""])[0],
        }
    
    def _parse_live_info_v3(self, rawdata: dict, author: dict) -> dict:
        """解析直播信息 - 新格式（搜索结果 v3）
        
        数据结构：
        rawdata = {
            "id_str": "直播间ID",
            "title": "直播间标题",
            "user_count": 在线人数,
            "cover": {"url_list": [...]},
            "stream_url": {
                "rtmp_pull_url": "rtmp流",
                "flv_pull_url": {"FULL_HD1": "flv流"},
                "hls_pull_url": "hls流"
            }
        }
        author = {
            "nickname": "主播昵称",
            "avatar_thumb": {"url_list": [...]}
        }
        """
        # 获取房间ID
        room_id = rawdata.get("id_str") or rawdata.get("id") or ""
        
        # 获取标题
        title = rawdata.get("title", "") or rawdata.get("desc", "")
        
        # 获取在线人数
        user_count = rawdata.get("user_count", 0) or 0
        
        # 获取主播昵称
        author_nickname = author.get("nickname", "") or rawdata.get("owner", {}).get("nickname", "")
        
        # 获取主播 sec_uid
        author_sec_uid = author.get("sec_uid", "") or rawdata.get("owner", {}).get("sec_uid", "")
        
        # 获取主播头像
        avatar_thumb = author.get("avatar_thumb", {}) or author.get("avatar", {})
        if isinstance(avatar_thumb, dict) and avatar_thumb.get("url_list"):
            author_avatar = avatar_thumb.get("url_list", [""])[0]
        else:
            author_avatar = ""
        
        # 获取封面
        cover = rawdata.get("cover", {})
        if isinstance(cover, dict) and cover.get("url_list"):
            cover_url = cover.get("url_list", [""])[0]
        else:
            cover_url = ""
        
        # 获取直播流地址
        stream_url = rawdata.get("stream_url", {})
        # 优先使用 HLS 流
        hls_url = stream_url.get("hls_pull_url", "")
        flv_url = ""
        if isinstance(stream_url.get("flv_pull_url"), dict):
            # 获取最高质量的 FLV 流
            flv_pull_url = stream_url.get("flv_pull_url", {})
            for quality in ["FULL_HD1", "HD1", "SD2", "SD1"]:
                if quality in flv_pull_url:
                    flv_url = flv_pull_url[quality]
                    break
        rtmp_url = stream_url.get("rtmp_pull_url", "")
        
        return {
            "room_id": str(room_id),
            "title": title,
            "user_count": user_count,
            "author_nickname": author_nickname,
            "author_sec_uid": author_sec_uid,
            "author_avatar": author_avatar,
            "cover": cover_url,
            "stream_url": {
                "hls": hls_url,
                "flv": flv_url,
                "rtmp": rtmp_url
            }
        }
    
    def _parse_live_info_v2(self, data: dict) -> dict:
        """解析直播信息 - 新格式（搜索结果）
        
        数据结构示例：
        {
            "id": 7617477841839459072,
            "id_str": "7617477841839459072",
            "title": "你好～",
            "user_count": 7,
            "cover": {
                "url_list": ["https://...", "https://..."]
            },
            "owner": {
                "nickname": "笨蛋美女",
                "avatar_thumb": {
                    "url_list": [...]
                }
            }
        }
        """
        # 获取主播信息 - 可能在 owner 或 author 字段
        owner = data.get("owner", {}) or data.get("author", {})
        
        # 获取直播间ID - 多种字段名
        room_id = (
            data.get("id_str") or 
            data.get("id") or 
            data.get("room_id") or 
            data.get("room_id_str") or 
            data.get("aweme_id") or
            ""
        )
        
        # 标题
        title = data.get("title", "") or data.get("desc", "")
        
        # 观看人数
        user_count = data.get("user_count", 0) or data.get("stats", {}).get("user_count", 0)
        
        # 获取头像URL
        avatar_thumb = owner.get("avatar_thumb", {}) or owner.get("avatar", {})
        if isinstance(avatar_thumb, dict) and avatar_thumb.get("url_list"):
            avatar_url = avatar_thumb.get("url_list", [""])[0]
        else:
            avatar_url = ""
        
        # 获取封面URL - 直接从最外层 cover 字段获取
        cover = data.get("cover", {})
        if isinstance(cover, dict) and cover.get("url_list"):
            cover_url = cover.get("url_list", [""])[0]
        else:
            cover_url = ""
        
        return {
            "room_id": str(room_id) if room_id else "",
            "title": title,
            "user_count": user_count,
            "author_nickname": owner.get("nickname", ""),
            "author_avatar": avatar_url,
            "cover": cover_url,
        }
