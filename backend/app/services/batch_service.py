"""
批处理服务

管理批处理任务和批处理项。
"""

from uuid import UUID
from typing import Optional
from datetime import datetime

from sqlalchemy import select, and_, desc

from .base import BaseService
from app.models.database import BatchJob, BatchItem, BatchJobStatus, BatchItemStatus
from app.models.schemas import BatchJobCreate


class BatchService(BaseService):
    """批处理服务

    管理批处理任务的创建、查询和取消。
    实际执行在 Phase 6 通过 Celery 实现。
    """

    # =========================================================================
    # 批处理任务管理
    # =========================================================================

    async def create_batch_job(
        self,
        user_id: UUID,
        data: BatchJobCreate
    ) -> BatchJob:
        """创建批处理任务

        Args:
            user_id: 用户 ID
            data: 批处理任务创建数据

        Returns:
            创建的批处理任务
        """
        self.logger.info(f"Creating batch job for user {user_id}")

        # 创建批处理任务
        batch_job = BatchJob(
            user_id=user_id,
            name=data.name,
            description=data.description,
            status=BatchJobStatus.pending,
            total_items=len(data.items),
            completed_items=0,
            failed_items=0,
        )
        self.db.add(batch_job)
        await self.db.flush()

        # 创建批处理项
        for item_data in data.items:
            batch_item = BatchItem(
                batch_job_id=batch_job.id,
                input_data=item_data.input_data,
                status=BatchItemStatus.pending,
            )
            self.db.add(batch_item)

        await self.db.commit()
        await self.db.refresh(batch_job)

        self.logger.info(f"Batch job created: {batch_job.id}")

        # TODO: 在 Phase 6 通过 Celery 触发实际执行

        return batch_job

    async def get_batch_job(
        self,
        batch_id: UUID,
        user_id: UUID
    ) -> Optional[BatchJob]:
        """获取批处理任务

        Args:
            batch_id: 批处理任务 ID
            user_id: 用户 ID

        Returns:
            批处理任务或 None
        """
        stmt = select(BatchJob).where(
            and_(
                BatchJob.id == batch_id,
                BatchJob.user_id == user_id
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_batch_jobs(
        self,
        user_id: UUID,
        status: Optional[BatchJobStatus] = None
    ) -> list[BatchJob]:
        """列出批处理任务

        Args:
            user_id: 用户 ID
            status: 状态筛选

        Returns:
            批处理任务列表
        """
        conditions = [BatchJob.user_id == user_id]
        if status:
            conditions.append(BatchJob.status == status)

        stmt = (
            select(BatchJob)
            .where(and_(*conditions))
            .order_by(desc(BatchJob.created_at))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def cancel_batch_job(
        self,
        batch_id: UUID,
        user_id: UUID
    ) -> BatchJob:
        """取消批处理任务

        Args:
            batch_id: 批处理任务 ID
            user_id: 用户 ID

        Returns:
            更新后的批处理任务

        Raises:
            ValueError: 任务不存在
        """
        batch_job = await self.get_batch_job(batch_id, user_id)
        if not batch_job:
            raise ValueError(f"Batch job {batch_id} not found")

        # 设置任务状态为已取消
        batch_job.status = BatchJobStatus.cancelled
        batch_job.updated_at = datetime.utcnow()

        # 取消未处理的项
        stmt = select(BatchItem).where(
            and_(
                BatchItem.batch_job_id == batch_id,
                BatchItem.status == BatchItemStatus.pending
            )
        )
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        for item in items:
            item.status = BatchItemStatus.skipped

        await self.db.commit()
        await self.db.refresh(batch_job)

        self.logger.info(f"Batch job cancelled: {batch_id}")
        return batch_job

    # =========================================================================
    # 批处理项管理
    # =========================================================================

    async def get_batch_items(
        self,
        batch_id: UUID,
        user_id: UUID,
        status: Optional[BatchItemStatus] = None
    ) -> list[BatchItem]:
        """获取批处理项列表

        Args:
            batch_id: 批处理任务 ID
            user_id: 用户 ID
            status: 状态筛选

        Returns:
            批处理项列表

        Raises:
            ValueError: 任务不存在
        """
        # 验证任务归属
        batch_job = await self.get_batch_job(batch_id, user_id)
        if not batch_job:
            raise ValueError(f"Batch job {batch_id} not found")

        conditions = [BatchItem.batch_job_id == batch_id]
        if status:
            conditions.append(BatchItem.status == status)

        stmt = select(BatchItem).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_batch_item(
        self,
        item_id: UUID,
        status: BatchItemStatus,
        output: Optional[dict] = None,
        error: Optional[str] = None
    ) -> BatchItem:
        """更新批处理项

        Args:
            item_id: 批处理项 ID
            status: 新状态
            output: 输出数据
            error: 错误信息

        Returns:
            更新后的批处理项

        Raises:
            ValueError: 项不存在
        """
        stmt = select(BatchItem).where(BatchItem.id == item_id)
        result = await self.db.execute(stmt)
        item = result.scalar_one_or_none()

        if not item:
            raise ValueError(f"Batch item {item_id} not found")

        # 更新项状态
        item.status = status
        item.output_data = output
        item.error_message = error
        item.updated_at = datetime.utcnow()

        # 更新父任务计数
        batch_job_stmt = select(BatchJob).where(BatchJob.id == item.batch_job_id)
        batch_job_result = await self.db.execute(batch_job_stmt)
        batch_job = batch_job_result.scalar_one_or_none()

        if batch_job:
            if status == BatchItemStatus.completed:
                batch_job.completed_items += 1
            elif status == BatchItemStatus.failed:
                batch_job.failed_items += 1

            # 检查是否所有项都已完成
            if (batch_job.completed_items + batch_job.failed_items) >= batch_job.total_items:
                if batch_job.failed_items == 0:
                    batch_job.status = BatchJobStatus.completed
                else:
                    batch_job.status = BatchJobStatus.failed

        await self.db.commit()
        await self.db.refresh(item)

        return item

    async def get_batch_progress(
        self,
        batch_id: UUID,
        user_id: UUID
    ) -> dict:
        """获取批处理进度

        Args:
            batch_id: 批处理任务 ID
            user_id: 用户 ID

        Returns:
            进度信息字典

        Raises:
            ValueError: 任务不存在
        """
        batch_job = await self.get_batch_job(batch_id, user_id)
        if not batch_job:
            raise ValueError(f"Batch job {batch_id} not found")

        total = batch_job.total_items
        completed = batch_job.completed_items
        failed = batch_job.failed_items
        pending = total - completed - failed

        progress_percentage = (completed + failed) / total * 100 if total > 0 else 0

        return {
            "batch_id": str(batch_id),
            "status": batch_job.status.value,
            "total_items": total,
            "completed_items": completed,
            "failed_items": failed,
            "pending_items": pending,
            "progress_percentage": round(progress_percentage, 2),
        }
