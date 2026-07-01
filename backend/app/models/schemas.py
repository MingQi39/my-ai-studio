"""Pydantic schemas for API request/response validation.

This module defines all DTOs (Data Transfer Objects) for the API.
Schemas are used for request validation and response serialization.
"""

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import AdapterType, OfficialProvider
from app.models.database import (
    BatchItemStatus,
    BatchJobStatus,
    FileType,
    LLMProvider,
    MessageRole,
    SessionType,
    ToolExecutionStatus,
    ToolType,
)

# =============================================================================
# Generic Types
# =============================================================================

T = TypeVar("T")


# =============================================================================
# Base Schema
# =============================================================================


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat()},
    )


# =============================================================================
# Pagination
# =============================================================================


class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseSchema, Generic[T]):
    """Paginated response wrapper."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# User Schemas
# =============================================================================


class UserCreate(BaseModel):
    """Schema for creating a user."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6)


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    username: str | None = Field(default=None, min_length=3, max_length=100)
    password: str | None = Field(default=None, min_length=6)


class UserResponse(BaseSchema):
    """Schema for user response."""

    id: UUID
    email: str
    username: str
    is_active: bool
    created_at: datetime


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str


class Token(BaseModel):
    """Schema for JWT token response."""

    access_token: str
    token_type: str = "bearer"


class TokenWithUser(Token):
    """Schema for token response with user info."""

    user: UserResponse


# =============================================================================
# Session Schemas
# =============================================================================


class SessionCreate(BaseModel):
    """Schema for creating a session."""

    title: str | None = Field(default="New Chat", max_length=255)
    description: str | None = None
    session_type: SessionType = SessionType.chat


class SessionUpdate(BaseModel):
    """Schema for updating a session."""

    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    is_archived: bool | None = None


class SessionResponse(BaseSchema):
    """Schema for session response."""

    id: UUID
    title: str
    description: str | None
    session_type: SessionType = SessionType.chat
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class SessionDetailResponse(SessionResponse):
    """Schema for detailed session response with messages."""

    messages: list["MessageResponse"] = []
    config: "SessionConfigResponse | None" = None


# =============================================================================
# Message Schemas
# =============================================================================


class MessageCreate(BaseModel):
    """Schema for creating a message."""

    content: str
    role: MessageRole = MessageRole.user
    thinking_content: str | None = None
    token_count: int | None = None
    file_ids: list[UUID] | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ChatToolsConfig(BaseModel):
    """Enabled tools for main chat (mirrors frontend toggles)."""

    search: bool = False
    code: bool = False
    function: bool = False
    structured: bool = False

    def any_enabled(self) -> bool:
        return self.search or self.code or self.function or self.structured


class MessageResponse(BaseSchema):
    """Schema for message response."""

    id: UUID
    role: MessageRole
    content: str
    thinking_content: str | None = None
    tokens_used: int | None = None
    model_used: str | None = None
    provider_used: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    created_at: datetime
    attachments: list["FileResponse"] | None = None


# =============================================================================
# Session Config Schemas
# =============================================================================


class SessionConfigCreate(BaseModel):
    """Schema for creating session config."""

    model_id: str
    provider: LLMProvider
    temperature: int = Field(default=70, ge=0, le=100)
    max_tokens: int | None = None
    top_p: int | None = Field(default=None, ge=0, le=100)
    system_prompt: str | None = None


class SessionConfigUpdate(BaseModel):
    """Schema for updating session config."""

    model_id: str | None = None
    provider: LLMProvider | None = None
    temperature: int | None = Field(default=None, ge=0, le=100)
    max_tokens: int | None = None
    top_p: int | None = Field(default=None, ge=0, le=100)
    system_prompt: str | None = None


class SessionConfigResponse(BaseSchema):
    """Schema for session config response."""

    id: UUID
    model_id: str
    provider: LLMProvider | None = None
    temperature: int
    max_tokens: int | None = None
    top_p: int | None = None
    system_prompt: str | None = None

    @field_validator('temperature', mode='before')
    @classmethod
    def parse_temperature(cls, v: Any) -> int:
        if isinstance(v, float):
            return int(v)  # Handle legacy float data
        return v


# =============================================================================
# Model Config Schemas
# =============================================================================


class ModelInfo(BaseModel):
    """Schema for model information."""

    id: str
    name: str
    supports_vision: bool = False
    supports_tools: bool = False
    supports_reasoning: bool = False


