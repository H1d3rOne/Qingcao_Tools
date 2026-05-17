import socket
import time
import requests
import json
import os
import platform
import logging

logger = logging.getLogger(__name__)


def get_default_download_path() -> str:
    """
    获取系统默认下载路径
    
    Returns:
        str: 默认下载路径
        - Windows: C:\\Users\\<用户名>\\Downloads
        - macOS/Linux: ~/Downloads
    """
    system = platform.system()
    
    if system == "Windows":
        # Windows: 使用环境变量获取下载目录
        download_path = os.path.join(os.environ.get('USERPROFILE', os.path.expanduser('~')), 'Downloads')
    else:
        # macOS/Linux: ~/Downloads
        download_path = os.path.expanduser('~/Downloads')
    
    # 确保路径存在
    if not os.path.exists(download_path):
        try:
            os.makedirs(download_path, exist_ok=True)
        except Exception:
            pass
    
    return download_path


def check_rpc_connection(host='127.0.0.1', port=16800, timeout=3):
    """
    检查 RPC 端口是否可以连接
    
    Args:
        host: RPC 主机地址
        port: RPC 端口
        timeout: 连接超时时间（秒）
    
    Returns:
        bool: True 表示可以连接，False 表示无法连接
    """
    try:
        logger.info(f"检查 RPC 连接: {host}:{port}")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        connected = result == 0
        logger.info(f"RPC 连接结果: {'成功' if connected else '失败'} (返回码: {result})")
        return connected
    except Exception as e:
        logger.error(f"检查 RPC 连接异常: {e}")
        return False


def send_to_rpc(file_name: str, download_url: str, save_path: str, cookies: str = ''):
    """
    将下载任务发送到 Motrix 下载管理器的 RPC 接口
    
    Args:
        file_name: 文件名
        download_url: 下载链接
        save_path: 保存路径
        cookies: Cookie 字符串（可选）
    """
    logger.info(f"准备发送到 RPC: file_name={file_name}, save_path={save_path}")
    
    
    url = 'http://127.0.0.1:16800/jsonrpc'
    headers = {
        "Cookie": cookies
    }

    payload = {
        "id": int(time.time() * 1000),
        "jsonrpc": "2.0",
        "method": "aria2.addUri",
        "params": [
            "token:",
            [download_url],
            {
                "dir": save_path,
                "out": file_name,
                "header": [f"Cookie: {cookies}"]
            }
        ]
    }
    
    logger.info(f"发送 RPC 请求: {url}")
    logger.debug(f"RPC payload: {json.dumps(payload, ensure_ascii=False)}")
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        logger.info(f"RPC 响应: {response.text}")
    except Exception as e:
        logger.error(f"RPC 请求失败: {e}")





if __name__ == "__main__":
    file_name = "test.txt"
    download_url = "https://www.baidu.com"
    save_path = get_default_download_path()
    cookies = ""
    send_to_rpc(file_name, download_url, save_path, cookies)
