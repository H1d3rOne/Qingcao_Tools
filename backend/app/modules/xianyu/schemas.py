"""
闲鱼搜索相关 Schema
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class XianyuSearchRequest(BaseModel):
    """闲鱼搜索请求"""
    keyword: str = Field(..., min_length=1, description="搜索关键词")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=50, description="每页条数")
    province: str = Field("", description="省份")
    city: str = Field("", description="城市")
    sort_field: str = Field("", description="排序字段")
    sort_value: str = Field("", description="排序值")
    prop_values: Dict[str, str] = Field(default_factory=dict, description="筛选属性")


class XianyuFilterOption(BaseModel):
    """闲鱼筛选项"""
    label: str = Field(..., description="展示文案")
    value: str = Field(..., description="属性值")
    checked: bool = Field(False, description="是否选中")


class XianyuFilterGroup(BaseModel):
    """闲鱼筛选分组"""
    name: str = Field(..., description="分组名称")
    pid: str = Field(..., description="属性 ID")
    options: List[XianyuFilterOption] = Field(default_factory=list, description="可选项")


class XianyuSearchItem(BaseModel):
    """闲鱼搜索结果项"""
    item_id: str = Field(..., description="商品 ID")
    title: str = Field("", description="标题")
    price: str = Field("", description="价格文本")
    image: str = Field("", description="图片地址")
    area: str = Field("", description="区域")
    seller: str = Field("", description="卖家昵称")
    seller_avatar: str = Field("", description="卖家头像")
    want: str = Field("", description="想要人数")
    tags: List[str] = Field(default_factory=list, description="标签")
    detail_url: str = Field("", description="详情链接")


class XianyuSearchResult(BaseModel):
    """闲鱼搜索结果"""
    keyword: str = Field(..., description="搜索词")
    total: int = Field(0, description="总数")
    page: int = Field(1, description="当前页")
    page_size: int = Field(20, description="每页条数")
    has_more: bool = Field(False, description="是否还有下一页")
    location: str = Field("", description="位置")
    search_id: str = Field("", description="搜索 ID")
    items: List[XianyuSearchItem] = Field(default_factory=list, description="商品列表")
    filters: List[XianyuFilterGroup] = Field(default_factory=list, description="筛选项")


class XianyuMonitorHit(BaseModel):
    """闲鱼监控命中项"""
    item_id: str = Field(..., description="商品 ID")
    title: str = Field("", description="标题")
    price: str = Field("", description="价格")
    image: str = Field("", description="图片")
    detail_url: str = Field("", description="详情链接")
    discovered_at: int = Field(0, description="命中时间戳")


class XianyuMonitorTask(BaseModel):
    """闲鱼关键词监控任务"""
    id: str = Field(..., description="任务 ID")
    name: str = Field(..., description="任务名称")
    keyword: str = Field(..., description="关键词")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=50, description="每页条数")
    sort_field: str = Field("", description="排序字段")
    sort_value: str = Field("", description="排序方向")
    prop_values: Dict[str, str] = Field(default_factory=dict, description="筛选属性")
    min_price: Optional[float] = Field(None, ge=0, description="最低价")
    max_price: Optional[float] = Field(None, ge=0, description="最高价")
    interval_seconds: int = Field(180, ge=30, description="轮询间隔")
    enabled: bool = Field(True, description="是否启用")
    created_at: int = Field(0, description="创建时间")
    updated_at: int = Field(0, description="更新时间")
    last_run_at: int = Field(0, description="最近执行时间")
    last_status: str = Field("idle", description="最近状态")
    last_error: str = Field("", description="最近错误")
    seen_item_ids: List[str] = Field(default_factory=list, description="已见商品 ID")
    latest_hits: List[XianyuMonitorHit] = Field(default_factory=list, description="最近命中")


class XianyuMonitorTaskCreate(BaseModel):
    """创建闲鱼监控任务"""
    name: str = Field(..., min_length=1, max_length=50, description="任务名称")
    keyword: str = Field(..., min_length=1, description="关键词")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=50, description="每页条数")
    sort_field: str = Field("", description="排序字段")
    sort_value: str = Field("", description="排序方向")
    prop_values: Dict[str, str] = Field(default_factory=dict, description="筛选属性")
    min_price: Optional[float] = Field(None, ge=0, description="最低价")
    max_price: Optional[float] = Field(None, ge=0, description="最高价")
    interval_seconds: int = Field(180, ge=30, description="轮询间隔")


class XianyuMonitorTaskUpdate(BaseModel):
    """更新闲鱼监控任务"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="任务名称")
    keyword: Optional[str] = Field(None, min_length=1, description="关键词")
    page: Optional[int] = Field(None, ge=1, description="页码")
    page_size: Optional[int] = Field(None, ge=1, le=50, description="每页条数")
    sort_field: Optional[str] = Field(None, description="排序字段")
    sort_value: Optional[str] = Field(None, description="排序方向")
    prop_values: Optional[Dict[str, str]] = Field(None, description="筛选属性")
    min_price: Optional[float] = Field(None, ge=0, description="最低价")
    max_price: Optional[float] = Field(None, ge=0, description="最高价")
    interval_seconds: Optional[int] = Field(None, ge=30, description="轮询间隔")
    enabled: Optional[bool] = Field(None, description="是否启用")


