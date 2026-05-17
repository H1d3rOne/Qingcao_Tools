"""
直播相关 Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class StreamUrl(BaseModel):
    """视频流地址"""
    rtmp: Optional[str] = Field(None, description="RTMP 拉流地址")
    hls: Optional[str] = Field(None, description="HLS 拉流地址")
    flv: Optional[str] = Field(None, description="FLV 拉流地址")


class LiveOwner(BaseModel):
    """主播信息"""
    nickname: Optional[str] = Field(None, description="主播昵称")
    avatar: Optional[str] = Field(None, description="主播头像")
    sec_uid: Optional[str] = Field(None, description="主播sec_uid")
    uid: Optional[str] = Field(None, description="主播uid")
    follow_count: Optional[int] = Field(0, description="关注数")
    follower_count: Optional[int] = Field(0, description="粉丝数")
    total_likes: Optional[int] = Field(0, description="获赞数")
    signature: Optional[str] = Field(None, description="个性签名")
    verified: Optional[bool] = Field(False, description="是否认证")
    verify_type: Optional[int] = Field(-1, description="认证类型")
    city: Optional[str] = Field(None, description="城市")
    province: Optional[str] = Field(None, description="省份")
    country: Optional[str] = Field(None, description="国家")
    location: Optional[str] = Field(None, description="IP属地")
    age: Optional[int] = Field(0, description="年龄")
    gender: Optional[int] = Field(0, description="性别: 0未知, 1男, 2女")


class LiveRoomInfo(BaseModel):
    """直播间信息"""
    web_rid: str = Field(..., description="直播间web_rid (用户输入的ID)")
    room_id: str = Field(..., description="直播间真实room_id")
    user_id: Optional[str] = Field(None, description="用户ID")
    title: Optional[str] = Field(None, description="直播间标题")
    owner: Optional[LiveOwner] = Field(None, description="主播信息")
    stream_url: Optional[StreamUrl] = Field(None, description="视频流地址")
    user_count: Optional[int] = Field(0, description="观看人数")
    status: int = Field(0, description="直播状态: 2=直播中, 4=未开播")


class LiveMessage(BaseModel):
    """直播消息"""
    type: str = Field(..., description="消息类型: gift/chat/member/like/follow/room_stats")
    user: Optional[Dict[str, Any]] = Field(None, description="用户信息")
    content: Optional[str] = Field(None, description="消息内容")
    count: Optional[int] = Field(None, description="数量")
    total: Optional[int] = Field(None, description="总数")
    gift: Optional[Dict[str, Any]] = Field(None, description="礼物信息")
    to_user: Optional[Dict[str, Any]] = Field(None, description="接收者信息")
    member_count: Optional[int] = Field(None, description="直播间人数")


class LiveStatus(BaseModel):
    """直播状态"""
    live_id: str = Field(..., description="直播间ID")
    is_running: bool = Field(False, description="是否运行中")
    message: str = Field("", description="状态消息")


class LiveInfoRequest(BaseModel):
    """获取直播间信息请求"""
    input: str = Field(..., description="直播间ID或链接")


class LiveStartRequest(BaseModel):
    """启动直播监听请求"""
    live_id: str = Field(..., description="直播间ID")
