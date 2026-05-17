from app.modules.xianyu.service import XianyuService


def test_map_item_detail_supports_reference_item_and_seller_shape():
    service = XianyuService()
    payload = {
        "data": {
            "item": {
                "itemId": "1013621070124",
                "title": "测试宝贝",
                "price": "128",
                "originalPrice": "256",
                "desc": "这是一个测试详情",
                "pics": [
                    {"url": "//img1.test/a.jpg"},
                    {"url": "https://img2.test/b.jpg"},
                ],
                "province": "浙江",
                "city": "杭州",
                "wantCnt": 12,
                "browseCnt": 345,
                "collectCnt": 6,
                "transportFee": "0",
                "itemStatusStr": "在售",
                "gmtCreate": 1710000000000,
                "tags": ["新品", "包邮"],
                "attributes": [
                    {"name": "成色", "value": "95新"},
                    {"propertyName": "颜色", "valueName": "黑色"},
                ],
            },
            "seller": {
                "nick": "测试卖家",
                "avatar": "//avatar.test/1.jpg",
                "city": "杭州",
                "summary": "芝麻信用优秀",
                "itemCount": 9,
                "lastVisitTime": "1小时前",
                "userId": "2218736549452",
            },
        }
    }

    detail = service._map_item_detail(payload, "1013621070124")

    assert detail.item_id == "1013621070124"
    assert detail.title == "测试宝贝"
    assert detail.price == "¥128"
    assert detail.original_price == "¥256"
    assert detail.desc == "这是一个测试详情"
    assert len(detail.images) == 2
    assert detail.images[0] == "//img1.test/a.jpg" or detail.images[0] == "https:////img1.test/a.jpg"
    assert detail.seller_name == "测试卖家"
    assert detail.seller_item_count == 9
    assert detail.seller_user_id == '2218736549452'
    assert detail.want_count == 12
    assert detail.collect_count == 6
    assert len(detail.attributes) == 2
