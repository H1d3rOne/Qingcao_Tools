from pathlib import Path

import pytest

from app.modules.xianyu.delivery_runtime import XianyuDeliveryRuntime
from app.modules.xianyu.delivery_store import XianyuDeliveryStore
from app.modules.xianyu.item_store import XianyuItemStore
from app.modules.xianyu.schemas import XianyuDeliveryRuleCreateRequest
from app.modules.xianyu.service import XianyuService


class FakeExecutor:
    def __init__(self):
        self.calls = []

    async def send_chat_and_ship(self, *, order_id: str, item_id: str, buyer_id: str, delivery_text: str):
        self.calls.append((order_id, item_id, buyer_id, delivery_text))
        return "ok"


@pytest.mark.asyncio
async def test_delivery_runtime_matches_rule_and_records_success(tmp_path: Path):
    item_store = XianyuItemStore(tmp_path / "items.json")
    delivery_store = XianyuDeliveryStore(
        tmp_path / "rules.json",
        tmp_path / "runtime.json",
    )
    delivery_store.create_rule(
        XianyuDeliveryRuleCreateRequest(
            name="按商品发货",
            enabled=True,
            item_id="1001",
            keyword="",
            match_mode="item_id",
            delivery_text="卡密 123",
            send_chat_text=True,
            send_dummy_ship=True,
        )
    )
    runtime = XianyuDeliveryRuntime(item_store=item_store, delivery_store=delivery_store)
    executor = FakeExecutor()

    await runtime.process_event(
        {"order_id": "order-1", "item_id": "1001", "buyer_id": "buyer-1", "text": "我已付款"},
        executor=executor,
    )

    assert executor.calls == [("order-1", "1001", "buyer-1", "卡密 123")]
    assert delivery_store.list_executions(limit=1)[0].status == "success"


@pytest.mark.asyncio
async def test_service_forwards_candidate_delivery_event_to_runtime(monkeypatch, tmp_path: Path):
    service = XianyuService()
    service._item_store_path = tmp_path / "items.json"
    service._delivery_rules_path = tmp_path / "rules.json"
    service._delivery_runtime_path = tmp_path / "runtime.json"
    service._item_store = None
    service._delivery_store = None
    service._delivery_runtime = None

    captured = {}

    async def fake_process_event(event, executor):
        captured["event"] = event
        captured["executor"] = executor

    monkeypatch.setattr(service.delivery_runtime, "process_event", fake_process_event)

    await service.handle_delivery_candidate_event(
        {
            "order_id": "order-1",
            "item_id": "1001",
            "buyer_id": "buyer-1",
            "text": "我已付款，等待发货",
        }
    )

    assert captured["event"]["order_id"] == "order-1"
    assert captured["executor"] is service


@pytest.mark.asyncio
async def test_delivery_runtime_skips_matched_rule_without_required_order_fields(tmp_path: Path):
    item_store = XianyuItemStore(tmp_path / "items.json")
    delivery_store = XianyuDeliveryStore(
        tmp_path / "rules.json",
        tmp_path / "runtime.json",
    )
    delivery_store.create_rule(
        XianyuDeliveryRuleCreateRequest(
            name="按商品发货",
            enabled=True,
            item_id="1001",
            keyword="",
            match_mode="item_id",
            delivery_text="卡密 123",
            send_chat_text=True,
            send_dummy_ship=True,
        )
    )
    runtime = XianyuDeliveryRuntime(item_store=item_store, delivery_store=delivery_store)
    executor = FakeExecutor()

    await runtime.process_event(
        {"order_id": "", "item_id": "1001", "buyer_id": "buyer-1", "text": "我已付款"},
        executor=executor,
    )

    assert executor.calls == []
    assert delivery_store.list_executions(limit=1)[0].message == "missing required fields"


