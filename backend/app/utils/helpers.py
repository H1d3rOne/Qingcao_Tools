"""
辅助工具函数
"""
import re
from typing import Optional
from datetime import datetime


def format_timestamp(timestamp: int) -> str:
    """格式化时间戳"""
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ""


def format_number(num: int) -> str:
    """格式化数字（万、亿）"""
    if num >= 100000000:
        return f"{num / 100000000:.1f}亿"
    elif num >= 10000:
        return f"{num / 10000:.1f}万"
    return str(num)


def clean_text(text: str) -> str:
    """清理文本（去除多余空白和换行）"""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


def truncate_text(text: str, max_length: int = 100) -> str:
    """截断文本"""
    if not text or len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def extract_urls(text: str) -> list:
    """从文本中提取URL"""
    pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(pattern, text)


def validate_douyin_url(url: str) -> tuple[bool, str]:
    """
    验证抖音URL
    
    Returns:
        (是否有效, 类型: video/user/live)
    """
    patterns = {
        "video": [
            r'douyin\.com/video/\d+',
            r'douyin\.com/\?modal_id=\d+',
            r'v\.douyin\.com/[A-Za-z0-9]+',
        ],
        "user": [
            r'douyin\.com/user/[A-Za-z0-9_-]+',
        ],
        "live": [
            r'live\.douyin\.com/\d+',
        ]
    }
    
    for url_type, pattern_list in patterns.items():
        for pattern in pattern_list:
            if re.search(pattern, url):
                return True, url_type
    
    return False, "unknown"
