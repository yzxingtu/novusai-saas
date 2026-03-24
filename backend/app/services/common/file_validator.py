"""
文件类型验证服务 / File Validator Service

提供文件扩展名和大小的验证功能
Provides file extension and size validation.
"""

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import ConfigService
from app.core.i18n import _
from app.enums import ErrorCode
from app.exceptions import BusinessException


class FileValidationResult:
    """文件验证结果 / File validation result"""

    def __init__(
        self,
        allowed: bool,
        message: str | None = None,
        code: ErrorCode | None = None,
    ):
        self.allowed = allowed
        self.message = message
        self.code = code

    @classmethod
    def ok(cls) -> "FileValidationResult":
        return cls(allowed=True)

    @classmethod
    def denied(cls, message: str, code: ErrorCode) -> "FileValidationResult":
        return cls(allowed=False, message=message, code=code)


class FileValidator:
    """
    文件验证器 / File validator

    验证文件扩展名和大小是否符合配置要求
    Validates file extension and size against config.
    """

    def __init__(self, db: AsyncSession):
        self._config_service = ConfigService(db)
        # 缓存配置 / Cache config
        self._platform_allowed: set[str] | None = None
        self._platform_denied: set[str] | None = None
        self._platform_max_size_mb: int | None = None

    async def validate_for_platform(
        self,
        filename: str,
        file_size: int | None = None,
    ) -> FileValidationResult:
        """
        平台端文件验证 / Platform-side file validation.

        使用平台配置进行验证

        Args:
            filename: 文件名
            file_size: 文件大小（字节），可选

        Returns:
            验证结果
        """
        extension = self._get_extension(filename)

        # 获取平台配置 / Get platform config
        allowed_extensions = await self._get_platform_allowed_extensions()
        denied_extensions = await self._get_platform_denied_extensions()
        max_size_mb = await self._get_platform_max_file_size()

        # 验证扩展名 / Validate extension
        ext_result = self._validate_extension(
            extension, allowed_extensions, denied_extensions
        )
        if not ext_result.allowed:
            return ext_result

        # 验证文件大小 / Validate file size
        if file_size is not None and max_size_mb > 0:
            size_result = self._validate_size(file_size, max_size_mb)
            if not size_result.allowed:
                return size_result

        return FileValidationResult.ok()

    async def validate_for_tenant(
        self,
        tenant_id: int,
        filename: str,
        file_size: int | None = None,
    ) -> FileValidationResult:
        """
        企业端文件验证 / Tenant-side file validation.

        优先使用企业配置，如果企业未配置则使用平台配置

        Args:
            tenant_id: 企业 ID
            filename: 文件名
            file_size: 文件大小（字节），可选

        Returns:
            验证结果
        """
        _ = file_size
        extension = self._get_extension(filename)

        # 获取企业配置（留空则使用平台配置）/ Get tenant config (empty = platform)
        tenant_allowed = await self._get_tenant_allowed_extensions(tenant_id)
        tenant_denied = await self._get_tenant_denied_extensions(tenant_id)

        # 如果企业未配置，则使用平台配置 / Fallback to platform if tenant not configured
        if not tenant_allowed:
            tenant_allowed = await self._get_platform_allowed_extensions()
        if not tenant_denied:
            tenant_denied = await self._get_platform_denied_extensions()

        # 验证扩展名 / Validate extension
        ext_result = self._validate_extension(
            extension, tenant_allowed, tenant_denied
        )
        if not ext_result.allowed:
            return ext_result

        # 文件大小验证统一由 AttachmentService._check_quota() 处理；此处不重复验证 / File size validated by AttachmentService._check_quota()

        return FileValidationResult.ok()

    def _get_extension(self, filename: str) -> str:
        """获取文件扩展名（小写，不含点）/ Get file extension (lowercase, no dot)"""
        if not filename:
            return ""
        return Path(filename).suffix.lstrip(".").lower()

    def _validate_extension(
        self,
        extension: str,
        allowed_extensions: set[str],
        denied_extensions: set[str],
    ) -> FileValidationResult:
        """
        验证文件扩展名 / Validate file extension.

        规则：1. 禁止列表直接拒绝 2. 允许列表为空则通过 3. 否则须在允许列表中
        Rules: deny list rejects; empty allow list passes; else must be in allow list.
        """
        # 禁止列表优先级最高 / Deny list has highest priority
        if extension in denied_extensions:
            return FileValidationResult.denied(
                message=_("file.extension_denied", extension=extension),
                code=ErrorCode.INVALID_PARAMETER,
            )

        # 如果允许列表为空，表示不限制 / Empty allow list = no restriction
        if not allowed_extensions:
            return FileValidationResult.ok()

        # 检查是否在允许列表中 / Check if in allow list
        if extension not in allowed_extensions:
            return FileValidationResult.denied(
                message=_("file.extension_not_allowed", extension=extension),
                code=ErrorCode.INVALID_PARAMETER,
            )

        return FileValidationResult.ok()

    def _validate_size(
        self,
        file_size: int,
        max_size_mb: int,
    ) -> FileValidationResult:
        """验证文件大小 / Validate file size"""
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            return FileValidationResult.denied(
                message=_("file.file_too_large"),
                code=ErrorCode.INVALID_PARAMETER,
            )
        return FileValidationResult.ok()

    def _parse_extensions(self, value: str) -> set[str]:
        """解析扩展名配置字符串为集合 / Parse extension config string to set"""
        if not value:
            return set()
        # 支持逗号分隔，去除空格，转小写 / Support comma-separated, strip, lowercase
        extensions = set()
        for ext in str(value).split(","):
            ext = ext.strip().lower().lstrip(".")
            if ext:
                extensions.add(ext)
        return extensions

    # ========== 配置获取方法 ========== / ========== Config accessors ==========

    async def _get_platform_allowed_extensions(self) -> set[str]:
        """获取平台允许的扩展名 / Get platform allowed extensions"""
        if self._platform_allowed is None:
            value = await self._config_service.get_platform_config(
                "platform_storage_allowed_extensions",
                default="",
            )
            self._platform_allowed = self._parse_extensions(str(value))
        return self._platform_allowed

    async def _get_platform_denied_extensions(self) -> set[str]:
        """获取平台禁止的扩展名 / Get platform denied extensions"""
        if self._platform_denied is None:
            value = await self._config_service.get_platform_config(
                "platform_storage_denied_extensions",
                default="",
            )
            self._platform_denied = self._parse_extensions(str(value))
        return self._platform_denied

    async def _get_platform_max_file_size(self) -> int:
        """获取平台最大文件大小（MB）/ Get platform max file size (MB)"""
        if self._platform_max_size_mb is None:
            value = await self._config_service.get_platform_config(
                "platform_storage_max_file_size_mb",
                default=100,
            )
            self._platform_max_size_mb = int(value) if value else 100
        return self._platform_max_size_mb

    async def _get_tenant_allowed_extensions(self, tenant_id: int) -> set[str]:
        """获取企业允许的扩展名 / Get tenant allowed extensions"""
        value = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_allowed_extensions",
            default="",
        )
        return self._parse_extensions(str(value))

    async def _get_tenant_denied_extensions(self, tenant_id: int) -> set[str]:
        """获取企业禁止的扩展名 / Get tenant denied extensions"""
        value = await self._config_service.get_tenant_config(
            tenant_id,
            "tenant_storage_denied_extensions",
            default="",
        )
        return self._parse_extensions(str(value))


def validate_result_or_raise(result: FileValidationResult) -> None:
    """
    验证结果，如果不通过则抛出异常 / Validate result and raise if failed.

    Args:
        result: 验证结果

    Raises:
        BusinessException: 验证失败时抛出
    """
    if not result.allowed:
        raise BusinessException(
            message=result.message or _("file.validation_failed"),
            code=result.code or ErrorCode.INVALID_PARAMETER,
        )


__all__ = [
    "FileValidator",
    "FileValidationResult",
    "validate_result_or_raise",
]