@pytest.mark.asyncio
async def test_chat_listener_forwards_delivery_event_without_ai_enabled(monkeypatch, tmp_path: Path):
    import asyncio

    from app.modules.xianyu.schemas import XianyuChatAiConfig, XianyuChatProfile

    class FakeBroadcastChatClient:
        def __init__(self):
            self.profile = XianyuChatProfile(
                user_id='111',
                main_user_id='111',
                domain='goofish',
                display_name='卖家',
                avatar='',
            )
            self.connected = True
            self.subscribers = []

        def is_connected(self) -> bool:
            return self.connected

        def subscribe_pushes(self):
            queue = asyncio.Queue()
            self.subscribers.append(queue)
            return queue

        def unsubscribe_pushes(self, queue):
            if queue in self.subscribers:
                self.subscribers.remove(queue)

        async def emit(self, payload):
            for queue in list(self.subscribers):
                await queue.put(payload)

        async def close(self):
            self.connected = False

    service = XianyuService()
    service._item_store_path = tmp_path / "items.json"
    service._delivery_rules_path = tmp_path / "rules.json"
    service._delivery_runtime_path = tmp_path / "runtime.json"
    service._item_store = None
    service._delivery_store = None
    service._delivery_runtime = None
    service.delivery_store.create_rule(
        XianyuDeliveryRuleCreateRequest(
            name="按商品发货",
            enabled=True,
            item_id="1001001001",
            keyword="",
            match_mode="item_id",
            delivery_text="卡密 123",
            send_chat_text=True,
            send_dummy_ship=True,
        )
    )

    fake_client = FakeBroadcastChatClient()
    captured = []

    monkeypatch.setattr(service, 'open_chat_ws_client', lambda: asyncio.sleep(0, result=fake_client))
    monkeypatch.setattr(service, 'get_chat_ai_config', lambda: XianyuChatAiConfig(enabled=False, providers=[], active_provider_id=''))
    monkeypatch.setattr(service.chat_ai_store, 'get_active_provider', lambda: None)
    monkeypatch.setattr(service, '_get_xianyu_cookie_value', lambda: 'cookie')

    async def fake_handle_delivery_candidate_event(payload):
        captured.append(payload)

    monkeypatch.setattr(service, 'handle_delivery_candidate_event', fake_handle_delivery_candidate_event)
    monkeypatch.setattr(
        service,
        'decode_chat_push',
        lambda payload: {
            'type': 'sync',
            'items': [
                {
                    'biz_type': 40000,
                    'decoded': {
                        'raw_text': 'https://www.goofish.com/order-detail?orderId=1234567890123456',
                        'urls': ['https://www.goofish.com/order-detail?orderId=1234567890123456'],
                        'json_objects': [
                            {
                                '1': {
                                    '2': 'cid-1@goofish',
                                    '7': 1,
                                    '6': {'3': {'4': 6}},
                                    '10': {
                                        'senderUserId': '2002002002',
                                        'reminderContent': '[我已付款，等待你发货]',
                                        'reminderTitle': '买家A',
                                    },
                                    '3': {
                                        'extension': {
                                            'itemId': '1001001001',
                                        }
                                    },
                                }
                            }
                        ],
                    },
                }
            ],
        },
    )

    await service.ensure_chat_ai_listener()
    for _ in range(20):
        if fake_client.subscribers:
            break
        await asyncio.sleep(0.01)

    try:
        await fake_client.emit({'lwp': '/s/sync', 'body': {'syncPushPackage': {'data': []}}})
        await asyncio.sleep(0.1)
    finally:
        await service.stop_chat_ai_listener()

    assert captured == [
        {
            'order_id': '1234567890123456',
            'item_id': '1001001001',
            'buyer_id': '2002002002',
            'text': '[我已付款，等待你发货]',
        }
    ]


@pytest.mark.asyncio
async def test_chat_listener_ignores_non_system_delivery_trigger(monkeypatch, tmp_path: Path):
    import asyncio

    from app.modules.xianyu.schemas import XianyuChatAiConfig, XianyuChatProfile

    class FakeBroadcastChatClient:
        def __init__(self):
            self.profile = XianyuChatProfile(
                user_id='111',
                main_user_id='111',
                domain='goofish',
                display_name='卖家',
                avatar='',
            )
            self.connected = True
            self.subscribers = []

        def is_connected(self) -> bool:
            return self.connected

        def subscribe_pushes(self):
            queue = asyncio.Queue()
            self.subscribers.append(queue)
            return queue

        def unsubscribe_pushes(self, queue):
            if queue in self.subscribers:
                self.subscribers.remove(queue)

        async def emit(self, payload):
            for queue in list(self.subscribers):
                await queue.put(payload)

        async def close(self):
            self.connected = False

    service = XianyuService()
    service._item_store_path = tmp_path / "items.json"
    service._delivery_rules_path = tmp_path / "rules.json"
    service._delivery_runtime_path = tmp_path / "runtime.json"
    service._item_store = None
    service._delivery_store = None
    service._delivery_runtime = None
    service.delivery_store.create_rule(
        XianyuDeliveryRuleCreateRequest(
            name="按商品发货",
            enabled=True,
            item_id="1001001001",
            keyword="",
            match_mode="item_id",
            delivery_text="卡密 123",
            send_chat_text=True,
            send_dummy_ship=True,
        )
    )

    fake_client = FakeBroadcastChatClient()
    captured = []

    monkeypatch.setattr(service, 'open_chat_ws_client', lambda: asyncio.sleep(0, result=fake_client))
    monkeypatch.setattr(service, 'get_chat_ai_config', lambda: XianyuChatAiConfig(enabled=False, providers=[], active_provider_id=''))
    monkeypatch.setattr(service.chat_ai_store, 'get_active_provider', lambda: None)
    monkeypatch.setattr(service, '_get_xianyu_cookie_value', lambda: 'cookie')

    async def fake_handle_delivery_candidate_event(payload):
        captured.append(payload)

    monkeypatch.setattr(service, 'handle_delivery_candidate_event', fake_handle_delivery_candidate_event)
    monkeypatch.setattr(
        service,
        'decode_chat_push',
        lambda payload: {
            'type': 'sync',
            'items': [
                {
                    'biz_type': 40000,
                    'decoded': {
                        'raw_text': 'https://www.goofish.com/order-detail?orderId=1234567890123456',
                        'json_objects': [
                            {
                                '1': {
                                    '2': 'cid-1@goofish',
                                    '7': 0,
                                    '6': {'3': {'4': 1}},
                                    '10': {
                                        'senderUserId': '2002002002',
                                        'reminderContent': '[我已付款，等待你发货]',
                                        'reminderTitle': '买家A',
                                    },
                                    '3': {'extension': {'itemId': '1001001001'}},
                                }
                            }
                        ],
                    },
                }
            ],
        },
    )

    await service.ensure_chat_ai_listener()
    for _ in range(20):
        if fake_client.subscribers:
            break
        await asyncio.sleep(0.01)

    try:
        await fake_client.emit({'lwp': '/s/sync', 'body': {'syncPushPackage': {'data': []}}})
        await asyncio.sleep(0.1)
    finally:
        await service.stop_chat_ai_listener()

    assert captured == []


