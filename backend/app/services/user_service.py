"""用户服务

提供用户注册、登录、查询等功能
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import User
from app.services.base import BaseService

# JWT 配置
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 天


class UserService(BaseService):
    """用户服务类"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )

    @staticmethod
    def get_password_hash(password: str) -> str:
        """生成密码哈希"""
        # bcrypt 限制密码最长 72 字节
        password_bytes = password.encode('utf-8')[:72]
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')

    @staticmethod
    def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
        """创建访问令牌"""
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode = {"sub": user_id, "exp": expire}
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def decode_access_token(token: str) -> str | None:
        """解码访问令牌，返回用户ID"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str | None = payload.get("sub")
            if user_id is None:
                return None
            return user_id
        except JWTError:
            return None

    async def get_user_by_email(self, email: str) -> User | None:
        """通过邮箱获取用户"""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> User | None:
        """通过用户名获取用户"""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """通过ID获取用户"""
        result = await self.db.execute(
            select(User).where(User.id == str(user_id))
        )
        return result.scalar_one_or_none()

    async def create_user(self, email: str, username: str, password: str) -> User:
        """创建用户"""
        hashed_password = self.get_password_hash(password)
        user = User(
            email=email,
            username=username,
            hashed_password=hashed_password,
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def authenticate_user(self, email: str, password: str) -> User | None:
        """验证用户登录"""
        user = await self.get_user_by_email(email)
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user

    async def update_user(
        self,
        user_id: UUID,
        username: str | None = None,
        password: str | None = None
    ) -> User | None:
        """更新用户信息"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        if username:
            user.username = username
        if password:
            user.hashed_password = self.get_password_hash(password)

        await self.db.flush()
        await self.db.refresh(user)
        return user
