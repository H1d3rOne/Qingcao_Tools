# -*- coding: utf-8 -*-
"""
文件下载服务
"""

import os
import sys
import httpx
import requests
import json
from pathlib import Path
from typing import Callable, Dict, List, Optional

# 支持直接运行：添加项目根目录到路径
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from quark_client.core.api_client import QuarkAPIClient
from quark_client.cookie_store import load_quark_cookie_string
from quark_client.exceptions import APIError
from quark_client.scripts.download import get_real_download_url


class FileDownloadService:
    """文件下载服务"""

    def __init__(self, client: QuarkAPIClient):
        """
        初始化文件下载服务

        Args:
            client: API客户端实例
        """
        self.client = client

    def get_download_url(self, file_id: str) -> str:
        """
        获取文件下载链接

        Args:
            file_id: 文件ID

        Returns:
            下载链接
        """

        # 使用与 reference.py 完全相同的参数
        params = {
            'pr': 'ucpro',
            'fr': 'pc',
            'sys': 'win32',
            've': '2.5.56',
            'ut': '',
            'guid': '',
        }
        params = {
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
        }
        cookies = load_quark_cookie_string()
        print(cookies)
        headers: Dict[str, str] = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160 Electron/18.3.5.4-b478491100 Safari/537.36 Channel/pckk_other_ch",
            'origin': 'https://pan.quark.cn',
            'referer': 'https://pan.quark.cn/',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cookie': cookies,
        }

        data = {'fids': [file_id]}

        # 使用完整的API端点URL，绕过基础URL拼接
        try:
            response = httpx.post(
                'https://drive-pc.quark.cn/1/clouddrive/file/download',
                json=data,
                params=params,
                headers=headers,
            ).json()
            # print(response.text)


            # 解析下载链接
            if isinstance(response, dict) and 'data' in response:
                data_list = response['data']
                if data_list and len(data_list) > 0:
                    download_info = data_list[0]
                    print(download_info)
                    return download_info.get('download_url', '')
        except Exception as e:
            print(f"请求失败: {e}")
            raise APIError("无法获取下载链接")

    def get_download_urls(self, file_ids: List[str]) -> Dict[str, str]:
        """
        批量获取文件下载链接

        Args:
            file_ids: 文件ID列表

        Returns:
            文件ID到下载链接的映射字典
        """
        # 添加必要的查询参数
        params = {
            'pr': 'ucpro',
            'fr': 'pc',
            'uc_param_str': ''
        }

        data = {'fids': file_ids}
        print(self.client)
        response = self.client.post('file/download', json_data=data, params=params)

        # 解析下载链接
        download_urls = {}
        if isinstance(response, dict) and 'data' in response:
            data_list = response['data']
            for download_info in data_list:
                fid = download_info.get('fid', '')
                download_url = download_info.get('download_url', '')
                if fid and download_url:
                    download_urls[fid] = download_url

        return download_urls

    def download_file(
        self,
        file_id: str,
        save_path: Optional[str] = None,
        chunk_size: int = 8192,
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        下载文件

        Args:
            file_id: 文件ID
            save_path: 保存路径，如果为None则使用文件原名
            chunk_size: 下载块大小
            progress_callback: 进度回调函数 (downloaded_bytes, total_bytes)

        Returns:
            实际保存的文件路径
        """

        # 获取下载链接和文件信息
        # 使用与 reference.py 完全相同的参数
        params = {
            'pr': 'ucpro',
            'fr': 'pc',
            'sys': 'win32',
            've': '2.5.56',
            'ut': '',
            'guid': '',
        }

        data = {'fids': [file_id]}

        # 使用完整的API端点URL，绕过基础URL拼接
        response = self.client.post(
            'file/download',
            json_data=data,
            params=params,
            base_url='https://drive-pc.quark.cn/1/clouddrive'
        )

        # 解析下载链接和文件信息
        if isinstance(response, dict) and 'data' in response:
            data_list = response['data']
            if data_list and len(data_list) > 0:
                download_info = data_list[0]
                download_url = download_info.get('download_url', '')
                file_name = download_info.get('file_name', f'file_{file_id}')
                _ = download_info.get('size', 0)  # file_size 暂时未使用
            else:
                raise APIError("无法获取下载信息")
        else:
            raise APIError("无法获取下载信息")

        if not download_url:
            raise APIError("无法获取下载链接")

        # 确定保存路径
        if save_path is None:
            save_path = file_name
        elif os.path.isdir(save_path):
            save_path = os.path.join(save_path, file_name)

        # 此时 save_path 不会是 None
        assert save_path is not None

        # 创建目录
        save_dir = os.path.dirname(save_path)
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)

        # 下载文件，使用与API客户端相同的session和完整的headers
        download_headers = {
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Referer': 'https://pan.quark.cn/',
            'Origin': 'https://pan.quark.cn',
            'Sec-Ch-Ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'Sec-Ch-Ua-Mobile': '?1',
            'Sec-Ch-Ua-Platform': '"Android"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36'
        }

        # 尝试多种下载方式
        success = False

        # 方法1: 使用API客户端的session
        try:
            with self.client._client.stream('GET', download_url,  # type: ignore[attr-defined]
                                            headers=download_headers) as response:
                response.raise_for_status()
                success = True

                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0

                with open(save_path, 'wb') as f:
                    for chunk in response.iter_bytes(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)

                            # 调用进度回调
                            if progress_callback:
                                progress_callback(downloaded_size, total_size)
        except Exception as e:
            # 第一种方法失败是正常的，静默切换到备用方法
            if "403" in str(e) or "Forbidden" in str(e):
                # 403错误是预期的，不显示错误信息
                pass
            else:
                # 其他错误可能需要用户知道
                print(f"下载方法1遇到问题，正在尝试备用方法...")
            success = False

        # 方法2: 如果方法1失败，尝试使用外部httpx客户端
        if not success:
            try:
                import httpx

                # 从API客户端获取cookies
                cookie_dict = {}
                if hasattr(self.client._client, 'cookies'):
                    for cookie in self.client._client.cookies.jar:  # type: ignore[attr-defined]
                        cookie_dict[cookie.name] = cookie.value

                # 添加cookies到headers
                if cookie_dict:
                    download_headers['Cookie'] = '; '.join([f'{k}={v}' for k, v in cookie_dict.items()])

                with httpx.stream('GET', download_url, headers=download_headers, timeout=60) as response:
                    response.raise_for_status()
                    success = True

                    # 获取文件大小
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0

                    with open(save_path, 'wb') as f:
                        for chunk in response.iter_bytes(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)

                                # 调用进度回调
                                if progress_callback:
                                    progress_callback(downloaded_size, total_size)
            except Exception as e:
                print(f"方法2失败: {e}")
                success = False

        if not success:
            raise APIError("所有下载方法都失败了，可能是夸克网盘的反爬虫机制")

        return save_path

    def download_files(
        self,
        file_ids: List[str],
        save_dir: str = "downloads",
        chunk_size: int = 8192,
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
        """
        批量下载文件

        Args:
            file_ids: 文件ID列表
            save_dir: 保存目录
            chunk_size: 下载块大小
            progress_callback: 进度回调函数 (current_file, total_files, file_progress)

        Returns:
            下载的文件路径列表
        """

        os.makedirs(save_dir, exist_ok=True)
        downloaded_files = []

        for i, file_id in enumerate(file_ids, 1):
            try:
                def file_progress(downloaded, total):
                    if progress_callback:
                        progress_callback(i, len(file_ids), downloaded, total)

                file_path = self.download_file(
                    file_id,
                    save_dir,
                    chunk_size,
                    file_progress
                )
                downloaded_files.append(file_path)

            except Exception as e:
                print(f"下载文件 {file_id} 失败: {e}")
                continue

        return downloaded_files

if __name__ == "__main__":
    import sys
    from pathlib import Path
    import json
    
    # 添加项目根目录到路径，支持直接运行
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # 重新导入以使用正确的路径
    from quark_client.core.api_client import QuarkAPIClient
    from quark_client import create_client
    
    # 测试代码
    print("=" * 50)
    print("文件下载服务测试")
    print("=" * 50)
    
    cookies = load_quark_cookie_string()
    if cookies:
        print("\n从 backend/config/quark_cookies.json 读取 cookies...")
        print("✅ Cookies 读取成功")
    
    if not cookies:
        print("\n❌ 未找到有效的 cookies")
        print("\n请先登录:")
        print("  1. 启动后端服务: cd backend && uvicorn app.main:app --reload")
        print("  2. 讨问 http://localhost:8000 进行登录")
        print("  3. 登录成功后再运行此测试")
        sys.exit(1)
    
    # 创建客户端
    try:
        client = create_client(cookies=cookies, auto_login=False)

        download = FileDownloadService(None)
        
        # 测试获取下载链接
        file_id = input("\n请输入要测试的文件ID (直接回车使用默认): ").strip()
        if not file_id:
            file_id = "35acdde9f25747bdbae3e5cac4154a62"
        
        print(f"\n获取文件 {file_id} 的下载链接...")
        url = download.get_download_url(file_id)
        print(f"✅ 下载链接: {url}")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
