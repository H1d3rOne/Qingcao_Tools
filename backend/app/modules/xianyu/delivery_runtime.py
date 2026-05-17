from __future__ import annotations

from app.modules.xianyu.delivery_store import XianyuDeliveryStore
from app.modules.xianyu.item_store import XianyuItemStore


class XianyuDeliveryRuntime:
    def __init__(self, *, item_store: XianyuItemStore, delivery_store: XianyuDeliveryStore):
        self.item_store = item_store
        self.delivery_store = delivery_store

    async def process_event(self, event: dict, executor) -> None:
        order_id = str((event or {}).get("order_id") or "").strip()
        item_id = str((event or {}).get("item_id") or "").strip()
        buyer_id = str((event or {}).get("buyer_id") or "").strip()
        text = str((event or {}).get("text") or "").strip()
        self.delivery_store.mark_runtime_event()

        matched = next(
            (
                rule
                for rule in self.delivery_store.list_rules()
                if rule.enabled
                and (
                    (rule.match_mode == "item_id" and rule.item_id and rule.item_id == item_id)
                    or (rule.match_mode == "keyword" and rule.keyword and rule.keyword in text)
                )
            ),
            None,
        )
        if matched is None:
            self.delivery_store.record_execution(
                rule_id="",
                rule_name="",
                order_id=order_id,
                item_id=item_id,
                buyer_id=buyer_id,
                status="skipped",
                message="no matching rule",
            )
            return

        if not order_id or not item_id or not buyer_id:
            self.delivery_store.record_execution(
                rule_id=matched.id,
                rule_name=matched.name,
                order_id=order_id,
                item_id=item_id,
                buyer_id=buyer_id,
                status="skipped",
                message="missing required fields",
            )
            return

        try:
            await executor.send_chat_and_ship(
                order_id=order_id,
                item_id=item_id,
                buyer_id=buyer_id,
                delivery_text=matched.delivery_text,
            )
            self.delivery_store.record_execution(
                rule_id=matched.id,
                rule_name=matched.name,
                order_id=order_id,
                item_id=item_id,
                buyer_id=buyer_id,
                status="success",
                message="delivered",
            )
        except Exception as exc:
            self.delivery_store.record_execution(
                rule_id=matched.id,
                rule_name=matched.name,
                order_id=order_id,
                item_id=item_id,
                buyer_id=buyer_id,
                status="failed",
                message=str(exc),
            )
            raise
