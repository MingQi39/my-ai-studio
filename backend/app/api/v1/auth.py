"""认证 API 路由

提供用户注册、登录、获取当前用户等功能
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_auth, get_db
from app.models.schemas import (
    TokenWithUser,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenWithUser, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> TokenWithUser:
    """用户注册

    Args:
        user_data: 用户注册信息
        db: 数据库会话

    Returns:
        TokenWithUser: 包含访问令牌和用户信息

    Raises:
        HTTPException: 邮箱或用户名已存在
    """
    user_service = UserService(db)

    # 检查邮箱是否已存在
    existing_user = await user_service.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册",
        )

    # 检查用户名是否已存在
    existing_user = await user_service.get_user_by_username(user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户名已被使用",
        )

    # 创建用户
    user = await user_service.create_user(
        email=user_data.email,
        username=user_data.username,
        password=user_data.password,
    )

    # 生成令牌
    access_token = UserService.create_access_token(user.id)

    return TokenWithUser(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenWithUser)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenWithUser:
    """用户登录

    Args:
        login_data: 登录信息
        db: 数据库会话

    Returns:
        TokenWithUser: 包含访问令牌和用户信息

    Raises:
        HTTPException: 邮箱或密码错误
    """
    user_service = UserService(db)

    user = await user_service.authenticate_user(
        email=login_data.email,
        password=login_data.password,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 生成令牌
    access_token = UserService.create_access_token(user.id)

    return TokenWithUser(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    db: AsyncSession = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_auth),
) -> UserResponse:
    """获取当前用户信息

    Args:
        db: 数据库会话
        current_user_id: 当前用户ID

    Returns:
        UserResponse: 用户信息

    Raises:
        HTTPException: 用户不存在
    """
    user_service = UserService(db)
    user = await user_service.get_user_by_id(current_user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    return UserResponse.model_validate(user)
