"""
模型配置服务

管理用户的模型配置，创建和管理 LLM 适配器实例。
"""

from uuid import UUID
from typing import Optional
from cryptography.fernet import Fernet
import os

from sqlalchemy import select, and_, desc

from .base import BaseService
from app.core import (
    adapter_factory,
    BaseLLMAdapter,
    AdapterType,
    OfficialProvider,
    ModelInfo,
    ConfigurationError,
)
from app.models.database import ModelConfig
from app.models.schemas import ModelConfigCreate, ModelConfigUpdate


# 加密密钥管理
import pathlib

# 密钥文件路径（保存在项目根目录的隐藏文件中）
KEY_FILE_PATH = pathlib.Path(__file__).parent.parent.parent / ".encryption_key"

def get_or_create_encryption_key() -> bytes:
    """获取或创建加密密钥
    
    优先级：
    1. 环境变量 API_KEY_ENCRYPTION_KEY（用于生产环境）
    2. 本地密钥文件 .encryption_key（开发环境自动管理）
    3. 生成新密钥并保存到文件
    """
    # 1. 尝试从环境变量读取
    env_key = os.getenv("API_KEY_ENCRYPTION_KEY")
    if env_key:
        return env_key.encode() if isinstance(env_key, str) else env_key
    
    # 2. 尝试从本地文件读取
    if KEY_FILE_PATH.exists():
        try:
            with open(KEY_FILE_PATH, 'rb') as f:
                return f.read()
        except Exception as e:
            import warnings
            warnings.warn(f"Failed to read encryption key from file: {e}", RuntimeWarning)
    
    # 3. 生成新密钥并保存到文件
    new_key = Fernet.generate_key()
    try:
        KEY_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(KEY_FILE_PATH, 'wb') as f:
            f.write(new_key)
        print(f"✅ Generated and saved new encryption key to {KEY_FILE_PATH}")
    except Exception as e:
        import warnings
        warnings.warn(f"Failed to save encryption key to file: {e}. Using temporary key.", RuntimeWarning)
    
    return new_key

ENCRYPTION_KEY = get_or_create_encryption_key()
cipher_suite = Fernet(ENCRYPTION_KEY)


def encrypt_api_key(api_key: str) -> str:
    """加密 API Key

    Args:
        api_key: 明文 API Key

    Returns:
        加密后的 API Key
    """
    return cipher_suite.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """解密 API Key

    Args:
        encrypted_key: 加密的 API Key

    Returns:
        明文 API Key
        
    Raises:
        ConfigurationError: 解密失败（密钥不匹配）
    """
    try:
        return cipher_suite.decrypt(encrypted_key.encode()).decode()
    except Exception as e:
        raise ConfigurationError(
            config_key="encrypted_api_key",
            reason="Failed to decrypt API key. The encryption key may have changed. Please reconfigure your API keys."
        ) from e


