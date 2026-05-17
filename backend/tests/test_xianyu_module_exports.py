from app.modules.xianyu import XianyuManageItemMultiQuantityUpdateRequest


def test_xianyu_module_exports_manage_multi_quantity_request():
    assert XianyuManageItemMultiQuantityUpdateRequest.model_fields['enabled'].annotation is bool
