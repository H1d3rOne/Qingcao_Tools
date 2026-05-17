from pydantic import BaseModel, Field
from typing import Optional, List, Any


class FileListRequest(BaseModel):
    """文件列表请求"""
    folder_id: str = Field(default="0", description="文件夹 ID")
    page: int = Field(default=1, ge=1, description="页码")
    size: int = Field(default=50, ge=1, le=200, description="每页数量")


class FileListResponse(BaseModel):
    """文件列表响应"""
    success: bool
    data: Optional[dict] = None
    message: Optional[str] = None


class CreateFolderRequest(BaseModel):
    """创建文件夹请求"""
    folder_name: str = Field(..., description="文件夹名称")
    parent_id: str = Field(default="0", description="父文件夹 ID")


class DeleteFilesRequest(BaseModel):
    """删除文件请求"""
    file_ids: List[str] = Field(..., description="文件 ID 列表")


class RenameFileRequest(BaseModel):
    """重命名文件请求"""
    file_id: str = Field(..., description="文件 ID")
    new_name: str = Field(..., description="新名称")


class MoveFilesRequest(BaseModel):
    """移动文件请求"""
    file_ids: List[str] = Field(..., description="文件 ID 列表")
    target_folder_id: str = Field(..., description="目标文件夹 ID")


class SearchFilesRequest(BaseModel):
    """搜索文件请求"""
    keyword: str = Field(..., description="搜索关键词")
    page: int = Field(default=1, ge=1, description="页码")
    size: int = Field(default=50, ge=1, le=200, description="每页数量")


class StorageInfoResponse(BaseModel):
    """存储信息响应"""
    success: bool
    data: Optional[dict] = None
    message: Optional[str] = None


class CreateShareRequest(BaseModel):
    """创建分享请求"""
    file_ids: List[str] = Field(..., description="文件 ID 列表")
    title: str = Field(default="", description="分享标题")
    expire_days: int = Field(default=0, description="过期天数，0表示永久")
    password: Optional[str] = Field(default=None, description="提取码")


class ShareResponse(BaseModel):
    """分享响应"""
    success: bool
    data: Optional[dict] = None
    message: Optional[str] = None


class GetFolderTreeRequest(BaseModel):
    """获取文件夹树请求"""
    folder_id: str = Field(default="0", description="文件夹 ID")
    max_depth: int = Field(default=3, description="最大深度")


class UploadLocalFileRequest(BaseModel):
    """本地路径上传请求"""
    local_path: str = Field(..., description="本地文件绝对路径")
    parent_folder_id: Optional[str] = Field(default=None, description="目标文件夹 ID")
    relative_path: Optional[str] = Field(default=None, description="相对路径，用于重建文件夹树")
