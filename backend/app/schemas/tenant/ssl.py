"""
SSL 证书 Schema / SSL Certificate Schema

定义 SSL 证书管理相关的请求和响应数据结构
Defines SSL certificate management request and response data structures.
"""

from datetime import datetime

from pydantic import Field, field_validator

from app.core.base_schema import BaseSchema
from app.core.i18n import _


class SslCertificateResponse(BaseSchema):
    """SSL 证书详情响应（不含私钥）"""

    id: int = Field(..., description="证书 ID")
    domain_id: int = Field(..., description="域名 ID")
    tenant_id: int = Field(..., description="企业 ID")
    cert_type: str = Field(..., description="证书类型: platform/custom")
    status: str = Field(..., description="证书状态: pending/active/expired/revoked/failed")
    issuer: str | None = Field(None, description="签发机构")
    serial_number: str | None = Field(None, description="证书序列号")
    issued_at: datetime | None = Field(None, description="签发时间")
    expires_at: datetime | None = Field(None, description="到期时间")
    auto_renew: bool = Field(False, description="是否自动续期")
    has_certificate: bool = Field(False, description="是否已有证书内容")
    has_private_key: bool = Field(False, description="是否已有私钥")
    has_chain: bool = Field(False, description="是否有证书链")
    last_renewal_attempt: datetime | None = Field(None, description="最近续期尝试时间")
    renewal_error: str | None = Field(None, description="最近续期失败原因")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    @classmethod
    def from_model(cls, cert) -> "SslCertificateResponse":
        """从模型实例构建响应（隐藏敏感字段）"""
        return cls(
            id=cert.id,
            domain_id=cert.domain_id,
            tenant_id=cert.tenant_id,
            cert_type=cert.cert_type,
            status=cert.status,
            issuer=cert.issuer,
            serial_number=cert.serial_number,
            issued_at=cert.issued_at,
            expires_at=cert.expires_at,
            auto_renew=cert.auto_renew,
            has_certificate=bool(cert.certificate),
            has_private_key=bool(cert.private_key_encrypted),
            has_chain=bool(cert.certificate_chain),
            last_renewal_attempt=cert.last_renewal_attempt,
            renewal_error=cert.renewal_error,
            created_at=cert.created_at,
            updated_at=cert.updated_at,
        )


class SslCertificateUploadRequest(BaseSchema):
    """自定义证书上传请求"""

    certificate: str = Field(
        ...,
        min_length=50,
        description="PEM 格式证书内容",
    )
    private_key: str = Field(
        ...,
        min_length=50,
        description="PEM 格式私钥内容",
    )
    certificate_chain: str | None = Field(
        None,
        description="PEM 格式证书链（中间证书，可选）",
    )

    @field_validator("certificate")
    @classmethod
    def validate_certificate(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("-----BEGIN CERTIFICATE-----"):
            raise ValueError(_("ssl_certificate.invalid_cert_format"))
        return v

    @field_validator("private_key")
    @classmethod
    def validate_private_key(cls, v: str) -> str:
        v = v.strip()
        if not (
            v.startswith("-----BEGIN PRIVATE KEY-----")
            or v.startswith("-----BEGIN RSA PRIVATE KEY-----")
            or v.startswith("-----BEGIN EC PRIVATE KEY-----")
        ):
            raise ValueError(_("ssl_certificate.invalid_key_format"))
        return v

    @field_validator("certificate_chain")
    @classmethod
    def validate_chain(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if v and not v.startswith("-----BEGIN CERTIFICATE-----"):
            raise ValueError(_("ssl_certificate.invalid_chain_format"))
        return v or None


class SslAutoRenewRequest(BaseSchema):
    """自动续期开关请求"""

    auto_renew: bool = Field(..., description="是否开启自动续期")


class SslReplaceRequest(BaseSchema):
    """管理员强制替换证书请求（Admin 独有）"""

    mode: str = Field(
        ...,
        description="替换模式: platform(重新ACME签发) / custom(上传新证书)",
    )
    certificate: str | None = Field(
        None,
        description="PEM 格式证书内容（mode=custom 时必填）",
    )
    private_key: str | None = Field(
        None,
        description="PEM 格式私钥内容（mode=custom 时必填）",
    )
    certificate_chain: str | None = Field(
        None,
        description="PEM 格式证书链（mode=custom 时可选）",
    )

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ("platform", "custom"):
            raise ValueError(_("ssl_certificate.invalid_replace_mode"))
        return v


__all__ = [
    "SslCertificateResponse",
    "SslCertificateUploadRequest",
    "SslAutoRenewRequest",
    "SslReplaceRequest",
]
