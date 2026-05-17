import base64
import io
import logging
import json
import os
import posixpath
import time

import qrcode
import qrcode.image.svg
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings as host_settings
from app.modules.quark.core.utils import (
    check_rpc_connection,
    get_default_download_path,
    send_to_rpc,
)
from quark_client.config import get_config_dir
from quark_client.cookie_store import (
    clear_quark_cookie_storage,
    load_quark_cookie_payload,
    load_quark_cookie_string,
    save_quark_cookie_string,
)

try:
    from quark_client import QuarkClient, create_client
    from quark_client.auth.api_login import APILogin
    QUARK_CLIENT_AVAILABLE = True
except ImportError as e:
    print(f"Warning: quark_client not available: {e}")
    QUARK_CLIENT_AVAILABLE = False
    QuarkClient = None
    create_client = None
    APILogin = None


class QuarkService:
    """夸克网盘服务管理"""
    
    DEFAULT_UPLOAD_FOLDER_NAME = "夸克上传文件"
    DEFAULT_SHARE_FOLDER_NAME = "来自：分享"
    
    _instance: Optional['QuarkService'] = None
    _client: Optional[Any] = None
    _is_logged_in: bool = False
    _api_login: Optional[Any] = None  # API登录管理器
    _current_qr_token: Optional[str] = None  # 当前二维码token
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._logger = logging.getLogger(__name__)
            # 初始化配置目录
            cls._instance._config_dir = get_config_dir()
            cls._instance._config_dir.mkdir(parents=True, exist_ok=True)
        return cls._instance
    
    @property
    def config_dir(self):
        """获取配置目录"""
        return self._config_dir
    
    @property
    def logger(self):
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(__name__)
        return self._logger
    
    def get_client(self) -> Optional[Any]:
        """获取 QuarkClient 实例"""
        return self._client
    
    def init_client(self, cookies: Optional[str] = None, auto_login: bool = True) -> Any:
        """初始化 QuarkClient"""
        if create_client:
            self._client = create_client(cookies=cookies, auto_login=auto_login)
        return self._client
    
    def _build_qrcode_data_url(self, content: str) -> Optional[str]:
        """生成二维码图片 Data URL，供前端直接展示"""
        try:
            image = qrcode.make(content, image_factory=qrcode.image.svg.SvgImage)
            buffer = io.BytesIO()
            image.save(buffer)
            encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return f"data:image/svg+xml;base64,{encoded}"
        except Exception as exc:
            self.logger.warning(f"生成二维码图片失败: {exc}")
            return None

    def get_qrcode(self) -> Dict[str, Any]:
        """获取登录二维码（非阻塞）"""
        try:
            if not QUARK_CLIENT_AVAILABLE:
                return {
                    "success": False,
                    "message": "quark_client 模块未安装，请检查依赖"
                }
            
            # 使用APILogin获取二维码
            if self._api_login is None:
                self._api_login = APILogin(timeout=300)
            
            qr_token, qr_url = self._api_login.get_qr_code()
            self._current_qr_token = qr_token
            qrcode_image = self._build_qrcode_data_url(qr_url)
            
            return {
                "success": True,
                "message": "二维码已生成，请使用夸克APP扫码",
                "qrcode_url": qr_url,
                "qrcode_token": qr_token,
                "qrcode_image": qrcode_image
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"获取二维码失败: {str(e)}"
            }
    
    def check_login_status(self, qr_token: str) -> Dict[str, Any]:
        """检查登录状态"""
        try:
            if not QUARK_CLIENT_AVAILABLE:
                return {
                    "success": False,
                    "message": "quark_client 模块未安装"
                }
            
            if self._api_login is None:
                return {
                    "success": False,
                    "message": "请先获取二维码"
                }
            
            # 检查登录状态
            result = self._api_login.check_login_status(qr_token)
            
            if result is not None:
                # 检查是否登录成功
                if self._api_login._is_login_success(result):
                    # 登录成功，保存登录结果并获取cookies
                    self._api_login._save_login_result(result)
                    
                    cookie_string = self._api_login.extract_quark_cookie_string()
                    self._is_logged_in = True
                    
                    self.logger.info(
                        f"登录成功，获取到 {len(cookie_string.split('; ')) if cookie_string else 0} 个 cookies"
                    )
                    
                    # 保存 cookies 到文件
                    self._save_cookies_to_file(cookie_string)
                    
                    # 使用获取到的cookies初始化QuarkClient
                    if create_client and cookie_string:
                        try:
                            self._client = create_client(cookies=cookie_string, auto_login=False)
                            self.logger.info(f"QuarkClient 初始化成功，client={self._client is not None}")
                        except Exception as e:
                            self.logger.error(f"QuarkClient 初始化失败: {e}")
                    else:
                        self.logger.warning(f"无法初始化 QuarkClient: create_client={create_client is not None}, cookie_string={bool(cookie_string)}")
                    
                    return {
                        "success": True,
                        "message": "登录成功",
                        "is_logged_in": True,
                        "login_token": cookie_string
                    }
                elif self._api_login._is_login_failed(result):
                    self.logger.info(f"登录失败: {result}")
                    return {
                        "success": False,
                        "message": "二维码已过期或登录失败，请重新获取",
                        "is_logged_in": False
                    }
                else:
                    self.logger.debug(f"登录状态未知: {result}")
            
            # 还在等待扫码
            return {
                "success": True,
                "message": "等待扫码...",
                "is_logged_in": False
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"检查登录状态失败: {str(e)}",
                "is_logged_in": False
            }
    
    def login(self, method: str = "api", cookies: Optional[str] = None) -> Dict[str, Any]:
        """执行登录"""
        try:
            if not QUARK_CLIENT_AVAILABLE:
                return {
                    "success": False,
                    "message": "quark_client 模块未安装，请检查依赖"
                }
            
            if self._client is None and create_client:
                self.init_client(cookies=cookies, auto_login=False)
            
            if method == "simple" and cookies:
                # 验证 Cookie 有效性
                if not self._validate_cookies(cookies):
                    return {
                        "success": False,
                        "message": "Cookie 格式无效，请检查是否包含必要的字段"
                    }
                
                if self._client:
                    # 设置 cookies 到 API 客户端
                    self._client.api_client.cookies = cookies
                    
                    # 验证 Cookie 是否能正常访问
                    if not self._verify_cookie_validity():
                        return {
                            "success": False,
                            "message": "Cookie 已失效，请重新获取"
                        }
                    
                    # 保存 cookies 到文件
                    self._save_cookies_to_file(cookies)
                    
                    self._is_logged_in = True
                    
                return {
                    "success": True,
                    "message": "Cookie 登录成功",
                    "cookies": cookies
                }
            elif self._client:
                result = self._client.login(method=method)
                self._is_logged_in = True
                return {
                    "success": True,
                    "message": "登录成功",
                    "cookies": result
                }
            else:
                return {
                    "success": False,
                    "message": "QuarkClient 未正确初始化"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"登录失败: {str(e)}"
            }
    
    def _validate_cookies(self, cookies: str) -> bool:
        """验证 Cookie 格式是否有效"""
        if not cookies or not cookies.strip():
            return False
        
        # 检查是否包含必要的 Cookie 字段
        required_cookies = ['__pus', '__kps', '__uid']
        cookies_lower = cookies.lower()
        
        for required in required_cookies:
            if required.lower() not in cookies_lower:
                self.logger.warning(f"Cookie 缺少必要字段: {required}")
                return False
        
        return True
    
    def _verify_cookie_validity(self) -> bool:
        """验证 Cookie 是否能有效访问夸克网盘"""
        try:
            if self._client is None:
                return False
            
            # 尝试获取用户信息来验证 Cookie
            user_info = self._client.get_user_info()
            if user_info and (user_info.get('nickname') or user_info.get('uid')):
                self.logger.info("Cookie 验证成功")
                return True
            
            return False
        except Exception as e:
            self.logger.error(f"验证 Cookie 失败: {e}")
            return False
    
    def load_saved_cookies(self) -> Optional[str]:
        """加载已保存的 Cookies"""
        try:
            cookie_string = load_quark_cookie_string(config_dir=self.config_dir)
            if not cookie_string:
                return None

            data = load_quark_cookie_payload(config_dir=self.config_dir) or {}

            timestamp = data.get('timestamp', 0)
            if time.time() - timestamp > 7 * 24 * 3600:
                self.logger.info("已保存的 Cookie 已过期")
                return None
            
            return cookie_string
            
        except Exception as e:
            self.logger.error(f"加载 Cookie 失败: {e}")
            return None
    
    def try_auto_login(self) -> Dict[str, Any]:
        """尝试使用已保存的 Cookie 自动登录"""
        try:
            if not QUARK_CLIENT_AVAILABLE:
                return {
                    "success": False,
                    "message": "quark_client 模块未安装"
                }
            
            saved_cookies = self.load_saved_cookies()
            
            if not saved_cookies:
                host_cookie = (getattr(host_settings, 'QUARK_COOKIES', '') or '').strip()
                if host_cookie:
                    saved_cookies = host_cookie
                else:
                    return {
                        "success": False,
                        "message": "没有已保存的登录信息"
                    }
            
            # 尝试使用保存的 Cookie 登录
            return self.login(method="simple", cookies=saved_cookies)
            
        except Exception as e:
            return {
                "success": False,
                "message": f"自动登录失败: {str(e)}"
            }
    
    def _save_cookies_to_file(self, cookies: str) -> None:
        """保存 cookies 到文件"""
        try:
            save_quark_cookie_string(
                cookies,
                config_dir=self.config_dir,
                source='web_login',
            )
            self.logger.info(f"Cookies 已保存到: {self.config_dir / 'quark_cookies.json'}")
            
        except Exception as e:
            self.logger.error(f"保存 cookies 失败: {e}")
    
    def is_logged_in(self) -> bool:
        """检查登录状态"""
        if self._client is None:
            self._is_logged_in = False
            return False
        try:
            if hasattr(self._client, "is_logged_in") and self._client.is_logged_in():
                self._is_logged_in = True
                return True

            if self._is_logged_in:
                return True

            user_info = self._client.get_user_info()
            is_valid = bool(user_info and (user_info.get('nickname') or user_info.get('uid')))
            self._is_logged_in = is_valid
            return is_valid
        except Exception:
            self._is_logged_in = False
            return False
    
    def logout(self) -> Dict[str, Any]:
        """登出"""
        try:
            if self._client:
                self._client.logout()
            else:
                clear_quark_cookie_storage(config_dir=self.config_dir)
            self._client = None
            self._is_logged_in = False
            self._api_login = None
            self._current_qr_token = None
            return {
                "success": True,
                "message": "登出成功"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"登出失败: {str(e)}"
            }
    
    def list_files(self, folder_id: str = "0", page: int = 1, size: int = 50) -> Dict[str, Any]:
        """获取文件列表"""
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if not self._is_logged_in:
            return {"success": False, "message": "未登录，请先扫码登录"}
        
        if self._client is None:
            return {"success": False, "message": "客户端未初始化，请重新登录"}
        
        try:
            result = self._client.list_files(folder_id=folder_id, page=page, size=size)
            self.logger.info(f"后端获取文件夹fid:{folder_id}")
            self.logger.info(f"后端获取文件列表fid::{result}")
            return {"success": True, "data": result}
        except Exception as e:
            self.logger.error(f"获取文件列表失败: {e}")
            return {"success": False, "message": str(e)}
    
    def create_folder(self, folder_name: str, parent_id: str = "0") -> Dict[str, Any]:
        """创建文件夹"""
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        try:
            result = self._client.create_folder(folder_name, parent_id)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def delete_files(self, file_ids: List[str]) -> Dict[str, Any]:
        """删除文件"""
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        try:
            result = self._client.delete_files(file_ids)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def rename_file(self, file_id: str, new_name: str) -> Dict[str, Any]:
        """重命名文件"""
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        try:
            result = self._client.rename_file(file_id, new_name)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def move_files(self, file_ids: List[str], target_folder_id: str) -> Dict[str, Any]:
        """移动文件"""
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        try:
            result = self._client.move_files(file_ids, target_folder_id)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def search_files(self, keyword: str, page: int = 1, size: int = 50) -> Dict[str, Any]:
        """搜索文件"""
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        try:
            result = self._client.search_files(keyword, page=page, size=size)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def get_storage_info(self) -> Dict[str, Any]:
        """获取存储信息"""
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        try:
            # 使用 UserInfoService 获取用户信息（包含存储空间）
            result = self._client.get_user_info()
            
            total = result.get('total_capacity', 0)
            used = result.get('use_capacity', 0)
            
            return {
                "success": True,
                "data": {
                    "total": total,
                    "used": used
                }
            }
        except Exception as e:
            self.logger.error(f"获取存储信息失败: {e}")
            return {"success": False, "message": str(e)}
    
    def get_user_info(self) -> Dict[str, Any]:
        """获取用户信息"""
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        try:
            # 使用 UserInfoService 获取用户信息
            result = self._client.get_user_info()
            
            return {
                "success": True,
                "data": {
                    "nickname": result.get('nickname', ''),
                    "avatar": result.get('avatar', ''),
                    "total_capacity": result.get('total_capacity', 0),
                    "use_capacity": result.get('use_capacity', 0),
                }
            }
        except Exception as e:
            self.logger.error(f"获取用户信息失败: {e}")
            return {"success": False, "message": str(e)}
    
    def upload_file(self, file_content: bytes, file_name: str, parent_folder_id: str = None, progress_callback=None) -> Dict[str, Any]:
        """上传文件到夸克网盘
        
        Args:
            file_content: 文件内容（字节）
            file_name: 文件名
            parent_folder_id: 父文件夹ID（可选，默认为"夸克上传文件"文件夹）
            progress_callback: 进度回调函数
            
        Returns:
            上传结果
        """
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        try:
            target_folder_id = self._resolve_upload_target_folder(parent_folder_id)
            
            # 保存文件到临时目录
            import tempfile
            import os
            
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, file_name)
            
            with open(temp_file_path, 'wb') as f:
                f.write(file_content)
            
            self.logger.info(f"临时文件保存到: {temp_file_path}")
            
            # 调用 quark_client 的上传方法
            def progress_wrapper(progress, message):
                if progress_callback:
                    progress_callback(progress, message)
                self.logger.info(f"上传进度: {progress}% - {message}")
            
            result = self._client.upload_file(
                file_path=temp_file_path,
                parent_folder_id=target_folder_id,
                progress_callback=progress_wrapper if progress_callback else None
            )
            
            # 删除临时文件
            try:
                os.remove(temp_file_path)
            except:
                pass
            
            self.logger.info(f"上传结果: {result}")
            
            if result.get('status') == 'success':
                return {
                    "success": True,
                    "message": f"文件 {file_name} 上传成功",
                    "data": {
                        "file_name": file_name,
                        "task_id": result.get('task_id'),
                        "file_size": result.get('file_size'),
                        "md5": result.get('md5')
                    }
                }
            else:
                return {"success": False, "message": f"上传失败: {result}"}
                
        except Exception as e:
            self.logger.error(f"上传文件失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {"success": False, "message": str(e)}

    def upload_file_with_path(
        self,
        file_content: bytes,
        file_name: str,
        parent_folder_id: str = None,
        relative_path: Optional[str] = None,
        progress_callback=None
    ) -> Dict[str, Any]:
        """按相对路径重建远程目录树并上传文件"""
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}

        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}

        try:
            target_folder_id = self._resolve_upload_target_folder(parent_folder_id)
            final_file_name = file_name

            normalized_relative_path = self._normalize_relative_path(relative_path)
            if normalized_relative_path:
                relative_dir = posixpath.dirname(normalized_relative_path)
                relative_basename = posixpath.basename(normalized_relative_path)

                if relative_basename:
                    final_file_name = relative_basename

                if relative_dir and relative_dir != ".":
                    target_folder_id = self._ensure_remote_folder_path(relative_dir, target_folder_id)

            return self.upload_file(
                file_content=file_content,
                file_name=final_file_name,
                parent_folder_id=target_folder_id,
                progress_callback=progress_callback
            )
        except Exception as e:
            self.logger.error(f"按路径上传文件失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {"success": False, "message": str(e)}

    def upload_local_file(
        self,
        local_path: str,
        parent_folder_id: str = None,
        relative_path: Optional[str] = None,
        progress_callback=None
    ) -> Dict[str, Any]:
        """直接从本机文件路径上传，绕过浏览器文件流读取"""
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}

        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}

        try:
            path_obj = Path(local_path)
            if not path_obj.exists():
                return {"success": False, "message": f"本地文件不存在: {local_path}"}
            if not path_obj.is_file():
                return {"success": False, "message": f"本地路径不是文件: {local_path}"}

            target_folder_id = self._resolve_upload_target_folder(parent_folder_id)
            normalized_relative_path = self._normalize_relative_path(relative_path)
            if normalized_relative_path:
                relative_dir = posixpath.dirname(normalized_relative_path)
                if relative_dir and relative_dir != ".":
                    target_folder_id = self._ensure_remote_folder_path(relative_dir, target_folder_id)

            result = self._client.upload_file(
                file_path=str(path_obj),
                parent_folder_id=target_folder_id,
                progress_callback=progress_callback
            )

            if result.get("status") == "success":
                return {
                    "success": True,
                    "message": f"文件 {path_obj.name} 上传成功",
                    "data": {
                        "file_name": path_obj.name,
                        "task_id": result.get("task_id"),
                        "file_size": result.get("file_size"),
                        "md5": result.get("md5")
                    }
                }

            return {"success": False, "message": f"上传失败: {result}"}
        except Exception as e:
            self.logger.error(f"本地路径上传文件失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {"success": False, "message": str(e)}

    def _normalize_relative_path(self, relative_path: Optional[str]) -> str:
        """标准化相对路径，剔除无效和危险片段"""
        if not relative_path:
            return ""

        raw_parts = relative_path.replace("\\", "/").split("/")
        clean_parts = [part.strip() for part in raw_parts if part and part not in (".", "..")]
        return "/".join(clean_parts)

    def _ensure_remote_folder_path(self, relative_dir: str, base_parent_id: str) -> str:
        """根据相对目录逐级查找或创建远程文件夹"""
        current_parent_id = base_parent_id or "0"
        for folder_name in [part for part in relative_dir.split("/") if part]:
            current_parent_id = self._get_or_create_folder(folder_name, current_parent_id)
        return current_parent_id

    def _resolve_upload_target_folder(self, parent_folder_id: Optional[str]) -> str:
        """解析上传目标目录；未指定时默认使用根目录下的默认上传文件夹"""
        if parent_folder_id:
            return parent_folder_id
        return self._get_or_create_folder(self.DEFAULT_UPLOAD_FOLDER_NAME, "0")

    def _resolve_share_target_folder(self, target_folder_id: Optional[str]) -> str:
        """解析分享转存目标目录；未指定时默认使用根目录下的分享文件夹"""
        if target_folder_id:
            self.logger.info(f"使用指定的目标文件夹: {target_folder_id}")
            return target_folder_id
        return self._get_or_create_folder(self.DEFAULT_SHARE_FOLDER_NAME, "0")

    def _extract_file_list(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从不同响应结构中提取 list_files 的列表数据"""
        files_data = result.get('data', {})
        if isinstance(files_data, dict) and 'data' in files_data:
            nested_data = files_data.get('data', {})
            if isinstance(nested_data, dict):
                return nested_data.get('list', []) or []
            return []
        if isinstance(files_data, dict):
            return files_data.get('list', []) or []
        return []

    def _list_all_folder_items(self, folder_id: str, page_size: int = 200) -> List[Dict[str, Any]]:
        """拉取目录下全部分页项目，避免只看第一页导致漏目录"""
        all_items: List[Dict[str, Any]] = []
        page = 1

        while True:
            result = self._client.list_files(folder_id=folder_id, page=page, size=page_size)
            current_items = self._extract_file_list(result)
            if not current_items:
                break

            all_items.extend(current_items)

            metadata = result.get('metadata', {}) if isinstance(result, dict) else {}
            total = metadata.get('_total')
            if isinstance(total, int) and total > 0 and len(all_items) >= total:
                break

            if len(current_items) < page_size:
                break

            page += 1

        return all_items
    
    def _get_or_create_folder(self, folder_name: str, parent_id: str = "0") -> str:
        """获取或创建文件夹，返回文件夹ID"""
        files_list = self._list_all_folder_items(parent_id)
        
        # 查找文件夹
        for item in files_list:
            if item.get('file_type') == 0 and item.get('file_name') == folder_name:
                self.logger.info(f"找到现有文件夹: {folder_name} ({item.get('fid')})")
                return item.get('fid')
        
        # 没找到，创建文件夹
        create_result = self._client.create_folder(folder_name, parent_id)
        folder_id = create_result.get('data', {}).get('fid')
        
        if folder_id:
            self.logger.info(f"创建文件夹: {folder_name} ({folder_id})")
        else:
            self.logger.warning(f"创建文件夹失败，使用根目录")
            folder_id = parent_id
        
        return folder_id
    
    def get_download_url(self, file_id: str, file_name: str = None, save_path: str = None) -> Dict[str, Any]:
        """获取下载链接
        
        Args:
            file_id: 文件ID
            file_name: 文件名（可选，用于RPC下载时的文件名）
            save_path: 保存路径，默认使用系统下载目录
        """
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}

        task_url = "https://drive-pc.quark.cn/1/clouddrive/file/download"
        cookies = self._client.api_client.cookies
        headers: Dict[str, str] = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160 Electron/18.3.5.4-b478491100 Safari/537.36 Channel/pckk_other_ch",
            'origin': 'https://pan.quark.cn',
            'referer': 'https://pan.quark.cn/',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cookie': cookies,
         }
        params = {
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
        }
        data = {
            "fids": [file_id]
        }
        
        try:
            response = httpx.post(task_url, json=data, headers=headers, params=params, timeout=60)
            if response.status_code != 200:
                return {"success": False, "message": f"获取下载链接失败，状态码： {response.status_code}"}
            # url = self._client.get_download_url(file_id)
            json_data = response.json()
            data = json_data['data']
            fname = data[0]["file_name"]
            url = data[0]["download_url"]
            
                
            self.logger.info(f"获取下载链接成功: file_id={file_id}, file_name={file_name}")
            
            # 如果没有传入文件名，尝试从文件列表中获取
            if not file_name:
                # 尝试获取文件信息
                file_name = fname
            
            persisted_cookies = load_quark_cookie_string(config_dir=self.config_dir)
            if persisted_cookies:
                cookies = persisted_cookies
                self.logger.info(f"✅ Cookies 读取成功，长度: {len(cookies)}")
            else:
                self.logger.warning(f"Cookie 文件不存在: {self.config_dir / 'quark_cookies.json'}")
            
            # 检查 RPC 连接状态
            rpc_connected = check_rpc_connection()
            self.logger.info(f"RPC 连接状态: {rpc_connected}")
            
            if not rpc_connected:
                # RPC 未开启，返回下载链接供浏览器下载
                self.logger.info(f"RPC 未开启，使用浏览器下载: {file_name}")
                return {"success": True, "data": {"download_url": url, "file_name": file_name}}
            else:
                # RPC 已开启，发送到 Motrix 下载
                if save_path is None:
                    save_path = get_default_download_path()
                
                self.logger.info(f"RPC 已开启，发送到 Motrix 下载: file_name={file_name}, save_path={save_path}")
                
                send_to_rpc(file_name, url, save_path, cookies)
                return {"success": True, "message": f"已发送到 Motrix 下载: {file_name}", "data": {"file_name": file_name, "save_path": save_path}}
        except Exception as e:
            self.logger.error(f"获取下载链接失败: {e}")
            return {"success": False, "message": str(e)}
    
    def download_folder(self, folder_id: str, folder_name: str = None, save_path: str = None) -> Dict[str, Any]:
        """递归下载文件夹
        
        Args:
            folder_id: 文件夹ID
            folder_name: 文件夹名称
            save_path: 保存路径
            
        Returns:
            下载结果
        """
        import os
        
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        # 检查 RPC 连接状态
        rpc_connected = check_rpc_connection()
        
        if not rpc_connected:
            return {"success": False, "message": "文件夹下载需要开启 RPC 服务（Motrix）"}
        
        # 设置保存路径
        if save_path is None:
            save_path = get_default_download_path()
        
        # 获取文件夹名称
        if not folder_name:
            folder_name = folder_id
        
        # 创建文件夹路径
        folder_path = os.path.join(save_path, folder_name)
        
        self.logger.info(f"开始下载文件夹: {folder_name}, 路径: {folder_path}")
        
        # 统计下载结果
        download_stats = {
            "total_files": 0,
            "total_folders": 0,
            "success_files": 0,
            "failed_files": 0
        }
        
        def download_recursive(fid: str, current_path: str, depth: int = 0):
            """递归下载文件夹内容"""
            if depth > 50:  # 限制递归深度
                self.logger.warning(f"递归深度超过限制: {depth}")
                return
            
            indent = "  " * depth
            self.logger.info(f"{indent}扫描文件夹: {fid}")
            
            try:
                # 使用现有的 list_files 方法获取文件夹内容
                result = self.list_files(folder_id=fid, page=1, size=500)
                
                if not result.get("success"):
                    self.logger.error(f"{indent}获取文件列表失败: {result.get('message')}")
                    return
                
                # result 结构: {"success": True, "data": {"status": 200, "data": {"list": [...]}}}
                files_data = result.get('data', {})
                # 需要再取一层 data
                if isinstance(files_data, dict) and 'data' in files_data:
                    files_list = files_data.get('data', {}).get('list', [])
                else:
                    files_list = files_data.get('list', [])
                
                self.logger.info(f"{indent}找到 {len(files_list)} 个文件/文件夹")
                
                for item in files_list:
                    item_name = item.get('file_name', 'unknown')
                    item_type = item.get('file_type', 1)  # 0=文件夹, 1=文件
                    item_fid = item.get('fid')
                    
                    if item_type == 0:
                        # 子文件夹：创建目录并递归
                        download_stats["total_folders"] += 1
                        sub_folder_path = os.path.join(current_path, item_name)
                        self.logger.info(f"{indent}发现子文件夹: {item_name}")
                        
                        # 递归下载子文件夹
                        download_recursive(item_fid, sub_folder_path, depth + 1)
                    else:
                        # 文件：使用现有的 get_download_url 方法下载
                        download_stats["total_files"] += 1
                        
                        try:
                            self.logger.info(f"{indent}下载文件: {item_name}")
                            
                            # 调用现有的 get_download_url 方法，传递当前路径作为保存路径
                            download_result = self.get_download_url(
                                file_id=item_fid,
                                file_name=item_name,
                                save_path=current_path
                            )
                            
                            if download_result.get("success"):
                                download_stats["success_files"] += 1
                            else:
                                download_stats["failed_files"] += 1
                                self.logger.error(f"{indent}下载文件失败 {item_name}: {download_result.get('message')}")
                            
                            # 避免请求过快
                            time.sleep(0.1)
                            
                        except Exception as e:
                            self.logger.error(f"{indent}下载文件失败 {item_name}: {e}")
                            download_stats["failed_files"] += 1
                            
            except Exception as e:
                self.logger.error(f"{indent}扫描文件夹失败: {e}")
        
        # 开始递归下载
        download_recursive(folder_id, folder_path)
        
        result_message = f"文件夹下载任务已发送: {folder_name}\n"
        result_message += f"共扫描 {download_stats['total_folders']} 个子文件夹\n"
        result_message += f"共 {download_stats['total_files']} 个文件\n"
        result_message += f"成功发送 {download_stats['success_files']} 个下载任务\n"
        
        if download_stats['failed_files'] > 0:
            result_message += f"失败 {download_stats['failed_files']} 个文件"
        
        self.logger.info(result_message)
        
        return {
            "success": True,
            "message": result_message,
            "data": {
                "folder_name": folder_name,
                "save_path": folder_path,
                "stats": download_stats
            }
        }
    
    def get_folder_tree(self, folder_id: str = "0", max_depth: int = 3) -> Dict[str, Any]:
        """获取文件夹树"""
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        try:
            # 递归构建文件夹树
            def build_tree(fid: str, depth: int) -> list:
                if depth > max_depth:
                    return []
                
                try:
                    files_list = self._list_all_folder_items(fid)
                    
                    children = []
                    for f in files_list:
                        # file_type == 0 表示文件夹
                        if f.get('file_type') == 0:
                            node = {
                                "id": f.get('fid'),
                                "name": f.get('file_name'),
                                "children": build_tree(f.get('fid'), depth + 1)
                            }
                            children.append(node)
                    return children
                except Exception:
                    return []
            
            tree = [{
                "id": "0",
                "name": "根目录",
                "children": build_tree("0", 1)
            }]
            
            return {"success": True, "data": tree}
        except Exception as e:
            self.logger.error(f"获取文件夹树失败: {e}")
            return {"success": False, "message": str(e)}
    
    def create_share(self, file_ids: List[str], title: str = "", expire_days: int = 0, password: Optional[str] = None) -> Dict[str, Any]:
        """创建分享链接"""
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        try:
            result = self._client.create_share(file_ids, title=title, expire_days=expire_days, password=password)
            self.logger.info(f"创建分享结果: {result}")
            
            # 确保返回正确的数据格式
            if isinstance(result, dict):
                share_data = {
                    "share_url": result.get("share_url", ""),
                    "passcode": result.get("passcode", result.get("password", "")),
                    "share_id": result.get("pwd_id", result.get("share_id", ""))
                }
            else:
                share_data = {"share_url": str(result), "passcode": ""}
            
            return {"success": True, "data": share_data}
        except Exception as e:
            self.logger.error(f"创建分享失败: {e}")
            return {"success": False, "message": str(e)}
    
    def get_my_shares(self, page: int = 1, size: int = 50) -> Dict[str, Any]:
        """获取我的分享列表"""
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        try:
            result = self._client.get_my_shares(page=page, size=size)
            return {"success": True, "data": result}
        except Exception as e:
            self.logger.error(f"获取分享列表失败: {e}")
            return {"success": False, "message": str(e)}
    
    def delete_share(self, share_id: str) -> Dict[str, Any]:
        """删除分享"""
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        try:
            result = self._client.delete_share(share_id)
            return {"success": True, "data": result}
        except Exception as e:
            self.logger.error(f"删除分享失败: {e}")
            return {"success": False, "message": str(e)}
    
    def get_share_info(self, share_id: str, passcode: str = None, pdir_fid: str = "0", token: str = None) -> Dict[str, Any]:
        """获取分享链接信息
        
        Args:
            share_id: 分享ID
            passcode: 提取码
            pdir_fid: 父目录ID，根目录为"0"
            token: 访问令牌（浏览子目录时传入）
        """
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        try:
            # 如果没有传入token，先获取token
            if not token:
                token = self._client.shares.get_share_token(share_id, passcode)
            
            # 获取分享内容信息
            result = self._client.shares.get_share_info(share_id, token, pdir_fid)
            
            # 调试：打印API返回结果
            import json
            self.logger.info(f"[DEBUG] get_share_info API返回: {json.dumps(result.get('data', {}).get('list', [])[:2], ensure_ascii=False, indent=2)}")
            
            # 提取文件列表
            files = []
            total_size = 0
            if result and 'data' in result:
                file_list = result['data'].get('list', [])
                for item in file_list:
                    files.append({
                        "fid": item.get('fid', ''),
                        "file_name": item.get('file_name', ''),
                        "file_type": item.get('file_type', 1),  # 0=文件夹, 1=文件
                        "size": item.get('size', 0),
                        "pdir_fid": item.get('pdir_fid', pdir_fid),  # 父目录ID
                        "share_fid_token": item.get('share_fid_token', '')  # 必须返回用于转存
                    })
                    total_size += item.get('size', 0)
            
            return {
                "success": True,
                "data": {
                    "files": files,
                    "total_size": total_size,
                    "token": token,  # 保存token用于后续操作
                    "pdir_fid": pdir_fid  # 当前目录ID
                }
            }
        except Exception as e:
            self.logger.error(f"获取分享信息失败: {e}")
            return {"success": False, "message": str(e)}
    
    def transfer_share(self, share_id: str, passcode: str, file_ids: list, share_fid_tokens: list, target_folder_id: Optional[str], pdir_fid: str = "0", token: str = None) -> Dict[str, Any]:
        """转存分享文件到网盘
        
        Args:
            share_id: 分享ID
            passcode: 提取码
            file_ids: 文件ID列表
            share_fid_tokens: 文件对应的share_fid_token列表
            target_folder_id: 目标文件夹ID
            pdir_fid: 源文件夹ID
            token: 访问令牌（必须与share_fid_tokens配对）
        """
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        try:
            # 调试：打印接收到的参数
            import json
            self.logger.info(f"[DEBUG] transfer_share 接收参数: token={token}, share_fid_tokens={share_fid_tokens}")
            
            # 如果没有传入 token，才重新获取
            if not token:
                token = self._client.shares.get_share_token(share_id, passcode)
                self.logger.info(f"[DEBUG] 重新获取 token: {token}")
            
            resolved_target_folder_id = self._resolve_share_target_folder(target_folder_id)

            # 转存文件
            result = self._client.shares.save_shared_files(
                share_id=share_id,
                token=token,
                file_ids=file_ids,
                share_fid_tokens=share_fid_tokens,
                target_folder_id=resolved_target_folder_id,
                pdir_fid=pdir_fid,
                wait_for_completion=True
            )
            return {"success": True, "data": result}
        except Exception as e:
            self.logger.error(f"转存分享文件失败: {e}")
            return {"success": False, "message": str(e)}
    
    def download_share(self, share_id: str, passcode: str, file_ids: list, token: str = None, mode: str = "clean", target_folder_id: str = None) -> Dict[str, Any]:
        """下载分享文件（异步执行，立即返回）
        
        流程：
        1. 验证参数
        2. 启动后台任务执行下载
        3. 立即返回"任务已提交"
        
        Args:
            share_id: 分享ID
            passcode: 提取码
            file_ids: 文件/文件夹ID列表
            token: 访问令牌（可选）
            mode: 下载模式 - keep: 保存下载（保留在网盘）, clean: 无痕下载（下载后删除）
            target_folder_id: 目标文件夹ID（可选，默认使用"来自：分享"文件夹）
            
        Returns:
            下载结果
        """
        if not QUARK_CLIENT_AVAILABLE:
            return {"success": False, "message": "quark_client 模块未安装"}
        
        if self._client is None or not self._is_logged_in:
            return {"success": False, "message": "未登录"}
        
        # 检查 RPC 连接状态
        rpc_connected = check_rpc_connection()
        
        if not rpc_connected:
            return {"success": False, "message": "分享下载需要开启 RPC 服务（Motrix）"}
        
        if not file_ids:
            return {"success": False, "message": "请选择要下载的文件"}
        
        mode_text = "保存下载" if mode == "keep" else "无痕下载"
        self.logger.info(f"[DEBUG] download_share 任务提交: file_ids={file_ids}, mode={mode}")
        
        # 在后台线程中执行下载任务
        import threading
        
        def background_download():
            """后台执行下载任务"""
            try:
                self._execute_download_share(share_id, passcode, file_ids, token, mode, target_folder_id)
            except Exception as e:
                self.logger.error(f"后台下载任务失败: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
        
        # 启动后台线程
        thread = threading.Thread(target=background_download, daemon=True)
        thread.start()
        
        return {
            "success": True,
            "message": f"{mode_text}任务已提交，正在后台执行中...\n请查看 Motrix 下载进度"
        }
    
    def _execute_download_share(self, share_id: str, passcode: str, file_ids: list, token: str, mode: str, target_folder_id: str):
        """执行下载分享文件的实际逻辑（内部方法）"""
        try:
            # 获取分享token
            if not token:
                token = self._client.shares.get_share_token(share_id, passcode)

            dest_folder_id = self._resolve_share_target_folder(target_folder_id)
            
            if not dest_folder_id:
                self.logger.error("无法获取或创建分享文件夹")
                return
            
            # Step 1: 获取分享文件信息（支持子目录搜索）
            self.logger.info(f"[DEBUG] 获取分享文件信息...")
            
            def collect_file_info(pdir_fid: str = "0", depth: int = 0) -> dict:
                """递归收集所有文件信息"""
                if depth > 10:
                    return {}
                
                result = {}
                try:
                    share_result = self._client.shares.get_share_info(share_id, token, pdir_fid)
                    files = share_result.get('data', {}).get('list', [])
                    
                    for item in files:
                        fid = item.get('fid')
                        result[fid] = {
                            'share_fid_token': item.get('share_fid_token', ''),
                            'name': item.get('file_name', ''),
                            'type': item.get('file_type', 1),
                            'pdir_fid': pdir_fid
                        }
                        
                        if item.get('file_type') == 0:
                            sub_result = collect_file_info(fid, depth + 1)
                            result.update(sub_result)
                except Exception as e:
                    self.logger.error(f"收集文件信息失败: {e}")
                
                return result
            
            # 收集所有文件信息
            all_files_info = collect_file_info()
            self.logger.info(f"[DEBUG] 共收集到 {len(all_files_info)} 个文件/文件夹")
            
            # 收集要转存的文件信息
            transfer_file_ids = []
            transfer_fid_tokens = []
            transfer_pdir_fids = []
            
            for fid in file_ids:
                if fid in all_files_info:
                    info = all_files_info[fid]
                    transfer_file_ids.append(fid)
                    transfer_fid_tokens.append(info['share_fid_token'])
                    transfer_pdir_fids.append(info['pdir_fid'])
                    self.logger.info(f"[DEBUG] 将转存: {info['name']}")
                else:
                    self.logger.warning(f"[DEBUG] 文件 {fid} 不在分享列表中")
            
            if not transfer_file_ids:
                self.logger.error("未找到选中的文件")
                return
            
            # Step 2: 按 pdir_fid 分组转存
            files_by_pdir = {}
            for i, fid in enumerate(transfer_file_ids):
                pdir_fid = transfer_pdir_fids[i]
                info = all_files_info[fid]
                if pdir_fid not in files_by_pdir:
                    files_by_pdir[pdir_fid] = []
                files_by_pdir[pdir_fid].append((fid, transfer_fid_tokens[i], info['name'], info['type']))
            
            self.logger.info(f"[DEBUG] 文件分布在 {len(files_by_pdir)} 个目录中")
            
            # 逐目录转存
            for pdir_fid, files in files_by_pdir.items():
                fids = [f[0] for f in files]
                tokens = [f[1] for f in files]
                
                self.logger.info(f"[DEBUG] 转存目录 {pdir_fid} 中的 {len(fids)} 个文件...")
                
                transfer_result = self.transfer_share(
                    share_id=share_id,
                    passcode=passcode,
                    file_ids=fids,
                    share_fid_tokens=tokens,
                    target_folder_id=dest_folder_id,
                    pdir_fid=pdir_fid,
                    token=token
                )
                
                if transfer_result.get("success"):
                    self.logger.info(f"[DEBUG] 目录 {pdir_fid} 转存成功")
                else:
                    self.logger.error(f"[DEBUG] 转存失败: {transfer_result.get('message')}")
                
                time.sleep(0.5)
            
            # 等待转存完成
            time.sleep(1)
            
            # Step 3: 获取转存后的文件列表
            self.logger.info(f"[DEBUG] 获取转存后的文件列表...")
            saved_result = self._client.list_files(folder_id=dest_folder_id, page=1, size=100)
            saved_data = saved_result.get('data', {})
            if isinstance(saved_data, dict) and 'data' in saved_data:
                saved_files = saved_data.get('data', {}).get('list', [])
            else:
                saved_files = saved_data.get('list', [])
            
            self.logger.info(f"[DEBUG] 目标文件夹中有 {len(saved_files)} 个文件")
            
            # 找到刚转存的文件
            transferred_items = []
            saved_fids_to_delete = []
            
            for fid in transfer_file_ids:
                info = all_files_info[fid]
                for saved_file in saved_files:
                    if saved_file.get('file_name') == info['name']:
                        transferred_items.append({
                            'fid': saved_file.get('fid'),
                            'name': info['name'],
                            'type': info['type']
                        })
                        saved_fids_to_delete.append(saved_file.get('fid'))
                        self.logger.info(f"[DEBUG] 找到转存后的文件: {info['name']}")
                        break
            
            if not transferred_items:
                self.logger.error("转存成功但未找到转存后的文件")
                return
            
            # Step 4: 下载转存后的文件
            self.logger.info(f"[DEBUG] 开始下载 {len(transferred_items)} 个文件...")
            
            for item in transferred_items:
                if item['type'] == 0:
                    # 文件夹
                    self.logger.info(f"[DEBUG] 下载文件夹: {item['name']}")
                    self.download_folder(folder_id=item['fid'], folder_name=item['name'])
                else:
                    # 单个文件
                    self.logger.info(f"[DEBUG] 下载文件: {item['name']}")
                    self.get_download_url(file_id=item['fid'], file_name=item['name'])
            
            # Step 5: 无痕模式删除
            if mode == 'clean' and saved_fids_to_delete:
                # 等待下载任务发送完成
                time.sleep(2)
                self.logger.info(f"[DEBUG] 无痕模式：删除 {len(saved_fids_to_delete)} 个转存的文件/文件夹")
                try:
                    self._client.delete_files(saved_fids_to_delete)
                except Exception as e:
                    self.logger.warning(f"删除转存文件失败: {e}")
            
            mode_text = "保存下载" if mode == "keep" else "无痕下载"
            self.logger.info(f"[DEBUG] {mode_text}任务执行完成")
            
        except Exception as e:
            self.logger.error(f"执行下载任务失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        except Exception as e:
            self.logger.error(f"下载分享文件失败: {e}")
            return {"success": False, "message": str(e)}


# 全局服务实例
quark_service = QuarkService()
