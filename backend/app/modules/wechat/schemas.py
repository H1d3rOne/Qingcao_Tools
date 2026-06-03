from typing import List, Optional

from pydantic import BaseModel, Field


class WechatVideoItem(BaseModel):
    id: str = Field(..., description="视频唯一标识")
    description: str = Field(default="", description="视频描述")
    url: str = Field(default="", description="视频下载地址")
    cover_url: str = Field(default="", description="视频封面")
    file_size: int = Field(default=0, description="文件大小（字节）")
    file_size_text: str = Field(default="0B", description="文件大小文本")
    duration: int = Field(default=0, description="视频时长")
    decode_key: str = Field(default="", description="视频解密 Key")
    created_at: float = Field(default=0, description="捕获时间戳")


class ListenerStatus(BaseModel):
    listening: bool = Field(default=False, description="是否正在监听")
    proxy_running: bool = Field(default=False, description="代理服务是否运行")
    local_server_running: bool = Field(default=False, description="本地服务是否运行")
    system_proxy_enabled: bool = Field(default=False, description="系统代理是否已开启")
    proxy_host: str = Field(default="127.0.0.1")
    proxy_port: int = Field(default=8090)
    local_server_port: int = Field(default=3122)
    video_count: int = Field(default=0)
    download_dir: str = Field(default="")
    last_error: Optional[str] = Field(default=None)


class WechatProxyConfig(BaseModel):
    proxy_host: str = Field(default="127.0.0.1", description="mitm 代理监听地址")
    proxy_port: int = Field(default=8090, ge=1, le=65535, description="mitm 代理端口")
    local_server_host: str = Field(default="127.0.0.1", description="本地接收服务监听地址")
    local_server_port: int = Field(default=3122, ge=1, le=65535, description="本地接收服务端口")


class UpdateWechatProxyConfigRequest(BaseModel):
    proxy_port: int = Field(..., ge=1, le=65535, description="mitm 代理端口")
    local_server_port: int = Field(..., ge=1, le=65535, description="本地接收服务端口")


class WechatCertificateStatus(BaseModel):
    platform: str = Field(default="", description="当前系统")
    architecture: str = Field(default="", description="系统架构")
    supported: bool = Field(default=False, description="是否支持自动检测/安装")
    certificate_exists: bool = Field(default=False, description="mitmproxy CA 文件是否存在")
    trusted: bool = Field(default=False, description="证书是否已被系统信任")
    certificate_path: str = Field(default="", description="证书文件路径")
    message: str = Field(default="", description="状态说明")


class WechatVideoListResponse(BaseModel):
    items: List[WechatVideoItem] = Field(default_factory=list)
    total: int = Field(default=0)


class WechatDownloadTaskItem(BaseModel):
    id: str = Field(..., description="任务唯一标识")
    video_id: str = Field(..., description="视频唯一标识")
    description: str = Field(default="", description="视频描述")
    cover_url: str = Field(default="", description="视频封面")
    url: str = Field(default="", description="视频预览地址")
    file_size: int = Field(default=0, description="文件大小（字节）")
    file_size_text: str = Field(default="0B", description="文件大小文本")
    duration: int = Field(default=0, description="视频时长")
    status: str = Field(default="pending", description="任务状态")
    progress: int = Field(default=0, description="下载进度百分比")
    downloaded_size: int = Field(default=0, description="已下载大小（字节）")
    downloaded_size_text: str = Field(default="0B", description="已下载大小文本")
    raw_file: str = Field(default="", description="原始视频文件路径")
    decoded_file: str = Field(default="", description="解密视频文件路径")
    error: Optional[str] = Field(default=None, description="错误信息")
    created_at: float = Field(default=0, description="任务创建时间")
    updated_at: float = Field(default=0, description="任务更新时间")


class WechatDownloadTaskListResponse(BaseModel):
    items: List[WechatDownloadTaskItem] = Field(default_factory=list)
    total: int = Field(default=0)


class DownloadWechatVideoRequest(BaseModel):
    video_id: str = Field(..., description="视频唯一标识")


class QueueWechatDownloadRequest(BaseModel):
    video_id: str = Field(..., description="视频唯一标识")


class UpdateWechatDownloadDirRequest(BaseModel):
    path: str = Field(..., description="下载目录")


class ClearWechatDownloadTasksRequest(BaseModel):
    statuses: Optional[List[str]] = Field(default=None, description="待清空的任务状态列表")
