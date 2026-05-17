"""
自定义异常类
"""
from fastapi import HTTPException, status


class AppException(HTTPException):
    """应用基础异常"""
    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail: str = "请求错误",
        headers: dict = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class NotFoundException(AppException):
    """资源不存在异常"""
    def __init__(self, detail: str = "资源不存在"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class UnauthorizedException(AppException):
    """未授权异常"""
    def __init__(self, detail: str = "未授权访问"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class ForbiddenException(AppException):
    """禁止访问异常"""
    def __init__(self, detail: str = "禁止访问"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ValidationException(AppException):
    """验证错误异常"""
    def __init__(self, detail: str = "数据验证失败"):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


class SpiderException(AppException):
    """爬虫异常"""
    def __init__(self, detail: str = "爬虫请求失败"):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


class CookieExpiredException(AppException):
    """Cookie 过期异常"""
    def __init__(self, detail: str = "Cookie 已过期，请重新配置"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
