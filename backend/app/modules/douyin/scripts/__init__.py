"""
抖音模块脚本文件
"""
from pathlib import Path

# 脚本文件目录
SCRIPTS_DIR = Path(__file__).parent

# 导入 protobuf 编译后的模块
try:
    from app.modules.douyin.scripts import Live_pb2
except ImportError:
    Live_pb2 = None
