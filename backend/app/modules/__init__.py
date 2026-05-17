"""
功能模块
"""
# 延迟导入以避免循环导入
__all__ = ['douyin', 'quark']

def __getattr__(name):
    if name in __all__:
        return __import__(f"app.modules.{name}", fromlist=[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
