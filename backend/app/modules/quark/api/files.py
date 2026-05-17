from fastapi import APIRouter, HTTPException, Query, File, UploadFile, Form, Body
from typing import Optional, List

from pydantic import BaseModel

from app.modules.quark.schemas import (
    FileListRequest,
    FileListResponse,
    CreateFolderRequest,
    DeleteFilesRequest,
    RenameFileRequest,
    MoveFilesRequest,
    SearchFilesRequest,
    StorageInfoResponse,
    CreateShareRequest,
    ShareResponse,
    UploadLocalFileRequest,
)
from app.modules.quark.services import quark_service

router = APIRouter(prefix="/files", tags=["文件管理"])


# 分享转存请求模型
class TransferShareRequest(BaseModel):
    share_id: str
    passcode: Optional[str] = None
    file_ids: List[str]
    share_fid_tokens: List[str] = []  # 文件对应的token列表
    target_folder_id: Optional[str] = None
    pdir_fid: str = "0"  # 源目录ID，根目录为"0"
    token: Optional[str] = None  # 访问令牌（必须与share_fid_tokens配对）


# 分享下载请求模型
class DownloadShareRequest(BaseModel):
    share_id: str
    passcode: Optional[str] = None
    file_ids: List[str]
    token: Optional[str] = None  # 访问令牌（可选）
    mode: Optional[str] = "clean"  # 下载模式: keep=保存下载, clean=无痕下载
    target_folder_id: Optional[str] = None  # 目标文件夹ID（可选，默认使用"来自：分享"）


@router.get("/user-info")
async def get_user_info():
    """获取用户信息"""
    result = quark_service.get_user_info()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.get("/list", response_model=FileListResponse)
