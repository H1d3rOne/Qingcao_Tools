"""
基础响应模式
"""
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional, List
from datetime import datetime

T = TypeVar("T")


class ResponseBase(BaseModel):
    """基础响应"""
    success: bool = True
    message: Optional[str] = None
    error: Optional[str] = None


class ApiResponse(ResponseBase, Generic[T]):
    """通用API响应"""
    data: Optional[T] = None


class PagedResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: List[T]
    total: int
    page: int
    page_size: int
    has_more: bool


class EmptyResponse(ResponseBase):
    """空数据响应"""
    pass