class ModelService(BaseService):
    """模型配置服务

    管理用户的模型配置，支持四种适配器类型：
    - OFFICIAL: 官方直连（DeepSeek、Qwen 等）
    - OPENROUTER: OpenRouter 集成
    - OLLAMA: 本地 Ollama 部署
    - VLLM: 本地 vLLM 部署
    """

    # =========================================================================
    # 模型配置 CRUD
    # =========================================================================

    async def create_model_config(
        self,
        user_id: UUID,
        data: ModelConfigCreate
    ) -> ModelConfig:
        """创建模型配置

        Args:
            user_id: 用户 ID
            data: 配置创建数据

        Returns:
            创建的配置对象

        Raises:
            ConfigurationError: 配置验证失败
        """
        self.logger.info(f"Creating model config for user {user_id}")

        # 验证 adapter_type
        try:
            adapter_type = AdapterType(data.adapter_type)
        except ValueError:
            raise ConfigurationError(
                config_key="adapter_type",
                reason=f"Invalid adapter type: {data.adapter_type}"
            )

        # 如果是 OFFICIAL 类型，验证 provider
        if adapter_type == AdapterType.OFFICIAL:
            if not data.provider:
                raise ConfigurationError(
                    config_key="provider",
                    reason="Provider is required for OFFICIAL adapter type"
                )
            try:
                OfficialProvider(data.provider)
            except ValueError:
                raise ConfigurationError(
                    config_key="provider",
                    reason=f"Invalid provider: {data.provider}"
                )

        # 加密 API Key
        encrypted_key = encrypt_api_key(data.api_key)

        # 如果设为默认，取消其他默认配置
        if data.is_default:
            await self._unset_default_configs(user_id, adapter_type)

        # 创建配置 - 转换类型为字符串
        config = ModelConfig(
            user_id=str(user_id),
            name=data.name,
            adapter_type=data.adapter_type.value if hasattr(data.adapter_type, 'value') else str(data.adapter_type),
            provider=data.provider.value if data.provider and hasattr(data.provider, 'value') else (str(data.provider) if data.provider else None),
            model_id=data.model_id,
            base_url=data.base_url,
            encrypted_api_key=encrypted_key,
            is_default=data.is_default or False,
        )
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)

        self.logger.info(f"Model config created: {config.id}")
        return config

    async def get_model_config(
        self,
        config_id: UUID,
        user_id: UUID
    ) -> Optional[ModelConfig]:
        """获取模型配置

        Args:
            config_id: 配置 ID
            user_id: 用户 ID

        Returns:
            配置对象或 None（不返回解密的 API Key）
        """
        stmt = select(ModelConfig).where(
            and_(
                ModelConfig.id == str(config_id),
                ModelConfig.user_id == str(user_id)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_model_configs(
        self,
        user_id: UUID,
        adapter_type: Optional[AdapterType] = None,
        provider: Optional[str] = None
    ) -> list[ModelConfig]:
        """列出模型配置

        Args:
            user_id: 用户 ID
            adapter_type: 适配器类型筛选（可选）
            provider: 供应商筛选（可选，仅对 OFFICIAL 类型有效）

        Returns:
            配置列表
        """
        conditions = [ModelConfig.user_id == str(user_id)]

        if adapter_type:
            conditions.append(ModelConfig.adapter_type == adapter_type.value)

        if provider:
            conditions.append(ModelConfig.provider == provider)

        stmt = (
            select(ModelConfig)
            .where(and_(*conditions))
            .order_by(desc(ModelConfig.created_at))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_model_config(
        self,
        config_id: UUID,
        user_id: UUID,
        data: ModelConfigUpdate
    ) -> ModelConfig:
        """更新模型配置

        Args:
            config_id: 配置 ID
            user_id: 用户 ID
            data: 更新数据

        Returns:
            更新后的配置对象

        Raises:
            ValueError: 配置不存在
        """
        config = await self.get_model_config(config_id, user_id)
        if not config:
            raise ValueError(f"Model config {config_id} not found")

        # 更新字段
        if data.name is not None:
            config.name = data.name
        if data.model_id is not None:
            config.model_id = data.model_id
        if data.base_url is not None:
            config.base_url = data.base_url
        if data.api_key is not None:
            config.encrypted_api_key = encrypt_api_key(data.api_key)
        if data.is_default is not None:
            if data.is_default:
                await self._unset_default_configs(
                    user_id,
                    AdapterType(config.adapter_type)
                )
            config.is_default = data.is_default

        await self.db.commit()
        await self.db.refresh(config)

        self.logger.info(f"Model config updated: {config_id}")
        return config

    async def delete_model_config(
        self,
        config_id: UUID,
        user_id: UUID
    ) -> bool:
        """删除模型配置

        Args:
            config_id: 配置 ID
            user_id: 用户 ID

        Returns:
            是否删除成功

        Raises:
            ValueError: 配置正在被使用
        """
        config = await self.get_model_config(config_id, user_id)
        if not config:
            return False

        # TODO: 检查是否有会话正在使用此配置

        await self.db.delete(config)
        await self.db.commit()

        self.logger.info(f"Model config deleted: {config_id}")
        return True

    async def get_default_config(
        self,
        user_id: UUID,
        adapter_type: Optional[AdapterType] = None
    ) -> Optional[ModelConfig]:
        """获取用户默认配置

        Args:
            user_id: 用户 ID
            adapter_type: 适配器类型筛选（可选）

        Returns:
            默认配置或 None
        """
        conditions = [
            ModelConfig.user_id == str(user_id),
            ModelConfig.is_default == True
        ]

        if adapter_type:
            conditions.append(ModelConfig.adapter_type == adapter_type.value)

        stmt = select(ModelConfig).where(and_(*conditions)).order_by(desc(ModelConfig.updated_at))
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _unset_default_configs(
        self,
        user_id: UUID,
        adapter_type: AdapterType
    ) -> None:
        """取消其他默认配置

        Args:
            user_id: 用户 ID
            adapter_type: 适配器类型
        """
        stmt = select(ModelConfig).where(
            and_(
                ModelConfig.user_id == str(user_id),
                ModelConfig.adapter_type == adapter_type.value,
                ModelConfig.is_default == True
            )
        )
        result = await self.db.execute(stmt)
        configs = result.scalars().all()

        for config in configs:
            config.is_default = False

    # =========================================================================
    # 模型验证
    # =========================================================================

    async def validate_model_config(
        self,
        config_id: UUID,
        user_id: UUID
    ) -> dict:
        """验证模型配置

        Args:
            config_id: 配置 ID
            user_id: 用户 ID

        Returns:
            验证结果字典

        Raises:
            ValueError: 配置不存在
        """
        self.logger.info(f"Validating model config {config_id}")

        config = await self.get_model_config(config_id, user_id)
        if not config:
            raise ValueError(f"Model config {config_id} not found")

        try:
            # 创建适配器
            adapter = await self._create_adapter(config)

            # 验证凭证
            is_valid = await adapter.validate_credentials()

            await adapter.close()

            return {
                "valid": is_valid,
                "config_id": str(config_id),
                "adapter_type": config.adapter_type,
                "provider": config.provider,
                "model_id": config.model_id,
            }
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return {
                "valid": False,
                "config_id": str(config_id),
                "error": str(e),
            }

    async def list_available_models(
        self,
        config_id: UUID,
        user_id: UUID
    ) -> list[ModelInfo]:
        """列出可用模型

        Args:
            config_id: 配置 ID
            user_id: 用户 ID

        Returns:
            模型信息列表

        Raises:
            ValueError: 配置不存在
        """
        config = await self.get_model_config(config_id, user_id)
        if not config:
            raise ValueError(f"Model config {config_id} not found")

        adapter = await self._create_adapter(config)
        models = await adapter.list_models()
        await adapter.close()

        return models

    # =========================================================================
    # 适配器获取
    # =========================================================================

    async def get_adapter(
        self,
        config_id: UUID,
        user_id: UUID
    ) -> BaseLLMAdapter:
        """获取适配器实例

        Args:
            config_id: 配置 ID
            user_id: 用户 ID

        Returns:
            适配器实例

        Raises:
            ValueError: 配置不存在或适配器类型不支持
        """
        config = await self.get_model_config(config_id, user_id)
        if not config:
            raise ValueError(f"Model config {config_id} not found")

        return await self._create_adapter(config)

    async def get_adapter_for_session(
        self,
        session_id: UUID,
        user_id: UUID
    ) -> BaseLLMAdapter:
        """获取会话的适配器实例

        Args:
            session_id: 会话 ID
            user_id: 用户 ID

        Returns:
            适配器实例

        Raises:
            ConfigurationError: 没有可用的模型配置或所有配置都无法使用
        """
        # TODO: 从会话配置获取 model_config_id
        # 目前先返回默认配置的适配器
        default_config = await self.get_default_config(user_id)
        
        # 尝试使用默认配置创建适配器
        if default_config:
            try:
                return await self._create_adapter(default_config)
            except ConfigurationError as e:
                self.logger.warning(f"Default config {default_config.id} failed: {e.reason}. Trying other configs...")
        
        # 如果默认配置失败或不存在，尝试其他配置
        configs = await self.list_model_configs(user_id)
        
        # 如果有配置，逐个尝试
        for config in configs:
            if default_config and config.id == default_config.id:
                continue  # 跳过已经尝试失败的默认配置
            
            try:
                adapter = await self._create_adapter(config)
                self.logger.info(f"Using config {config.id} (name: {config.name})")
                return adapter
            except ConfigurationError as e:
                self.logger.warning(f"Config {config.id} failed: {e.reason}. Trying next...")
                continue
        
        # 所有配置都失败了
        if configs:
            raise ConfigurationError(
                config_key="model_config",
                reason="All model configurations failed. This may be due to encryption key mismatch. "
                       "Please reconfigure your API keys in the Settings."
            )
        else:
            raise ConfigurationError(
                config_key="model_config",
                reason="No model configuration found. Please configure a model in the Settings first."
            )

    async def _create_adapter(self, config: ModelConfig) -> BaseLLMAdapter:
        """创建适配器实例

        Args:
            config: 模型配置

        Returns:
            适配器实例

        Raises:
            ValueError: 不支持的适配器类型
        """
        # 解密 API Key
        api_key = decrypt_api_key(config.encrypted_api_key)

        adapter_type = AdapterType(config.adapter_type)

        # 根据适配器类型创建
        if adapter_type == AdapterType.OFFICIAL:
            return adapter_factory.create_official(
                provider=config.provider,
                model_id=config.model_id,
                api_key=api_key,
                base_url=config.base_url,
            )
        elif adapter_type == AdapterType.OPENROUTER:
            return adapter_factory.create_openrouter(
                model_id=config.model_id,
                api_key=api_key,
            )
        elif adapter_type == AdapterType.OLLAMA:
            return adapter_factory.create_ollama(
                model_id=config.model_id,
                base_url=config.base_url or "http://localhost:11434",
            )
        elif adapter_type == AdapterType.VLLM:
            return adapter_factory.create_vllm(
                model_id=config.model_id,
                base_url=config.base_url or "http://localhost:8000/v1",
            )
        elif adapter_type == AdapterType.OMP:
            return adapter_factory.create_omp(
                model_id=config.model_id,
                api_key=api_key,
                base_url=config.base_url,
            )
        else:
            raise ValueError(f"Unsupported adapter type: {adapter_type}")