@pytest.mark.asyncio
async def test_chat_listener_extracts_delivery_event_from_system_detail_notice(monkeypatch, tmp_path: Path):
    import asyncio

    from app.modules.xianyu.schemas import XianyuChatAiConfig, XianyuChatProfile

    class FakeBroadcastChatClient:
        def __init__(self):
            self.profile = XianyuChatProfile(
                user_id='111',
                main_user_id='111',
                domain='goofish',
                display_name='卖家',
                avatar='',
            )
            self.connected = True
            self.subscribers = []

        def is_connected(self) -> bool:
            return self.connected

        def subscribe_pushes(self):
            queue = asyncio.Queue()
            self.subscribers.append(queue)
            return queue

        def unsubscribe_pushes(self, queue):
            if queue in self.subscribers:
                self.subscribers.remove(queue)

        async def emit(self, payload):
            for queue in list(self.subscribers):
                await queue.put(payload)

        async def close(self):
            self.connected = False

    service = XianyuService()
    service._item_store_path = tmp_path / "items.json"
    service._delivery_rules_path = tmp_path / "rules.json"
    service._delivery_runtime_path = tmp_path / "runtime.json"
    service._item_store = None
    service._delivery_store = None
    service._delivery_runtime = None
    service.delivery_store.create_rule(
        XianyuDeliveryRuleCreateRequest(
            name="按商品发货",
            enabled=True,
            item_id="1001001001",
            keyword="",
            match_mode="item_id",
            delivery_text="卡密 123",
            send_chat_text=True,
            send_dummy_ship=True,
        )
    )
    service._conversation_item_cache['cid-1@goofish'] = {
        'item_id': '1001001001',
        'peer_user_id': '2002002002',
        'item_title': '测试商品',
    }

    fake_client = FakeBroadcastChatClient()
    captured = []

    monkeypatch.setattr(service, 'open_chat_ws_client', lambda: asyncio.sleep(0, result=fake_client))
    monkeypatch.setattr(service, 'get_chat_ai_config', lambda: XianyuChatAiConfig(enabled=False, providers=[], active_provider_id=''))
    monkeypatch.setattr(service.chat_ai_store, 'get_active_provider', lambda: None)
    monkeypatch.setattr(service, '_get_xianyu_cookie_value', lambda: 'cookie')

    async def fake_handle_delivery_candidate_event(payload):
        captured.append(payload)

    monkeypatch.setattr(service, 'handle_delivery_candidate_event', fake_handle_delivery_candidate_event)
    monkeypatch.setattr(
        service,
        'decode_chat_push',
        lambda payload: {
            'type': 'sync',
            'items': [
                {
                    'biz_type': 40000,
                    'decoded': {
                        'raw_text': 'trade_paid_done_seller:1234567890123456',
                        'json_objects': [
                            {
                                '1': {
                                    '2': 'cid-1@goofish',
                                    '7': 1,
                                    '6': {'3': {'4': 6}},
                                    '10': {
                                        'senderUserId': '111',
                                        'detailNotice': '[已付款，待发货]',
                                        'reminderTitle': '系统消息',
                                    },
                                    '3': {'extension': {'updateKey': 'trade_paid_done_seller:1234567890123456'}},
                                }
                            }
                        ],
                    },
                }
            ],
        },
    )

    await service.ensure_chat_ai_listener()
    for _ in range(20):
        if fake_client.subscribers:
            break
        await asyncio.sleep(0.01)

    try:
        await fake_client.emit({'lwp': '/s/sync', 'body': {'syncPushPackage': {'data': []}}})
        await asyncio.sleep(0.1)
    finally:
        await service.stop_chat_ai_listener()

    assert captured == [
        {
            'order_id': '1234567890123456',
            'item_id': '1001001001',
            'buyer_id': '2002002002',
            'text': '[已付款，待发货]',
        }
    ]
