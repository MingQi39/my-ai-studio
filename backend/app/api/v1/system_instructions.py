"""System instructions endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.database import SystemInstruction
from app.models.schemas import (
    SystemInstructionCreate,
    SystemInstructionResponse,
    SystemInstructionUpdate,
)

router = APIRouter(prefix="/system-instructions", tags=["system-instructions"])


@router.get("", response_model=list[SystemInstructionResponse])
async def list_system_instructions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user_id: Annotated[UUID, Depends(get_current_user)],
) -> list[SystemInstructionResponse]:
    """List all system instructions for the current user.
    
    Returns instructions sorted by last_used_at (most recent first), then by created_at.
    """
    stmt = (
        select(SystemInstruction)
        .where(SystemInstruction.user_id == str(current_user_id))
        .order_by(SystemInstruction.last_used_at.desc().nulls_last())
        .order_by(SystemInstruction.created_at.desc())
    )
    result = await db.execute(stmt)
    instructions = result.scalars().all()
    return [SystemInstructionResponse.model_validate(inst) for inst in instructions]


@router.get("/{instruction_id}", response_model=SystemInstructionResponse)
async def get_system_instruction(
    instruction_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user_id: Annotated[UUID, Depends(get_current_user)],
) -> SystemInstructionResponse:
    """Get a specific system instruction by ID."""
    stmt = select(SystemInstruction).where(
        SystemInstruction.id == str(instruction_id),
        SystemInstruction.user_id == str(current_user_id),
    )
    result = await db.execute(stmt)
    instruction = result.scalar_one_or_none()

    if not instruction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="System instruction not found",
        )

    return SystemInstructionResponse.model_validate(instruction)


@router.post("", response_model=SystemInstructionResponse, status_code=status.HTTP_201_CREATED)
async def create_system_instruction(
    instruction_in: SystemInstructionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user_id: Annotated[UUID, Depends(get_current_user)],
) -> SystemInstructionResponse:
    """Create a new system instruction."""
    # If setting as default, remove default from other instructions
    if instruction_in.is_default:
        stmt = (
            update(SystemInstruction)
            .where(
                SystemInstruction.user_id == str(current_user_id),
                SystemInstruction.is_default == True,
            )
            .values(is_default=False)
        )
        await db.execute(stmt)

    instruction = SystemInstruction(
        user_id=str(current_user_id),
        title=instruction_in.title,
        content=instruction_in.content,
        is_default=instruction_in.is_default,
    )
    db.add(instruction)
    await db.commit()
    await db.refresh(instruction)

    return SystemInstructionResponse.model_validate(instruction)


@router.patch("/{instruction_id}", response_model=SystemInstructionResponse)
async def update_system_instruction(
    instruction_id: UUID,
    instruction_in: SystemInstructionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user_id: Annotated[UUID, Depends(get_current_user)],
) -> SystemInstructionResponse:
    """Update a system instruction."""
    stmt = select(SystemInstruction).where(
        SystemInstruction.id == str(instruction_id),
        SystemInstruction.user_id == str(current_user_id),
    )
    result = await db.execute(stmt)
    instruction = result.scalar_one_or_none()

    if not instruction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="System instruction not found",
        )

    # If setting as default, remove default from other instructions
    if instruction_in.is_default is True:
        stmt = (
            update(SystemInstruction)
            .where(
                SystemInstruction.user_id == str(current_user_id),
                SystemInstruction.is_default == True,
                SystemInstruction.id != str(instruction_id),
            )
            .values(is_default=False)
        )
        await db.execute(stmt)

    # Update fields
    if instruction_in.title is not None:
        instruction.title = instruction_in.title
    if instruction_in.content is not None:
        instruction.content = instruction_in.content
    if instruction_in.is_default is not None:
        instruction.is_default = instruction_in.is_default

    await db.commit()
    await db.refresh(instruction)

    return SystemInstructionResponse.model_validate(instruction)


@router.delete("/{instruction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_system_instruction(
    instruction_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user_id: Annotated[UUID, Depends(get_current_user)],
) -> None:
    """Delete a system instruction."""
    stmt = select(SystemInstruction).where(
        SystemInstruction.id == str(instruction_id),
        SystemInstruction.user_id == str(current_user_id),
    )
    result = await db.execute(stmt)
    instruction = result.scalar_one_or_none()

    if not instruction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="System instruction not found",
        )

    await db.delete(instruction)
    await db.commit()


@router.post("/{instruction_id}/use", response_model=SystemInstructionResponse)
async def mark_instruction_as_used(
    instruction_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user_id: Annotated[UUID, Depends(get_current_user)],
) -> SystemInstructionResponse:
    """Mark a system instruction as recently used (updates last_used_at)."""
    from datetime import datetime, timezone
    
    stmt = select(SystemInstruction).where(
        SystemInstruction.id == str(instruction_id),
        SystemInstruction.user_id == str(current_user_id),
    )
    result = await db.execute(stmt)
    instruction = result.scalar_one_or_none()

    if not instruction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="System instruction not found",
        )

    instruction.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(instruction)

    return SystemInstructionResponse.model_validate(instruction)
