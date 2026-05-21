from pathlib import Path

from app.modules.xianyu.delivery_store import XianyuDeliveryStore
from app.modules.xianyu.schemas import XianyuDeliveryRuleCreateRequest


def test_delivery_store_rule_and_execution_roundtrip(tmp_path: Path):
    store = XianyuDeliveryStore(
        rules_path=tmp_path / "xianyu_delivery_rules.json",
        runtime_path=tmp_path / "xianyu_delivery_runtime.json",
    )

    rule = store.create_rule(
        XianyuDeliveryRuleCreateRequest(
            name="卡密发货",
            enabled=True,
            match_mode="item_id",
            item_id="1001",
            keyword="",
            delivery_text="卡密：ABC-123",
            send_chat_text=True,
            send_dummy_ship=True,
        )
    )

    assert rule.id
    assert store.list_rules()[0].name == "卡密发货"
    assert (tmp_path / "xianyu_delivery_rules.json.bak").exists()
    assert (tmp_path / "xianyu_delivery_runtime.json.bak").exists()

    toggled = store.toggle_rule(rule.id)
    assert toggled is not None
    assert toggled.enabled is False

    record = store.record_execution(
        rule_id=rule.id,
        rule_name=rule.name,
        order_id="order-1",
        item_id="1001",
        buyer_id="buyer-1",
        status="success",
        message="delivered",
    )
    assert record.status == "success"

    runtime = store.get_runtime_status()
    assert runtime.recent_success_count == 1
    assert runtime.running is False