class ModelConfigCreate(BaseModel):
    """Schema for creating model config."""

    adapter_type: AdapterType
    provider: OfficialProvider | None = None  # Required only for 'official' adapter_type
    name: str = Field(max_length=100)
    api_key: str = ""  # Optional for local adapters
    base_url: str = Field(max_length=500)
    model_id: str = Field(max_length=100)
    is_default: bool = False


class ModelConfigUpdate(BaseModel):
    """Schema for updating model config."""

    adapter_type: AdapterType | None = None
    provider: OfficialProvider | None = None
    name: str | None = Field(default=None, max_length=100)
    api_key: str | None = None
    base_url: str | None = Field(default=None, max_length=500)
    model_id: str | None = Field(default=None, max_length=100)
    is_default: bool | None = None
    is_active: bool | None = None


class ModelConfigResponse(BaseSchema):
    """Schema for model config response.

    Note: api_key is NOT included for security.
    """

    id: UUID
    adapter_type: str
    provider: str | None
    name: str
    base_url: str
    model_id: str
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# File Schemas
# =============================================================================


class FileCreate(BaseModel):
    """Schema for creating a file."""

    filename: str
    mime_type: str
    file_size: int
    file_type: FileType
    storage_path: str
    file_metadata: dict[str, Any] | None = None


class FileUploadResponse(BaseSchema):
    """Schema for file upload response."""

    id: UUID
    name: str
    type: FileType
    mime_type: str
    size: int
    url: str | None = None
    created_at: datetime


class FileResponse(FileUploadResponse):
    """Schema for file response with metadata."""

    file_metadata: dict[str, Any] | None = None


# =============================================================================
# Batch Schemas
# =============================================================================


class BatchItemInput(BaseModel):
    """Schema for batch item input."""

    prompt: str
    system_prompt: str | None = None
    metadata: dict[str, Any] | None = None


class BatchJobCreate(BaseModel):
    """Schema for creating a batch job."""

    name: str = Field(max_length=255)
    items: list[BatchItemInput]
    model_config_id: UUID
    temperature: int | None = Field(default=None, ge=0, le=100)
    max_tokens: int | None = None


class BatchJobResponse(BaseSchema):
    """Schema for batch job response."""

    id: UUID
    name: str
    status: BatchJobStatus
    total_items: int
    processed_items: int
    failed_items: int
    progress_percent: float = 0.0
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def calculated_progress(self) -> float:
        """Calculate progress percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.processed_items + self.failed_items) / self.total_items * 100


class BatchItemResponse(BaseSchema):
    """Schema for batch item response."""

    id: UUID
    status: BatchItemStatus
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None = None
    error_message: str | None = None
    retry_count: int


# =============================================================================
# Chat Schemas
# =============================================================================


class ChatRequest(BaseModel):
    """Schema for chat request."""

    session_id: UUID
    message: str
    file_ids: list[UUID] | None = None
    stream: bool = True
    enable_reasoning: bool = True  # 是否启用推理模式
    system_prompt: str | None = None  # 临时系统指令（覆盖会话配置）
    model_config_id: UUID | None = None  # 指定使用的模型配置 ID
    tools_config: ChatToolsConfig | None = None  # 主聊天工具开关



class ChatStreamChunk(BaseModel):
    """Schema for chat stream chunk."""

    type: Literal["content", "thinking", "tool_call", "done", "error"]
    content: str | None = None
    tool_call: dict[str, Any] | None = None
    error: str | None = None
    usage: dict[str, Any] | None = None


# =============================================================================
# System Instruction Schemas
# =============================================================================


class SystemInstructionCreate(BaseModel):
    """Schema for creating a system instruction."""

    title: str = Field(max_length=255)
    content: str
    is_default: bool = False


class SystemInstructionUpdate(BaseModel):
    """Schema for updating a system instruction."""

    title: str | None = Field(default=None, max_length=255)
    content: str | None = None
    is_default: bool | None = None


class SystemInstructionResponse(BaseSchema):
    """Schema for system instruction response."""

    id: UUID
    title: str
    content: str
    is_default: bool
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Tool Execution Schemas
# =============================================================================


class ToolExecutionResponse(BaseSchema):
    """Schema for tool execution response."""

    id: UUID
    tool_name: str
    tool_type: ToolType
    input_params: dict[str, Any]
    output: str | None = None
    status: ToolExecutionStatus
    error_message: str | None = None
    execution_time_ms: int | None = None
    created_at: datetime


# =============================================================================
# Forward References Update
# =============================================================================

# Update forward references for nested models
SessionDetailResponse.model_rebuild()
MessageResponse.model_rebuild()