class XianyuAuthLoginRequest(BaseModel):
    """闲鱼登录请求"""
    method: str = Field(default="cookie", description="登录方式: qrcode, cookie")
    cookies: Optional[str] = Field(default=None, description="Cookie 字符串")


class XianyuAuthLoginResponse(BaseModel):
    """闲鱼登录响应"""
    success: bool = Field(True, description="是否成功")
    message: str = Field("", description="消息")
    qrcode_url: Optional[str] = Field(None, description="二维码 URL")
    qrcode_token: Optional[str] = Field(None, description="二维码 token")
    qrcode_image: Optional[str] = Field(None, description="二维码图片")
    login_token: Optional[str] = Field(None, description="登录后的 Cookie 字符串")


class XianyuAuthCheckLoginRequest(BaseModel):
    """检查扫码状态请求"""
    qrcode_token: str = Field(..., description="二维码 token")


class XianyuAuthCheckLoginResponse(BaseModel):
    """检查扫码状态响应"""
    success: bool = Field(True, description="是否成功")
    message: str = Field("", description="消息")
    is_logged_in: bool = Field(False, description="是否已登录")
    login_token: Optional[str] = Field(None, description="登录后的 Cookie 字符串")


class XianyuAuthStatusResponse(BaseModel):
    """闲鱼登录状态"""
    success: bool = Field(True, description="是否成功")
    message: str = Field("", description="消息")
    is_logged_in: bool = Field(False, description="是否已登录")
    user_info: Optional[dict] = Field(default=None, description="用户信息")


class XianyuAuthLogoutResponse(BaseModel):
    """闲鱼退出登录响应"""
    success: bool = Field(True, description="是否成功")
    message: str = Field("", description="消息")


class XianyuUserProfile(BaseModel):
    """闲鱼登录用户信息"""
    display_name: str = Field("", description="用户昵称")
    avatar: str = Field("", description="头像地址")
    sold_count: int = Field(0, description="卖出数量")
    purchase_count: int = Field(0, description="购买数量")
    followers: int = Field(0, description="粉丝数")
    following: int = Field(0, description="关注数")
    collection_count: int = Field(0, description="收藏数量")


class XianyuDetailAttribute(BaseModel):
    """闲鱼宝贝详情属性"""
    name: str = Field("", description="属性名")
    value: str = Field("", description="属性值")


class XianyuItemDetail(BaseModel):
    """闲鱼宝贝详情"""
    item_id: str = Field("", description="宝贝 ID")
    title: str = Field("", description="标题")
    price: str = Field("", description="价格")
    original_price: str = Field("", description="原价")
    desc: str = Field("", description="描述")
    images: List[str] = Field(default_factory=list, description="图片列表")
    location: str = Field("", description="发布地")
    publish_time: str = Field("", description="发布时间")
    status: str = Field("", description="状态")
    transport_fee: str = Field("", description="运费")
    browse_count: int = Field(0, description="浏览量")
    want_count: int = Field(0, description="想要人数")
    collect_count: int = Field(0, description="收藏数")
    tags: List[str] = Field(default_factory=list, description="标签")
    attributes: List[XianyuDetailAttribute] = Field(default_factory=list, description="属性")
    seller_name: str = Field("", description="卖家昵称")
    seller_user_id: str = Field("", description="卖家用户 ID")
    seller_avatar: str = Field("", description="卖家头像")
    seller_summary: str = Field("", description="卖家简介")
    seller_city: str = Field("", description="卖家城市")
    seller_last_visit: str = Field("", description="卖家最近活跃")
    seller_item_count: int = Field(0, description="卖家在售数量")
    detail_url: str = Field("", description="原站详情链接")


