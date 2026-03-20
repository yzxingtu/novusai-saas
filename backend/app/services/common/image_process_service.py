"""
图片处理服务 / Image Processing Service

提供统一的图片处理入口，自动选择最优处理方式：
Provides unified image processing entry point, auto-selects optimal approach:
- 云存储使用原生图片处理 URL / Cloud storage uses native image processing URL
- 本地存储使用 Pillow + 文件缓存 / Local storage uses Pillow + file cache
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import ConfigService, PLATFORM_TENANT_ID
from app.storage import StorageConfig, StorageVisibility, storage_manager
from app.utils.image import PRESETS, ImageProcessParams

if TYPE_CHECKING:
    from app.models.tenant.attachment import Attachment


class ImageProcessService:
    """
    图片处理服务 / Image processing service.

    提供统一的图片处理入口，根据存储驱动自动选择最优处理方式
    """

    def __init__(self, db: AsyncSession, tenant_id: int | None = None):
        """
        初始化服务 / Initialize service.

        Args:
            db: 数据库会话
            tenant_id: 企业 ID，为空表示公共上下文
        """
        self.db = db
        self.tenant_id = tenant_id
        self.config_service = ConfigService(db)

    async def is_enabled(self) -> bool:
        """
        检查图片处理功能是否启用 / Check if image processing is enabled.
        """
        enabled = await self.config_service.get_platform_config(
            "platform_image_process_enabled",
            default=True,
        )
        return bool(enabled)

    async def get_config(self) -> dict:
        """
        获取图片处理配置 / Get image processing config.
        """
        return {
            "enabled": await self.config_service.get_platform_config(
                "platform_image_process_enabled", default=True
            ),
            "cache_driver": await self.config_service.get_platform_config(
                "platform_image_cache_driver", default="filesystem"
            ),
            "cache_path": str(await self._get_image_cache_path()),
            "cache_ttl_days": await self.config_service.get_platform_config(
                "platform_image_cache_ttl_days", default=7
            ),
            "cache_ttl": int(await self.config_service.get_platform_config(
                "platform_image_cache_ttl_days", default=7
            )) * 86400,  # 转换为秒
            "max_width": await self.config_service.get_platform_config(
                "platform_image_max_width", default=4096
            ),
            "max_height": await self.config_service.get_platform_config(
                "platform_image_max_height", default=4096
            ),
            "default_quality": await self.config_service.get_platform_config(
                "platform_image_default_quality", default=85
            ),
        }

    async def parse_params(
        self,
        width: int | None = None,
        height: int | None = None,
        quality: int | None = None,
        format: str | None = None,
        mode: str | None = None,
        preset: str | None = None,
    ) -> ImageProcessParams:
        """
        解析图片处理参数 / Parse image process params.

        支持预设和自定义参数混合使用，自定义参数优先级更高
        参数会根据平台配置进行限制
        """
        # 获取平台配置
        config = await self.get_config()
        max_width = int(config["max_width"])
        max_height = int(config["max_height"])
        default_quality = int(config["default_quality"])

        # 如果指定了预设，先加载预设值
        if preset and preset in PRESETS:
            preset_config = PRESETS[preset]
            params = ImageProcessParams(
                width=preset_config.get("width"),
                height=preset_config.get("height"),
                quality=preset_config.get("quality", default_quality),
                format=preset_config.get("format"),
                mode=preset_config.get("mode", "fit"),
            )
        else:
            params = ImageProcessParams(quality=default_quality)

        # 自定义参数覆盖预设值
        if width is not None:
            params.width = min(width, max_width)
        if height is not None:
            params.height = min(height, max_height)
        if quality is not None:
            params.quality = quality
        if format is not None:
            params.format = format
        if mode is not None:
            params.mode = mode

        # 确保尺寸不超过配置限制
        if params.width and params.width > max_width:
            params.width = max_width
        if params.height and params.height > max_height:
            params.height = max_height

        return params

    async def get_image_url(
        self,
        attachment: Attachment,
        params: ImageProcessParams,
        expires: int = 3600,
    ) -> str:
        """
        获取处理后的图片访问 URL / Get processed image URL.

        根据存储驱动自动选择：
        - OSS: 使用 x-oss-process 参数
        - S3 + 图片处理服务: 使用 Cloudflare/imgproxy 等
        - 本地/MinIO/其他: 本地处理并返回缓存文件 URL

        Args:
            attachment: 附件对象
            params: 图片处理参数
            expires: URL 有效期（秒）

        Returns:
            处理后的图片 URL
        """
        if params.is_empty():
            # 无需处理，返回原始 URL
            return await self._get_original_url(attachment, expires)

        storage_config = await self._resolve_storage_config(attachment)
        driver = storage_manager.get_driver(storage_config)
        visibility = StorageVisibility(attachment.visibility)

        return await driver.get_image_url(
            attachment.path,
            params,
            expires=expires,
            visibility=visibility,
        )

    async def get_processed_image(
        self,
        attachment: Attachment,
        params: ImageProcessParams,
    ) -> tuple[bytes, str] | None:
        """
        获取处理后的图片数据 / Get processed image data.

        用于流式响应场景，直接返回处理后的字节数据

        Args:
            attachment: 附件对象
            params: 图片处理参数

        Returns:
            (图片字节数据, MIME 类型) 或 None（如果无需处理）
        """
        if params.is_empty():
            return None

        storage_config = await self._resolve_storage_config(attachment)
        driver = storage_manager.get_driver(storage_config)

        return await driver.get_processed_image(attachment.path, params)

    async def get_processed_image_response(
        self,
        attachment: Attachment,
        params: ImageProcessParams,
        expires: int = 3600,
    ) -> str | tuple[bytes, str]:
        """
        获取处理后的图片响应 / Get processed image response.

        根据存储驱动自动选择最优处理方式:
        - 云存储原生处理: 返回重定向 URL (str)
        - 本地处理: 返回图片数据 (bytes, mime_type)
        - 配置不匹配: 返回 base_url 直接 CDN URL (str)

        Args:
            attachment: 附件对象
            params: 图片处理参数
            expires: URL 有效期（秒）

        Returns:
            重定向 URL 或 (图片数据, MIME 类型)
        """
        try:
            storage_config = await self._resolve_storage_config(attachment)
        except Exception:
            # Config resolution failed — try direct CDN URL fallback
            direct = self._build_direct_cdn_url(attachment)
            if direct:
                return direct
            raise

        # Config driver doesn't match attachment driver — direct URL fallback
        if storage_config.driver != attachment.driver:
            direct = self._build_direct_cdn_url(attachment)
            if direct:
                return direct

        driver = storage_manager.get_driver(storage_config)

        # 云存储原生处理，返回重定向 URL
        if driver.supports_native_image_processing():
            visibility = StorageVisibility(attachment.visibility)
            url = await driver.get_image_url(
                attachment.path,
                params,
                expires=expires,
                visibility=visibility,
            )
            return url

        # 本地处理，返回图片数据
        result = await driver.get_processed_image(attachment.path, params)
        if result is None:
            # 无需处理，返回原始 URL
            visibility = StorageVisibility(attachment.visibility)
            return await driver.get_url(attachment.path, expires=expires, visibility=visibility)

        return result

    async def get_image_info(
        self,
        attachment: Attachment,
        params: ImageProcessParams,
    ) -> dict[str, Any]:
        """
        获取图片处理结果信息 / Get image process result info.

        返回处理方式和 URL 等信息

        Args:
            attachment: 附件对象
            params: 图片处理参数

        Returns:
            图片处理信息
        """
        storage_config = await self._resolve_storage_config(attachment)
        driver = storage_manager.get_driver(storage_config)

        url = await self.get_image_url(attachment, params)

        return {
            "attachment_id": attachment.id,
            "url": url,
            "driver": storage_config.driver,
            "native_processing": driver.supports_native_image_processing(),
            "params": {
                "width": params.width,
                "height": params.height,
                "quality": params.quality,
                "format": params.format,
                "mode": params.mode,
            },
        }

    async def _get_original_url(
        self,
        attachment: Attachment,
        expires: int,
    ) -> str:
        """
        获取原始图片 URL / Get original image URL.
        """
        storage_config = await self._resolve_storage_config(attachment)
        driver = storage_manager.get_driver(storage_config)
        visibility = StorageVisibility(attachment.visibility)
        return await driver.get_url(attachment.path, expires=expires, visibility=visibility)

    async def _resolve_storage_config(
        self,
        attachment: Attachment,
    ) -> StorageConfig:
        """
        解析附件所属的存储配置（委托给统一 StorageConfigResolver）/ Resolve storage config for attachment (via StorageConfigResolver).
        """
        from app.services.common.storage_config_resolver import StorageConfigResolver

        resolver = StorageConfigResolver(self.db)
        return await resolver.resolve_for_attachment(
            driver=attachment.driver,
            tenant_id=self.tenant_id or PLATFORM_TENANT_ID,
        )

    @staticmethod
    def _build_direct_cdn_url(attachment: Attachment) -> str | None:
        """从附件 base_url + path 构建直连 CDN URL / Build direct CDN URL from attachment's own stored base_url + path.

        Works for public cloud files regardless of current storage config.
        Returns None for local driver, private files, or missing base_url.
        """
        from app.enums.attachment import AttachmentVisibility

        if attachment.driver == "local":
            return None
        if attachment.visibility != AttachmentVisibility.PUBLIC.value:
            return None
        base_url = attachment.base_url
        if not base_url:
            return None
        path = attachment.path.lstrip("/")
        return f"{base_url.rstrip('/')}/{path}"

    async def _get_image_cache_path(self):
        """
        获取图片缓存路径（本地存储硬编码）/ Get image cache path (local storage).
        """
        from app.storage import LOCAL_IMAGE_CACHE_ROOT
        return LOCAL_IMAGE_CACHE_ROOT


__all__ = ["ImageProcessService"]
