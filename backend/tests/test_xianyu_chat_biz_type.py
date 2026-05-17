"""Guard the biz_type=40 path for incoming chat messages.

生产日志里观察到推送的 bizType 是 40，不是文档写的 40000。参考项目
XianYuApis.goofish_live.handle_message 本来就不过滤 bizType。这里锁定
`_extract_ai_candidate` 对 40 和 40000 都能识别为新消息候选。
"""
from __future__ import annotations

from app.modules.xianyu.service import XianyuService


def _make_item(biz_type: int) -> dict:
    return {
        "biz_type": biz_type,
        "decoded": {
            "raw_text": f"raw-{biz_type}",
            "json_objects": [
                {
                    "1": {
                        "2": "60613035186@goofish",
                        "10": {
                            "senderUserId": "824092266",
                            "reminderContent": "莫多想",
                            "reminderTitle": "呵呵是你想太多",
                        },
                    }
                }
            ],
        },
    }


def test_extract_candidate_accepts_biz_type_40():
    svc = XianyuService()
    candidate = svc._extract_ai_candidate(_make_item(40))
    assert candidate is not None
    assert candidate["text"] == "莫多想"
    assert candidate["sender_uid"] == "824092266"
    assert candidate["sender_name"] == "呵呵是你想太多"
    assert candidate["cid"] == "60613035186@goofish"


def test_extract_candidate_accepts_biz_type_40000():
    svc = XianyuService()
    candidate = svc._extract_ai_candidate(_make_item(40000))
    assert candidate is not None
    assert candidate["text"] == "莫多想"


def test_extract_candidate_rejects_typing_indicator():
    svc = XianyuService()
    # bizType=40006 is typing change, never an AI reply target.
    candidate = svc._extract_ai_candidate(_make_item(40006))
    assert candidate is None


def test_extract_candidate_rejects_read_receipt():
    svc = XianyuService()
    # bizType=40102 is read receipt, not a new message.
    candidate = svc._extract_ai_candidate(_make_item(40102))
    assert candidate is None
