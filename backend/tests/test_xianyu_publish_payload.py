import asyncio

from app.modules.xianyu.service import XianyuService


def test_build_publish_payload_keeps_required_fields():
    service = XianyuService()
    payload = service._build_publish_payload(
        {
            "title": "Switch OLED",
            "desc": "成色很好",
            "price": 1299,
            "original_price": 1899,
            "category_id": "50025386",
            "condition_id": "9成新",
            "province": "浙江",
            "city": "杭州",
            "shipping_mode": "seller",
            "free_shipping": True,
            "image_ids": ["img-1", "img-2"],
            "attribute_values": {"brand": "Nintendo"},
        }
    )

    assert payload["title"] == "Switch OLED"
    assert payload["price"] == 1299
    assert payload["image_ids"] == ["img-1", "img-2"]
    assert payload["attribute_values"]["brand"] == "Nintendo"


def test_build_publish_payload_rejects_empty_images():
    service = XianyuService()
    try:
        service._build_publish_payload(
            {
                "title": "iPhone",
                "desc": "desc",
                "price": 100,
                "category_id": "1",
                "condition_id": "95新",
                "province": "浙江",
                "city": "杭州",
                "shipping_mode": "seller",
                "image_ids": [],
            }
        )
    except ValueError as exc:
        assert "至少上传一张图片" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_submit_publish_returns_item_id(monkeypatch):
    service = XianyuService()

    async def fake_call(*args, **kwargs):
        return {
            "data": {
                "itemId": "987654321",
                "detailUrl": "https://www.goofish.com/item?id=987654321",
            }
        }

    monkeypatch.setattr(service, "_call_publish_submit_api", fake_call)

    result = asyncio.run(
        service.submit_publish(
            {
                "title": "Switch OLED",
                "desc": "成色很好",
                "price": 1299,
                "category_id": "50025386",
                "condition_id": "9成新",
                "province": "浙江",
                "city": "杭州",
                "shipping_mode": "seller",
                "image_ids": ["img-1"],
                "attribute_values": {},
            }
        )
    )

    assert result.item_id == "987654321"
    assert "987654321" in result.detail_url