class XianyuChatProfile(BaseModel):
    """闲鱼聊天当前登录用户"""
    user_id: str = Field("", description="当前用户 ID")
    main_user_id: str = Field("", description="主账号 ID")
    domain: str = Field("goofish", description="聊天域名")
    display_name: str = Field("", description="昵称")
    avatar: str = Field("", description="头像")


class XianyuChatConversation(BaseModel):
    """闲鱼聊天会话"""
    cid: str = Field("", description="会话 CID")
    session_id: str = Field("", description="会话 ID")
    session_type: int = Field(1, description="会话类型")
    biz_type: str = Field("", description="业务类型")
    title: str = Field("", description="会话标题")
    peer_user_id: str = Field("", description="对端用户 ID")
    peer_display_name: str = Field("", description="对端展示名")
    peer_avatar: str = Field("", description="对端头像")
    item_id: str = Field("", description="关联商品 ID")
    item_title: str = Field("", description="关联商品标题")
    item_image: str = Field("", description="关联商品图片")
    last_message_id: str = Field("", description="最后一条消息 ID")
    last_message_summary: str = Field("", description="最后一条消息摘要")
    last_message_time: int = Field(0, description="最后一条消息时间戳")
    last_message_time_text: str = Field("", description="最后一条消息时间文本")
    unread_count: int = Field(0, description="未读数")
    red_point: int = Field(0, description="红点状态")
    top_rank: int = Field(0, description="置顶值")
    muted: bool = Field(False, description="是否免打扰")
    visible: bool = Field(True, description="是否显示")
    can_send: bool = Field(True, description="是否支持发送")


class XianyuChatConversationPage(BaseModel):
    """闲鱼聊天会话列表"""
    total: int = Field(0, description="当前返回数量")
    offset: int = Field(0, description="偏移")
    limit: int = Field(20, description="数量")
    conversations: List[XianyuChatConversation] = Field(default_factory=list, description="会话列表")


class XianyuChatOpenSessionRequest(BaseModel):
    """打开聊天会话请求"""
    item_id: str = Field(..., min_length=1, description="商品 ID")
    peer_user_id: str = Field(..., min_length=1, description="卖家用户 ID")


class XianyuChatOpenSessionResponse(BaseModel):
    """打开聊天会话响应"""
    success: bool = Field(True, description="是否成功")
    message: str = Field("", description="提示消息")
    cid: str = Field("", description="会话 CID")
    session: Optional[XianyuChatConversation] = Field(None, description="匹配到的会话")


class XianyuChatMessage(BaseModel):
    """闲鱼聊天消息"""
    cid: str = Field("", description="会话 CID")
    message_id: str = Field("", description="消息 ID")
    numeric_message_id: int = Field(0, description="数值消息 ID")
    sender_uid: str = Field("", description="发送者 UID")
    sender_display_name: str = Field("", description="发送者展示名")
    direction: str = Field("in", description="消息方向")
    content_type: int = Field(0, description="消息内容类型")
    summary: str = Field("", description="消息摘要")
    text: str = Field("", description="消息文本")
    image_url: str = Field("", description="图片地址")
    create_at: int = Field(0, description="消息时间戳")
    create_at_text: str = Field("", description="消息时间文本")
    read_status: int = Field(0, description="已读状态")
    raw_extension: Dict[str, str] = Field(default_factory=dict, description="原始扩展")


class XianyuChatMessagePage(BaseModel):
    """闲鱼聊天消息列表"""
    cid: str = Field("", description="会话 CID")
    cursor: Optional[str] = Field(None, description="下一游标")
    has_more: bool = Field(False, description="是否还有更多")
    messages: List[XianyuChatMessage] = Field(default_factory=list, description="消息列表")


class XianyuChatConversationsQuery(BaseModel):
    """聊天会话查询"""
    offset: int = Field(0, ge=0, description="偏移")
    limit: int = Field(20, ge=1, le=50, description="数量")


