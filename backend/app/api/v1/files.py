"""
文件管理端点

提供文件上传、下载、列表和删除功能
"""
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.dependencies import get_current_user_auth, get_file_service
from app.models.schemas import FileResponse, FileUploadResponse, FileType
from app.services.file_service import FileService
from app.utils.logging import get_logger

router = APIRouter(prefix="/files", tags=["files"])
logger = get_logger(__name__)


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_current_user_auth),
    file_service: FileService = Depends(get_file_service),
) -> FileUploadResponse:
    """上传文件"""
    try:
        uploaded_file = await file_service.upload_file(user_id, file)
        return FileUploadResponse.from_orm(uploaded_file)
    except ValueError as e:
        # 文件验证失败
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"File upload failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="File upload failed")


@router.get("", response_model=list[FileResponse])
async def list_files(
    file_type: FileType | None = Query(None, description="文件类型筛选"),
    user_id: UUID = Depends(get_current_user_auth),
    file_service: FileService = Depends(get_file_service),
) -> list[FileResponse]:
    """列出用户文件"""
    files = await file_service.list_files(user_id, file_type)
    return [FileResponse.from_orm(f) for f in files]


@router.get("/{file_id}", response_model=FileResponse)
async def get_file_info(
    file_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    file_service: FileService = Depends(get_file_service),
) -> FileResponse:
    """获取文件信息"""
    file = await file_service.get_file(file_id, user_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse.from_orm(file)


@router.get("/{file_id}/download")
async def download_file(
    file_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    file_service: FileService = Depends(get_file_service),
) -> StreamingResponse:
    """下载文件内容"""
    # 获取文件信息
    file = await file_service.get_file(file_id, user_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # 读取文件内容
    try:
        content = await file_service.get_file_content(file_id, user_id)

        # 返回文件流
        def iterfile():
            yield content

        return StreamingResponse(
            iterfile(),
            media_type=file.mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{file.name}"',
                "Content-Length": str(file.size),
            },
        )
    except Exception as e:
        logger.error(f"File download failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="File download failed")


@router.delete("/{file_id}")
async def delete_file(
    file_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    file_service: FileService = Depends(get_file_service),
) -> dict:
    """删除文件"""
    success = await file_service.delete_file(file_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")

    return {"success": True}
