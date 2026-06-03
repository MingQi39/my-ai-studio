"""SQLAlchemy ORM models.

This module defines all database models for the application.
Models use UUID primary keys and include timestamp mixins.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


# =============================================================================
# Enums
# =============================================================================


class MessageRole(str, enum.Enum):
    """Message role enumeration."""

    user = "user"
    assistant = "assistant"
    system = "system"


class AdapterType(str, enum.Enum):
    """Adapter type enumeration.

    Defines the LLM adapter types supported by the system.
    """

    official = "official"      # Official direct connection (DeepSeek, Qwen, etc.)
    openrouter = "openrouter"  # OpenRouter integration
    ollama = "ollama"          # Local Ollama deployment
    vllm = "vllm"              # Local vLLM deployment
    omp = "omp"                # OMP / One Hub OpenAI-compatible gateway from local ~/.omp config


class OfficialProvider(str, enum.Enum):
    """Official provider enumeration.

    Used only when adapter_type is 'official'.
    """

    deepseek = "deepseek"
    qwen = "qwen"
    openai = "openai"
    anthropic = "anthropic"
    gemini = "gemini"


# Legacy enum - kept for backward compatibility, will be deprecated
class LLMProvider(str, enum.Enum):
    """LLM provider enumeration (DEPRECATED - use AdapterType + OfficialProvider)."""

    openai = "openai"
    anthropic = "anthropic"
    deepseek = "deepseek"
    gemini = "gemini"
    qwen = "qwen"
    openrouter = "openrouter"
    ollama = "ollama"
    local = "local"


class FileType(str, enum.Enum):
    """File type enumeration."""

    image = "image"
    video = "video"
    audio = "audio"
    document = "document"


class BatchJobStatus(str, enum.Enum):
    """Batch job status enumeration."""

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class BatchItemStatus(str, enum.Enum):
    """Batch item status enumeration."""

    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class ToolType(str, enum.Enum):
    """Tool type enumeration."""

    code = "code"
    search = "search"
    function = "function"
    structured = "structured"


class ToolExecutionStatus(str, enum.Enum):
    """Tool execution status enumeration."""

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


# =============================================================================
# Mixins
# =============================================================================


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class UUIDMixin:
    """Mixin for UUID primary key."""

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )


# =============================================================================
# Models
# =============================================================================


class User(Base, UUIDMixin, TimestampMixin):
    """User model."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
    model_configs: Mapped[list["ModelConfig"]] = relationship(
        "ModelConfig", back_populates="user", cascade="all, delete-orphan"
    )
    files: Mapped[list["File"]] = relationship(
        "File", back_populates="user", cascade="all, delete-orphan"
    )
    batch_jobs: Mapped[list["BatchJob"]] = relationship(
        "BatchJob", back_populates="user", cascade="all, delete-orphan"
    )
    system_instructions: Mapped[list["SystemInstruction"]] = relationship(
        "SystemInstruction", back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base, UUIDMixin, TimestampMixin):
    """Chat session model."""

    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_created_at", "created_at"),)

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), default="New Chat", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan"
    )
    config: Mapped["SessionConfig | None"] = relationship(
        "SessionConfig", back_populates="session", uselist=False, cascade="all, delete-orphan"
    )


class Message(Base, UUIDMixin):
    """Chat message model."""

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_session_id", "session_id"),
        Index("ix_messages_role", "role"),
        Index("ix_messages_created_at", "created_at"),
    )

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    thinking_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tool_calls: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="messages")
    attachments: Mapped[list["MessageAttachment"]] = relationship(
        "MessageAttachment", back_populates="message", cascade="all, delete-orphan"
    )
    tool_executions: Mapped[list["ToolExecution"]] = relationship(
        "ToolExecution", back_populates="message", cascade="all, delete-orphan"
    )


