# -*- coding: utf-8 -*-
"""
用户信息服务
"""

import os
from typing import Any, Callable, Dict, List, Optional

from ..core.api_client import QuarkAPIClient
from ..exceptions import APIError


class UserInfoService:
    """用户信息载服务"""

    def __init__(self, client: QuarkAPIClient):
        """
        初始化用户信息服务

        Args:
            client: API客户端实例
        """
        self.client = client

    def get_user_info(self) -> Dict[str, Any]:
        """获取用户信息"""
        import httpx
        
        user_info = {
            'nickname': '',
            'avatar': '',
            'use_capacity': 0,
            'total_capacity': 0
        }

        # 直接使用 httpx 调用 member API，避免额外的参数
        params = {
            'pr': 'ucpro',
            'fr': 'pc',
            'uc_param_str': '',
            'fetch_subscribe': 'true',
            '_ch': 'home',
            'fetch_identity': 'true'
        }
        
        headers = {
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
            'origin': 'https://pan.quark.cn',
            'referer': 'https://pan.quark.cn/',
            'accept': 'application/json, text/plain, */*',
        }
        
        if self.client.cookies:
            headers['cookie'] = self.client.cookies
        
        try:
            response_user = httpx.get(
                'https://pan.quark.cn/account/info',
                params=params,
                headers=headers,
                timeout=30.0
            )
            if response_user.status_code == 200:
                result = response_user.json()
                if isinstance(result, dict) and 'data' in result:
                    data = result['data']
                    if data and isinstance(data, dict):
                        user_info['nickname'] = data.get('nickname', '')
                        user_info['avatar'] = data.get('avatar', '')


            response_storage = httpx.get(
                'https://drive-pc.quark.cn/1/clouddrive/member',
                params=params,
                headers=headers,
                timeout=30.0
            )
            
            if response_storage.status_code == 200:
                result = response_storage.json()
                if isinstance(result, dict) and 'data' in result:
                    data = result['data']
                    if data and isinstance(data, dict):
                        user_info['use_capacity'] = data.get('use_capacity', 0)
                        user_info['total_capacity'] = data.get('total_capacity', 0)
           
        except Exception as e:
            # 获取用户信息失败
            pass
        
        return user_info
