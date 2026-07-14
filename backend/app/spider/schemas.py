"""Pydantic schemas for the Spider Agent."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class SpiderAgentRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: UUID | None = None
    model_config_id: UUID
    target_url: str | None = None


class SpiderWorkspaceFile(BaseModel):
    name: str
    size: int
    modified_at: str | None = None


class SpiderWorkspaceResponse(BaseModel):
    session_id: str
    workspace_path: str
    volume_name: str
    files: list[SpiderWorkspaceFile]