class XianyuChatMessagesQuery(BaseModel):
    """聊天消息查询"""
    cid: str = Field(..., min_length=1, description="会话 CID")
    cursor: Optional[str] = Field(None, description="消息游标")
    limit: int = Field(20, ge=1, le=50, description="数量")
    direction: str = Field("prev", description="方向 prev/next")


class XianyuChatSendRequest(BaseModel):
    """发送聊天消息请求"""
    cid: str = Field(..., min_length=1, description="会话 CID")
    text: str = Field(..., min_length=1, max_length=1000, description="消息文本")


class XianyuChatSendResult(BaseModel):
    """发送聊天消息结果"""
    cid: str = Field("", description="会话 CID")
    message_id: str = Field("", description="消息 ID")
    uuid: str = Field("", description="客户端消息 UUID")
    create_at: int = Field(0, description="发送时间")
    summary: str = Field("", description="消息摘要")


class XianyuChatClearRequest(BaseModel):
    """清理聊天会话红点"""
    cids: List[str] = Field(default_factory=list, description="会话 CID 列表")


class XianyuChatClearResult(BaseModel):
    """清理聊天会话红点结果"""
    success_count: int = Field(0, description="成功数量")


class XianyuChatImageSendRequest(BaseModel):
    """发送聊天图片消息请求"""
    cid: str = Field(..., min_length=1, description="会话 CID")
    image_url: str = Field(..., min_length=1, description="图片 URL")
    width: int = Field(0, description="图片宽度")
    height: int = Field(0, description="图片高度")


class XianyuChatRecallRequest(BaseModel):
    """撤回聊天消息请求"""
    message_id: str = Field(..., min_length=1, description="消息 ID")


class XianyuChatMarkReadRequest(BaseModel):
    """标记聊天消息已读请求"""
    cid: str = Field(..., min_length=1, description="会话 CID")


class XianyuChatCreateSessionRequest(BaseModel):
    """创建聊天会话请求"""
    peer_user_id: str = Field(..., min_length=1, description="对方用户 ID")
    item_id: str = Field("", description="关联商品 ID")


class XianyuPublishMeta(BaseModel):
    """闲鱼发布元数据"""
    categories: List[Dict[str, str]] = Field(default_factory=list, description="分类")
    conditions: List[Dict[str, str]] = Field(default_factory=list, description="成色")
    shipping_modes: List[Dict[str, str]] = Field(default_factory=list, description="运费方式")
    provinces: List[Dict[str, str]] = Field(default_factory=list, description="省份")


class XianyuPublishImageUploadResult(BaseModel):
    """闲鱼发布图片上传结果"""
    image_id: str = Field(..., description="图片 ID")
    image_url: str = Field("", description="图片地址")
    width: int = Field(0, description="宽度")
    height: int = Field(0, description="高度")


class XianyuPublishSubmitRequest(BaseModel):
    """闲鱼商品发布请求"""
    title: str = Field(..., min_length=1, max_length=100, description="标题")
    desc: str = Field(..., min_length=1, max_length=5000, description="描述")
    price: float = Field(..., gt=0, description="售价")
    original_price: Optional[float] = Field(None, gt=0, description="原价")
    category_id: str = Field(..., min_length=1, description="分类 ID")
    condition_id: str = Field(..., min_length=1, description="成色 ID")
    province: str = Field(..., min_length=1, description="省份")
    city: str = Field(..., min_length=1, description="城市")
    shipping_mode: str = Field(..., min_length=1, description="运费方式")
    free_shipping: bool = Field(False, description="是否包邮")
    image_ids: List[str] = Field(..., min_length=1, description="图片 ID 列表")
    attribute_values: Dict[str, str] = Field(default_factory=dict, description="属性")


class XianyuPublishSubmitResult(BaseModel):
    """闲鱼商品发布结果"""
    item_id: str = Field("", description="商品 ID")
    detail_url: str = Field("", description="详情链接")
    message: str = Field("", description="结果消息")


class XianyuChatAiProvider(BaseModel):
    """闲鱼聊天 AI 供应商配置"""
    id: str = Field(..., description="供应商 ID")
    name: str = Field(..., description="供应商名称")
    base_url: str = Field(..., description="OpenAI 兼容接口根地址")
    models: List[str] = Field(default_factory=list, description="模型列表")
    active_model: str = Field("", description="当前使用的模型")
    system_prompt: str = Field("", description="系统提示词")
    api_key_configured: bool = Field(False, description="是否已配置 API Key")
    api_key_masked: str = Field("", description="脱敏后的 API Key")
    is_active: bool = Field(False, description="是否为当前激活供应商")

    @property
    def model(self) -> str:
        return self.active_model or (self.models[0] if self.models else "")


