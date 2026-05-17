"""
下载工具
"""
import os
import aiofiles
import httpx
from typing import Optional
from loguru import logger


async def download_file(
    url: str,
    file_path: str,
    chunk_size: int = 1024 * 1024,  # 1MB
    timeout: int = 60
) -> bool:
    """
    异步下载文件
    
    Args:
        url: 下载链接
        file_path: 保存路径
        chunk_size: 分块大小
        timeout: 超时时间
    
    Returns:
        是否下载成功
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("GET", url, follow_redirects=True) as response:
                response.raise_for_status()
                
                # 确保目录存在
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # 写入文件
                async with aiofiles.open(file_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size):
                        await f.write(chunk)
        
        logger.info(f"下载成功: {file_path}")
        return True
    
    except Exception as e:
        logger.error(f"下载失败: {url}, 错误: {e}")
        return False


async def download_batch(
    urls: list,
    save_dir: str,
    filenames: Optional[list] = None,
    max_concurrent: int = 3
) -> list:
    """
    批量下载文件
    
    Args:
        urls: 下载链接列表
        save_dir: 保存目录
        filenames: 文件名列表
        max_concurrent: 最大并发数
    
    Returns:
        下载结果列表
    """
    import asyncio
    
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def download_with_semaphore(url: str, file_path: str):
        async with semaphore:
            result = await download_file(url, file_path)
            return {"url": url, "path": file_path, "success": result}
    
    tasks = []
    for i, url in enumerate(urls):
        filename = filenames[i] if filenames and i < len(filenames) else f"file_{i}"
        file_path = os.path.join(save_dir, filename)
        tasks.append(download_with_semaphore(url, file_path))
    
    results = await asyncio.gather(*tasks)
    return results
