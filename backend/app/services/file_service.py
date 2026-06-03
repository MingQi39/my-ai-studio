"""
文件服务

处理文件上传、读取和删除。
"""

from uuid import UUID, uuid4
from typing import Optional
from pathlib import Path
import base64
import os
import mimetypes

from fastapi import UploadFile
from sqlalchemy import select, and_

from .base import BaseService
from app.models.database import File, FileType
from app.models.schemas import FileCreate


# 文件类型映射
MIME_TYPE_MAP = {
    # 图片
    "image/jpeg": FileType.image,
    "image/png": FileType.image,
    "image/gif": FileType.image,
    "image/webp": FileType.image,
    # 视频
    "video/mp4": FileType.video,
    "video/mpeg": FileType.video,
    "video/webm": FileType.video,
    # 音频
    "audio/mpeg": FileType.audio,
    "audio/wav": FileType.audio,
    "audio/ogg": FileType.audio,
    # 文档
    "application/pdf": FileType.document,
    "text/plain": FileType.document,
}

# 最大文件大小 (500MB)
MAX_FILE_SIZE = 500 * 1024 * 1024


class FileService(BaseService):
    """文件服务

    管理文件上传、存储和访问。
    """

    def __init__(self, db, upload_dir: str = "./storage/uploads"):
        super().__init__(db)
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # 文件上传
    # =========================================================================

    async def upload_file(
        self,
        user_id: UUID,
        file: UploadFile
    ) -> File:
        """上传文件

        Args:
            user_id: 用户 ID
            file: 上传的文件

        Returns:
            文件记录

        Raises:
            ValueError: 文件验证失败
        """
        self.logger.info(f"Uploading file for user {user_id}: {file.filename}")

        # 验证文件
        file_type = await self._validate_file(file)

        # 生成文件 ID 和存储路径
        file_id = uuid4()
        extension = Path(file.filename).suffix
        storage_path = self._generate_storage_path(user_id, file_id, extension)

        # 保存文件到磁盘
        file_size = await self._save_file_to_disk(file, storage_path)

        # 提取元数据
        metadata = await self._extract_metadata(storage_path, file_type)

        # 生成访问 URL (使用完整URL以便前端直接访问)
        from app.config import settings
        # 在开发环境使用localhost,生产环境应该使用实际域名
        host = "localhost" if settings.HOST == "0.0.0.0" else settings.HOST
        base_url = f"http://{host}:{settings.PORT}" if settings.is_development else ""
        file_url = f"{base_url}/api/v1/files/{file_id}/download"

        # 对于图片类型,生成base64 data URL以便前端直接显示(避免认证问题)
        if file_type == FileType.image:
            with open(storage_path, "rb") as f:
                file_content = f.read()
                base64_data = base64.b64encode(file_content).decode()
                file_url = f"data:{file.content_type};base64,{base64_data}"

        # 创建数据库记录
        db_file = File(
            id=str(file_id),
            user_id=str(user_id),
            name=file.filename,
            type=file_type,
            mime_type=file.content_type,
            size=file_size,
            storage_path=str(storage_path),
            url=file_url,
            file_metadata=metadata,
        )
        self.db.add(db_file)
        await self.db.commit()
        await self.db.refresh(db_file)

        self.logger.info(f"File uploaded: {file_id}")
        return db_file

    async def _validate_file(self, file: UploadFile) -> FileType:
        """验证文件

        Args:
            file: 上传的文件

        Returns:
            文件类型

        Raises:
            ValueError: 文件验证失败
        """
        # 检查 MIME 类型
        mime_type = file.content_type
        if mime_type not in MIME_TYPE_MAP:
            raise ValueError(f"Unsupported file type: {mime_type}")

        file_type = MIME_TYPE_MAP[mime_type]

        # 检查文件大小
        file.file.seek(0, 2)  # 移动到文件末尾
        file_size = file.file.tell()
        file.file.seek(0)  # 重置到开头

        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {file_size} bytes (max {MAX_FILE_SIZE})")

        return file_type

    def _generate_storage_path(
        self,
        user_id: UUID,
        file_id: UUID,
        extension: str
    ) -> Path:
        """生成存储路径

        Args:
            user_id: 用户 ID
            file_id: 文件 ID
            extension: 文件扩展名

        Returns:
            存储路径
        """
        user_dir = self.upload_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        return user_dir / f"{file_id}{extension}"

    async def _save_file_to_disk(
        self,
        file: UploadFile,
        storage_path: Path
    ) -> int:
        """保存文件到磁盘

        Args:
            file: 上传的文件
            storage_path: 存储路径

        Returns:
            文件大小（字节）
        """
        file_size = 0
        with open(storage_path, "wb") as f:
            while chunk := await file.read(8192):
                f.write(chunk)
                file_size += len(chunk)

        return file_size

    async def _extract_metadata(
        self,
        file_path: Path,
        file_type: FileType
    ) -> dict:
        """提取文件元数据

        Args:
            file_path: 文件路径
            file_type: 文件类型

        Returns:
            元数据字典
        """
        metadata = {}

        try:
            if file_type == FileType.image:
                # 提取图片元数据
                try:
                    from PIL import Image
                    with Image.open(file_path) as img:
                        metadata["width"] = img.width
                        metadata["height"] = img.height
                        metadata["format"] = img.format
                except ImportError:
                    self.logger.warning("PIL not installed, skipping image metadata extraction")
                except Exception as e:
                    self.logger.warning(f"Failed to extract image metadata: {e}")

            elif file_type == FileType.video:
                # TODO: 提取视频元数据
                pass

            elif file_type == FileType.audio:
                # TODO: 提取音频元数据
                pass

            elif file_type == FileType.document:
                # TODO: 提取文档元数据
                pass

        except Exception as e:
            self.logger.warning(f"Failed to extract metadata: {e}")

        return metadata

    # =========================================================================
    # 文件读取
    # =========================================================================

    async def get_file(
        self,
        file_id: UUID,
        user_id: UUID
    ) -> Optional[File]:
        """获取文件信息

        Args:
            file_id: 文件 ID
            user_id: 用户 ID

        Returns:
            文件对象或 None
        """
        stmt = select(File).where(
            and_(
                File.id == file_id,
                File.user_id == user_id
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_file_content(
        self,
        file_id: UUID,
        user_id: UUID
    ) -> bytes:
        """获取文件内容

        Args:
            file_id: 文件 ID
            user_id: 用户 ID

        Returns:
            文件内容

        Raises:
            ValueError: 文件不存在
            FileNotFoundError: 文件在磁盘上不存在
        """
        file = await self.get_file(file_id, user_id)
        if not file:
            raise ValueError(f"File {file_id} not found")

        storage_path = Path(file.storage_path)
        if not storage_path.exists():
            raise FileNotFoundError(f"File not found on disk: {storage_path}")

        with open(storage_path, "rb") as f:
            return f.read()

    async def get_file_base64(
        self,
        file_id: UUID,
        user_id: UUID
    ) -> str:
        """获取文件的 Base64 编码

        Args:
            file_id: 文件 ID
            user_id: 用户 ID

        Returns:
            Base64 编码的文件内容
        """
        content = await self.get_file_content(file_id, user_id)
        return base64.b64encode(content).decode()

    async def list_files(
        self,
        user_id: UUID,
        file_type: Optional[FileType] = None
    ) -> list[File]:
        """列出文件

        Args:
            user_id: 用户 ID
            file_type: 文件类型筛选

        Returns:
            文件列表
        """
        conditions = [File.user_id == user_id]
        if file_type:
            conditions.append(File.file_type == file_type)

        stmt = select(File).where(and_(*conditions)).order_by(File.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # =========================================================================
    # 文件删除
    # =========================================================================

    async def delete_file(
        self,
        file_id: UUID,
        user_id: UUID
    ) -> bool:
        """删除文件

        Args:
            file_id: 文件 ID
            user_id: 用户 ID

        Returns:
            是否删除成功
        """
        file = await self.get_file(file_id, user_id)
        if not file:
            return False

        # TODO: 检查是否被消息引用

        # 删除磁盘文件
        storage_path = Path(file.storage_path)
        if storage_path.exists():
            storage_path.unlink()

        # 删除数据库记录
        await self.db.delete(file)
        await self.db.commit()

        self.logger.info(f"File deleted: {file_id}")
        return True

    async def cleanup_orphan_files(self) -> int:
        """清理孤立文件

        Returns:
            删除的文件数量
        """
        # TODO: 查找无引用的文件并删除
        count = 0
        self.logger.info(f"Cleaned up {count} orphan files")
        return count
