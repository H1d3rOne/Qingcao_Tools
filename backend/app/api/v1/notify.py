"""
消息推送相关 API
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional

from app.modules.base.schemas import ApiResponse
from app.core.config import settings

router = APIRouter(prefix="/notify", tags=["消息推送"])


class WebhookConfig(BaseModel):
    """Webhook配置"""
    enabled: bool = Field(False, description="是否启用")
    webhook_url: Optional[str] = Field(None, description="Webhook URL")


class NotifyConfig(BaseModel):
    """消息推送配置"""
    wecom: WebhookConfig = Field(default_factory=WebhookConfig, description="企业微信")
    dingtalk: WebhookConfig = Field(default_factory=WebhookConfig, description="钉钉")
    feishu: WebhookConfig = Field(default_factory=WebhookConfig, description="飞书")


class UpdateWebhookRequest(BaseModel):
    """更新Webhook请求"""
    webhook_url: str = Field(..., description="Webhook URL")
    enabled: bool = Field(True, description="是否启用")


class TestNotifyRequest(BaseModel):
    """测试通知请求"""
    message: str = Field("测试消息", description="测试消息内容")


# 存储配置（实际项目中应该存数据库）
_notify_config = NotifyConfig()


@router.get("/config", response_model=ApiResponse[NotifyConfig])
async def get_notify_config():
    """获取消息推送配置"""
    return ApiResponse(data=_notify_config)


@router.post("/config/wecom", response_model=ApiResponse)
async def update_wecom_config(request: UpdateWebhookRequest):
    """更新企业微信配置"""
    _notify_config.wecom.enabled = request.enabled
    _notify_config.wecom.webhook_url = request.webhook_url
    return ApiResponse(message="企业微信配置更新成功")


@router.post("/config/dingtalk", response_model=ApiResponse)
async def update_dingtalk_config(request: UpdateWebhookRequest):
    """更新钉钉配置"""
    _notify_config.dingtalk.enabled = request.enabled
    _notify_config.dingtalk.webhook_url = request.webhook_url
    return ApiResponse(message="钉钉配置更新成功")


@router.post("/config/feishu", response_model=ApiResponse)
async def update_feishu_config(request: UpdateWebhookRequest):
    """更新飞书配置"""
    _notify_config.feishu.enabled = request.enabled
    _notify_config.feishu.webhook_url = request.webhook_url
    return ApiResponse(message="飞书配置更新成功")


@router.post("/test/wecom", response_model=ApiResponse)
async def test_wecom_notify(request: TestNotifyRequest):
    """测试企业微信通知"""
    if not _notify_config.wecom.webhook_url:
        return ApiResponse(success=False, error="未配置企业微信Webhook")
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                _notify_config.wecom.webhook_url,
                json={
                    "msgtype": "text",
                    "text": {
                        "content": f"【青草工具箱】\n{request.message}"
                    }
                }
            )
            if response.status_code == 200:
                return ApiResponse(message="企业微信通知发送成功")
            return ApiResponse(success=False, error=f"发送失败: {response.text}")
    except Exception as e:
        return ApiResponse(success=False, error=f"发送失败: {str(e)}")


@router.post("/test/dingtalk", response_model=ApiResponse)
async def test_dingtalk_notify(request: TestNotifyRequest):
    """测试钉钉通知"""
    if not _notify_config.dingtalk.webhook_url:
        return ApiResponse(success=False, error="未配置钉钉Webhook")
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                _notify_config.dingtalk.webhook_url,
                json={
                    "msgtype": "text",
                    "text": {
                        "content": f"【青草工具箱】\n{request.message}"
                    }
                }
            )
            if response.status_code == 200:
                return ApiResponse(message="钉钉通知发送成功")
            return ApiResponse(success=False, error=f"发送失败: {response.text}")
    except Exception as e:
        return ApiResponse(success=False, error=f"发送失败: {str(e)}")


@router.post("/test/feishu", response_model=ApiResponse)
async def test_feishu_notify(request: TestNotifyRequest):
    """测试飞书通知"""
    if not _notify_config.feishu.webhook_url:
        return ApiResponse(success=False, error="未配置飞书Webhook")
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                _notify_config.feishu.webhook_url,
                json={
                    "msg_type": "text",
                    "content": {
                        "text": f"【青草工具箱】\n{request.message}"
                    }
                }
            )
            if response.status_code == 200:
                return ApiResponse(message="飞书通知发送成功")
            return ApiResponse(success=False, error=f"发送失败: {response.text}")
    except Exception as e:
        return ApiResponse(success=False, error=f"发送失败: {str(e)}")