class SessionConfig(Base, UUIDMixin):
    """Session configuration model.

    Links to a ModelConfig for adapter settings, or stores inline config.
    """

    __tablename__ = "session_configs"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Option 1: Reference to user's ModelConfig
    model_config_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True
    )

    # Option 2: Inline configuration (for backward compatibility)
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    adapter_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Generation parameters
    temperature: Mapped[int] = mapped_column(Integer, default=70, nullable=False)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    top_p: Mapped[int | None] = mapped_column(Integer, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="config")


class ModelConfig(Base, UUIDMixin, TimestampMixin):
    """User's model configuration model.

    Supports four adapter types:
    - official: Direct connection to official providers (requires provider field)
    - openrouter: OpenRouter integration (provider field is None)
    - ollama: Local Ollama deployment (provider field is None)
    - vllm: Local vLLM deployment (provider field is None)
    """

    __tablename__ = "model_configs"
    __table_args__ = (
        Index("ix_model_configs_adapter_type", "adapter_type"),
        Index("ix_model_configs_provider", "provider"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Adapter configuration
    adapter_type: Mapped[str] = mapped_column(String(20), nullable=False)  # official, openrouter, ollama, vllm
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Required only for 'official' type
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Security
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted API key

    # Status
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="model_configs")


class File(Base, UUIDMixin):
    """File model for multimodal uploads."""

    __tablename__ = "files"
    __table_args__ = (Index("ix_files_created_at", "created_at"),)

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[FileType] = mapped_column(Enum(FileType), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="files")
    message_attachments: Mapped[list["MessageAttachment"]] = relationship(
        "MessageAttachment", back_populates="file", cascade="all, delete-orphan"
    )


class MessageAttachment(Base, UUIDMixin):
    """Message attachment association model."""

    __tablename__ = "message_attachments"
    __table_args__ = (
        Index("ix_message_attachments_message_id", "message_id"),
        Index("ix_message_attachments_file_id", "file_id"),
    )

    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    message: Mapped["Message"] = relationship("Message", back_populates="attachments")
    file: Mapped["File"] = relationship("File", back_populates="message_attachments")


class BatchJob(Base, UUIDMixin):
    """Batch processing job model."""

    __tablename__ = "batch_jobs"
    __table_args__ = (Index("ix_batch_jobs_created_at", "created_at"),)

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[BatchJobStatus] = mapped_column(
        Enum(BatchJobStatus), default=BatchJobStatus.pending, nullable=False
    )
    total_items: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="batch_jobs")
    items: Mapped[list["BatchItem"]] = relationship(
        "BatchItem", back_populates="batch_job", cascade="all, delete-orphan"
    )


class BatchItem(Base, UUIDMixin):
    """Batch processing item model."""

    __tablename__ = "batch_items"
    __table_args__ = (Index("ix_batch_items_batch_job_id", "batch_job_id"),)

    batch_job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("batch_jobs.id", ondelete="CASCADE"), nullable=False
    )
    input_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    output_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[BatchItemStatus] = mapped_column(
        Enum(BatchItemStatus), default=BatchItemStatus.pending, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    batch_job: Mapped["BatchJob"] = relationship("BatchJob", back_populates="items")


class ToolExecution(Base, UUIDMixin):
    """Tool execution log model."""

    __tablename__ = "tool_executions"
    __table_args__ = (Index("ix_tool_executions_message_id", "message_id"),)

    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_type: Mapped[ToolType] = mapped_column(Enum(ToolType), nullable=False)
    input_params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ToolExecutionStatus] = mapped_column(
        Enum(ToolExecutionStatus), default=ToolExecutionStatus.pending, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    message: Mapped["Message"] = relationship("Message", back_populates="tool_executions")


class SystemInstruction(Base, UUIDMixin, TimestampMixin):
    """System instruction template model.
    
    Allows users to save and manage multiple system instruction templates.
    """

    __tablename__ = "system_instructions"
    __table_args__ = (
        Index("ix_system_instructions_user_id", "user_id"),
        Index("ix_system_instructions_last_used_at", "last_used_at"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="system_instructions")
