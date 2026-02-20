"""
存储驱动扩展点

允许插件注册新的存储驱动（如阿里云 OSS、腾讯云 COS、七牛云等）。
当前系统内置 LocalDriver 和 S3Driver，其他对象存储通过此扩展点以插件形式接入。

PluginManager 启用插件时会调用 get_driver_class() 获取驱动类，
并将 get_driver_name() 返回的驱动名注册到 StorageManager 中。
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, TYPE_CHECKING

from app.plugins.base import BasePlugin

if TYPE_CHECKING:
    pass


class StoragePlugin(BasePlugin):
    """
    存储驱动插件接口

    继承此类来注册新的存储驱动。

    使用示例::

        class AliyunOssPlugin(StoragePlugin):
            @property
            def name(self) -> str:
                return "novusai-aliyun-oss"

            @property
            def display_name(self) -> str:
                return "Aliyun OSS Storage"

            @property
            def version(self) -> str:
                return "1.0.0"

            def get_driver_name(self) -> str:
                return "oss"

            def get_driver_class(self):
                from .oss_driver import OssDriver
                return OssDriver

            def get_config_schema(self) -> dict:
                return {
                    "access_key_id": {"type": "string", "required": True},
                    "access_key_secret": {"type": "string", "required": True, "sensitive": True},
                    "bucket": {"type": "string", "required": True},
                    "endpoint": {"type": "string", "required": True},
                    "region": {"type": "string", "required": False},
                }
    """

    @abstractmethod
    def get_driver_name(self) -> str:
        """
        返回存储驱动唯一标识名

        此名称将用于:
        - 系统配置中的 platform_storage_driver / tenant_storage_driver 值
        - Attachment.driver 字段记录
        - StorageManager 驱动注册表 key

        Returns:
            驱动名称，如 "oss" / "cos" / "qiniu" / "minio"
        """
        ...

    @abstractmethod
    def get_driver_class(self) -> type:
        """
        返回存储驱动类

        驱动类必须实现以下异步方法:
        - put(path, content, mime_type, visibility, metadata) -> UploadResult
        - get(path) -> bytes
        - delete(path) -> bool
        - exists(path) -> bool
        - get_url(path, expires, visibility) -> str
        - get_size(path) -> int
        - get_base_url() -> str

        Returns:
            驱动类（继承 BaseStorageDriver）
        """
        ...

    def get_config_schema(self) -> dict[str, Any]:
        """
        返回驱动配置项的 JSON Schema

        用于前端动态渲染存储配置表单。
        sensitive=True 的字段在前端显示为密码框，存储时加密。

        Returns:
            配置项 Schema，格式:
            {
                "field_name": {
                    "type": "string",
                    "required": True/False,
                    "sensitive": True/False,
                    "description": "...",
                    "default": "...",
                }
            }
        """
        return {}

    def get_default_config(self) -> dict[str, Any]:
        """
        返回驱动默认配置

        Returns:
            默认配置字典
        """
        return {}

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """
        验证配置有效性

        Args:
            config: 用户输入的配置

        Returns:
            错误消息列表，空列表表示验证通过
        """
        errors: list[str] = []
        schema = self.get_config_schema()
        for field_name, field_spec in schema.items():
            if field_spec.get("required") and not config.get(field_name):
                errors.append(f"Missing required field: {field_name}")
        return errors

    async def test_connection(self, config: dict[str, Any]) -> bool:
        """
        测试存储连接是否可用

        Args:
            config: 存储配置

        Returns:
            连接是否成功
        """
        return True


__all__ = ["StoragePlugin"]