class XianyuChatAiProviderCreateRequest(BaseModel):
    """闲鱼聊天 AI 供应商创建请求"""
    model_config = {"populate_by_name": True}

    name: str = Field(..., min_length=1, max_length=50, description="供应商名称")
    base_url: str = Field(..., min_length=1, description="OpenAI 兼容接口根地址")
    api_key: str = Field("", description="API Key")
    models: List[str] = Field(default_factory=list, description="模型列表")
    active_model: str = Field("", description="当前使用的模型")
    system_prompt: str = Field("", description="系统提示词")
    provider_id: str = Field("", description="供应商 ID，编辑时传入用于回查已保存的 API Key")

    def get_model(self) -> str:
        return self.active_model or (self.models[0] if self.models else "")


class XianyuChatAiProviderUpdateRequest(BaseModel):
    """闲鱼聊天 AI 供应商更新请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="供应商名称")
    base_url: Optional[str] = Field(None, min_length=1, description="OpenAI 兼容接口根地址")
    api_key: Optional[str] = Field(None, description="新的 API Key，None 表示保留旧值")
    models: Optional[List[str]] = Field(None, description="模型列表")
    active_model: Optional[str] = Field(None, description="当前使用的模型")
    system_prompt: Optional[str] = Field(None, description="系统提示词")


class XianyuChatAiConfig(BaseModel):
    """闲鱼聊天 AI 配置"""
    enabled: bool = Field(False, description="是否启用 AI 总开关")
    chat_keepalive_interval_seconds: int = Field(180, ge=30, le=3600, description="聊天保活间隔秒数")
    providers: List[XianyuChatAiProvider] = Field(default_factory=list, description="供应商列表")
    active_provider_id: str = Field("", description="当前激活的供应商 ID")


class XianyuChatAiSessionState(BaseModel):
    """闲鱼聊天会话 AI 状态"""
    cid: str = Field(..., min_length=1, description="会话 CID")
    enabled: bool = Field(False, description="当前会话是否启用 AI")


class XianyuChatAiSessionUpdateRequest(BaseModel):
    """闲鱼聊天会话 AI 状态更新请求"""
    enabled: bool = Field(False, description="当前会话是否启用 AI")


class XianyuChatAiTestRequest(BaseModel):
    """闲鱼聊天 AI 测试请求"""
    text: str = Field(..., min_length=1, max_length=1000, description="测试输入内容")
    cid: str = Field("", description="可选的会话 CID，用于补充上下文")


class XianyuChatAiTestResponse(BaseModel):
    """闲鱼聊天 AI 测试响应"""
    reply: str = Field("", description="模型回复")


class XianyuChatHealthStatus(BaseModel):
    """闲鱼聊天链路诊断结果"""
    ok: bool = Field(False, description="聊天链路是否可用")
    status: str = Field("unknown", description="状态标记：ok/risk_blocked/auth_invalid/cookie_missing/error")
    message: str = Field("", description="诊断消息")
    captcha_url: str = Field("", description="风控验证链接")
    shared_ws_connected: bool = Field(False, description="当前共享 WebSocket 是否已连接")
    cookie_configured: bool = Field(False, description="是否已配置闲鱼 Cookie")


class XianyuManageItem(BaseModel):
    """闲鱼管理商品"""
    item_id: str = Field(..., description="商品 ID")
    item_title: str = Field("", description="商品标题")
    item_price: str = Field("", description="商品价格")
    item_image: str = Field("", description="商品主图")
    item_status: str = Field("", description="商品状态")
    item_detail: str = Field("", description="商品详情文本")
    multi_quantity_delivery: bool = Field(False, description="是否启用多数量发货")
    synced_at: int = Field(0, description="最近同步时间")
    updated_at: int = Field(0, description="最近更新时间")


class XianyuManageItemPage(BaseModel):
    """闲鱼管理商品分页列表"""
    items: List[XianyuManageItem] = Field(default_factory=list, description="商品列表")
    total: int = Field(0, description="总数")
    page: int = Field(1, description="当前页")
    page_size: int = Field(20, description="每页数量")
    has_more: bool = Field(False, description="是否还有更多")


class XianyuManageItemPolishRequest(BaseModel):
    """闲鱼管理商品擦亮请求"""
    item_id: str = Field(..., description="商品 ID")
    enable_notification: bool = Field(False, description="是否输出日志")


class XianyuManageItemPolishResponse(BaseModel):
    """闲鱼管理商品擦亮响应"""
    success: bool = Field(True, description="是否成功")
    item_id: str = Field(..., description="商品 ID")
    message: str = Field("", description="提示信息")


class XianyuManageItemPolishAllResponse(BaseModel):
    """闲鱼管理商品批量擦亮响应"""
    total: int = Field(..., description="商品总数")
    polished: int = Field(..., description="擦亮成功数量")


class XianyuManageItemSyncPageRequest(BaseModel):
    """闲鱼管理商品单页同步请求"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