async def list_files(
    folder_id: str = Query("0", description="文件夹 ID"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(50, ge=1, le=200, description="每页数量"),
):
    """获取文件列表"""
    result = quark_service.list_files(folder_id=folder_id, page=page, size=size)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return FileListResponse(
        success=result["success"],
        data=result.get("data"),
        message=result.get("message"),
    )


@router.post("/folder", response_model=FileListResponse)
async def create_folder(request: CreateFolderRequest):
    """创建文件夹"""
    result = quark_service.create_folder(
        folder_name=request.folder_name,
        parent_id=request.parent_id,
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return FileListResponse(
        success=result["success"],
        data=result.get("data"),
        message=result.get("message"),
    )


@router.delete("/delete", response_model=FileListResponse)
async def delete_files(request: DeleteFilesRequest):
    """删除文件"""
    result = quark_service.delete_files(file_ids=request.file_ids)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return FileListResponse(
        success=result["success"],
        data=result.get("data"),
        message=result.get("message"),
    )


@router.put("/rename", response_model=FileListResponse)
async def rename_file(request: RenameFileRequest):
    """重命名文件"""
    result = quark_service.rename_file(
        file_id=request.file_id,
        new_name=request.new_name,
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return FileListResponse(
        success=result["success"],
        data=result.get("data"),
        message=result.get("message"),
    )


@router.post("/move", response_model=FileListResponse)
async def move_files(request: MoveFilesRequest):
    """移动文件"""
    result = quark_service.move_files(
        file_ids=request.file_ids,
        target_folder_id=request.target_folder_id,
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return FileListResponse(
        success=result["success"],
        data=result.get("data"),
        message=result.get("message"),
    )


@router.get("/search", response_model=FileListResponse)
async def search_files(
    keyword: str = Query(..., description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(50, ge=1, le=200, description="每页数量"),
):
    """搜索文件"""
    result = quark_service.search_files(keyword=keyword, page=page, size=size)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return FileListResponse(
        success=result["success"],
        data=result.get("data"),
        message=result.get("message"),
    )


@router.get("/storage", response_model=StorageInfoResponse)
async def get_storage_info():
    """获取存储信息"""
    result = quark_service.get_storage_info()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return StorageInfoResponse(
        success=result["success"],
        data=result.get("data"),
        message=result.get("message"),
    )


@router.get("/download/{file_id}")
async def get_download_url(
    file_id: str,
    file_name: Optional[str] = Query(None, description="文件名"),
    save_path: Optional[str] = Query(None, description="保存路径"),
):
    """获取文件下载链接
    
    - 如果 RPC 服务(Motrix)开启，将发送到 RPC 下载
    - 如果 RPC 服务未开启，返回下载链接供浏览器下载
    """
    result = quark_service.get_download_url(
        file_id=file_id,
        file_name=file_name,
        save_path=save_path
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.get("/download-folder/{folder_id}")
async def download_folder(
    folder_id: str,
    folder_name: Optional[str] = Query(None, description="文件夹名"),
    save_path: Optional[str] = Query(None, description="保存路径"),
):
    """下载文件夹（递归下载所有子文件和子文件夹）
    
    - 需要开启 RPC 服务（Motrix）
    - 自动创建文件夹结构
    - 递归下载所有内容
    """
    result = quark_service.download_folder(
        folder_id=folder_id,
        folder_name=folder_name,
        save_path=save_path
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.get("/tree")
async def get_folder_tree(
    folder_id: str = Query("0", description="文件夹 ID"),
    max_depth: int = Query(3, ge=1, le=5, description="最大深度"),
):
    """获取文件夹树"""
    result = quark_service.get_folder_tree(folder_id=folder_id, max_depth=max_depth)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    # 直接返回结果，不使用 response_model
    return result


@router.post("/share", response_model=ShareResponse)
async def create_share(request: CreateShareRequest):
    """创建分享链接"""
    result = quark_service.create_share(
        file_ids=request.file_ids,
        title=request.title,
        expire_days=request.expire_days,
        password=request.password,
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return ShareResponse(
        success=result["success"],
        data=result.get("data"),
        message=result.get("message"),
    )


@router.get("/shares", response_model=ShareResponse)
async def get_my_shares(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(50, ge=1, le=200, description="每页数量"),
):
    """获取我的分享列表"""
    result = quark_service.get_my_shares(page=page, size=size)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return ShareResponse(
        success=result["success"],
        data=result.get("data"),
        message=result.get("message"),
    )


@router.delete("/share/{share_id}", response_model=ShareResponse)
async def delete_share(share_id: str):
    """删除分享"""
    result = quark_service.delete_share(share_id=share_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return ShareResponse(
        success=result["success"],
        data=result.get("data"),
        message=result.get("message"),
    )


@router.get("/share-info")
async def get_share_info(
    share_id: str = Query(..., description="分享ID"),
    passcode: Optional[str] = Query(None, description="提取码"),
    pdir_fid: str = Query("0", description="父目录ID，根目录为0"),
    token: Optional[str] = Query(None, description="访问令牌（可选，用于浏览子目录）"),
):
    """获取分享链接信息
    
    - 首次调用不需要传 token，会返回 token 用于后续浏览子目录
    - 浏览子目录时传入 token 和 pdir_fid
    """
    result = quark_service.get_share_info(
        share_id=share_id, 
        passcode=passcode, 
        pdir_fid=pdir_fid,
        token=token
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.post("/transfer-share")
async def transfer_share(request: TransferShareRequest):
    """转存分享文件到网盘"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[DEBUG] API接收参数: token={request.token}, share_fid_tokens={request.share_fid_tokens}")
    
    result = quark_service.transfer_share(
        share_id=request.share_id,
        passcode=request.passcode,
        file_ids=request.file_ids,
        share_fid_tokens=request.share_fid_tokens,
        target_folder_id=request.target_folder_id,
        pdir_fid=request.pdir_fid,
        token=request.token,
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.post("/download-share")
async def download_share(request: DownloadShareRequest):
    """下载分享文件（支持文件和文件夹递归下载）
    
    模式说明：
    - keep: 保存下载 - 转存到目标文件夹后下载，保留在网盘中
    - clean: 无痕下载 - 转存后下载，下载完成自动删除转存的文件
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[DEBUG] download_share API接收参数:")
    logger.info(f"[DEBUG]   share_id: {request.share_id}")
    logger.info(f"[DEBUG]   file_ids: {request.file_ids}")
    logger.info(f"[DEBUG]   token: {request.token}")
    logger.info(f"[DEBUG]   mode: {request.mode}")
    logger.info(f"[DEBUG]   target_folder_id: {request.target_folder_id}")
    
    result = quark_service.download_share(
        share_id=request.share_id,
        passcode=request.passcode,
        file_ids=request.file_ids,
        token=request.token,
        mode=request.mode,
        target_folder_id=request.target_folder_id,
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    parent_folder_id: Optional[str] = Form(None)
):
    """上传文件到夸克网盘
    
    Args:
        file: 上传的文件
        parent_folder_id: 目标文件夹ID（可选，默认为"夸克上传文件"文件夹）
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[DEBUG] 上传文件: {file.filename}, parent_folder_id: {parent_folder_id}")
    
    # 读取文件内容
    file_content = await file.read()
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    
    result = quark_service.upload_file(
        file_content=file_content,
        file_name=file.filename,
        parent_folder_id=parent_folder_id
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.post("/upload-raw")
async def upload_file_raw(
    file_name: str = Query(..., description="文件名"),
    parent_folder_id: Optional[str] = Query(None, description="目标文件夹ID"),
    relative_path: Optional[str] = Query(None, description="相对路径，用于重建文件夹树"),
    file_content: bytes = Body(..., media_type="application/octet-stream")
):
    """通过原始字节流上传文件到夸克网盘

    用于回避部分浏览器/WebView 对 multipart/form-data 上传的拦截。
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(
        f"[DEBUG] 原始上传文件: {file_name}, parent_folder_id: {parent_folder_id}, relative_path: {relative_path}, size: {len(file_content)}"
    )

    if not file_name:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    result = quark_service.upload_file_with_path(
        file_content=file_content,
        file_name=file_name,
        parent_folder_id=parent_folder_id,
        relative_path=relative_path
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@router.post("/upload-local")
async def upload_local_file(request: UploadLocalFileRequest):
    """通过本地文件绝对路径上传到夸克网盘"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(
        f"[DEBUG] 本地路径上传文件: {request.local_path}, parent_folder_id: {request.parent_folder_id}, relative_path: {request.relative_path}"
    )

    result = quark_service.upload_local_file(
        local_path=request.local_path,
        parent_folder_id=request.parent_folder_id,
        relative_path=request.relative_path
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return result
