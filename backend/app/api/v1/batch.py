"""
批处理端点

提供批处理任务的创建、查询、取消和进度跟踪
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_current_user_auth, get_batch_service
from app.models.schemas import (
    BatchJobCreate,
    BatchJobResponse,
    BatchItemResponse,
    BatchJobStatus,
    BatchItemStatus,
)
from app.services.batch_service import BatchService
from app.utils.logging import get_logger

router = APIRouter(prefix="/batch", tags=["batch"])
logger = get_logger(__name__)


@router.post("", response_model=BatchJobResponse)
async def create_batch_job(
    data: BatchJobCreate,
    user_id: UUID = Depends(get_current_user_auth),
    batch_service: BatchService = Depends(get_batch_service),
) -> BatchJobResponse:
    """创建批处理任务"""
    job = await batch_service.create_batch_job(user_id, data)
    return BatchJobResponse.from_orm(job)


@router.get("", response_model=list[BatchJobResponse])
async def list_batch_jobs(
    status: BatchJobStatus | None = Query(None, description="状态筛选"),
    user_id: UUID = Depends(get_current_user_auth),
    batch_service: BatchService = Depends(get_batch_service),
) -> list[BatchJobResponse]:
    """列出批处理任务"""
    jobs = await batch_service.list_batch_jobs(user_id, status)
    return [BatchJobResponse.from_orm(job) for job in jobs]


@router.get("/{batch_id}", response_model=BatchJobResponse)
async def get_batch_job(
    batch_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    batch_service: BatchService = Depends(get_batch_service),
) -> BatchJobResponse:
    """获取批处理任务详情"""
    job = await batch_service.get_batch_job(batch_id, user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")

    return BatchJobResponse.from_orm(job)


@router.get("/{batch_id}/status")
async def get_batch_status(
    batch_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    batch_service: BatchService = Depends(get_batch_service),
) -> dict:
    """获取批处理进度"""
    progress = await batch_service.get_batch_progress(batch_id, user_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Batch job not found")

    return progress


@router.post("/{batch_id}/cancel", response_model=BatchJobResponse)
async def cancel_batch_job(
    batch_id: UUID,
    user_id: UUID = Depends(get_current_user_auth),
    batch_service: BatchService = Depends(get_batch_service),
) -> BatchJobResponse:
    """取消批处理任务"""
    job = await batch_service.cancel_batch_job(batch_id, user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")

    return BatchJobResponse.from_orm(job)


@router.get("/{batch_id}/items", response_model=list[BatchItemResponse])
async def get_batch_items(
    batch_id: UUID,
    status: BatchItemStatus | None = Query(None, description="状态筛选"),
    user_id: UUID = Depends(get_current_user_auth),
    batch_service: BatchService = Depends(get_batch_service),
) -> list[BatchItemResponse]:
    """获取批处理项列表"""
    items = await batch_service.get_batch_items(batch_id, user_id, status)
    return [BatchItemResponse.from_orm(item) for item in items]