class XianyuManageItemUpdateRequest(BaseModel):
    """闲鱼管理商品更新请求"""
    item_detail: str = Field("", description="商品详情文本")


class XianyuManageItemMultiQuantityUpdateRequest(BaseModel):
    """闲鱼管理商品多数量发货开关请求"""
    enabled: bool = Field(False, description="是否启用多数量发货")


class XianyuDeliveryRule(BaseModel):
    """闲鱼自动发货规则"""
    id: str = Field(..., description="规则 ID")
    name: str = Field(..., description="规则名称")
    enabled: bool = Field(True, description="是否启用")
    item_id: str = Field("", description="关联商品 ID")
    keyword: str = Field("", description="关键字")
    match_mode: str = Field("item_id", description="匹配模式")
    delivery_text: str = Field("", description="发货文本")
    send_chat_text: bool = Field(True, description="是否发送聊天文本")
    send_dummy_ship: bool = Field(True, description="是否调用虚拟发货")
    created_at: int = Field(0, description="创建时间")
    updated_at: int = Field(0, description="更新时间")


class XianyuDeliveryRuleCreateRequest(BaseModel):
    """闲鱼自动发货规则创建请求"""
    name: str = Field(..., min_length=1, max_length=50, description="规则名称")
    enabled: bool = Field(True, description="是否启用")
    item_id: str = Field("", description="关联商品 ID")
    keyword: str = Field("", description="关键字")
    match_mode: str = Field("item_id", description="匹配模式")
    delivery_text: str = Field("", max_length=5000, description="发货文本")
    send_chat_text: bool = Field(True, description="是否发送聊天文本")
    send_dummy_ship: bool = Field(True, description="是否调用虚拟发货")


class XianyuDeliveryRuleUpdateRequest(BaseModel):
    """闲鱼自动发货规则更新请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="规则名称")
    enabled: Optional[bool] = Field(None, description="是否启用")
    item_id: Optional[str] = Field(None, description="关联商品 ID")
    keyword: Optional[str] = Field(None, description="关键字")
    match_mode: Optional[str] = Field(None, description="匹配模式")
    delivery_text: Optional[str] = Field(None, max_length=5000, description="发货文本")
    send_chat_text: Optional[bool] = Field(None, description="是否发送聊天文本")
    send_dummy_ship: Optional[bool] = Field(None, description="是否调用虚拟发货")


class XianyuDeliveryExecutionRecord(BaseModel):
    """闲鱼自动发货执行记录"""
    id: str = Field(..., description="执行记录 ID")
    rule_id: str = Field("", description="规则 ID")
    rule_name: str = Field("", description="规则名称")
    order_id: str = Field("", description="订单 ID")
    item_id: str = Field("", description="商品 ID")
    buyer_id: str = Field("", description="买家 ID")
    status: str = Field("skipped", description="执行状态")
    message: str = Field("", description="结果说明")
    created_at: int = Field(0, description="创建时间")


class XianyuDeliveryRuntimeStatus(BaseModel):
    """闲鱼自动发货运行状态"""
    running: bool = Field(False, description="是否运行中")
    last_event_at: int = Field(0, description="最近事件时间")
    last_success_at: int = Field(0, description="最近成功时间")
    last_failure_at: int = Field(0, description="最近失败时间")
    last_error: str = Field("", description="最近错误")
    enabled_rule_count: int = Field(0, description="启用规则数量")
    recent_success_count: int = Field(0, description="最近成功数")
    recent_failure_count: int = Field(0, description="最近失败数")
