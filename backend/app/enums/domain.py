"""
域名相关枚举

定义域名 SSL 状态、域名类型等枚举
"""

from app.enums.base import LabeledStrEnum


class DomainSslStatus(LabeledStrEnum):
    """域名 SSL 证书状态枚举"""

    NONE = ("none", "enum.domain_ssl_status.none")
    PENDING = ("pending", "enum.domain_ssl_status.pending")
    PROVISIONING = ("provisioning", "enum.domain_ssl_status.provisioning")
    ACTIVE = ("active", "enum.domain_ssl_status.active")
    FAILED = ("failed", "enum.domain_ssl_status.failed")
    EXPIRED = ("expired", "enum.domain_ssl_status.expired")


class DomainType(LabeledStrEnum):
    """域名类型枚举"""

    DEFAULT = ("default", "enum.domain_type.default")
    CUSTOM = ("custom", "enum.domain_type.custom")


class SslCertType(LabeledStrEnum):
    """SSL 证书类型枚举"""

    PLATFORM = ("platform", "enum.ssl_cert_type.platform")
    CUSTOM = ("custom", "enum.ssl_cert_type.custom")


class SslCertStatus(LabeledStrEnum):
    """SSL 证书记录状态枚举"""

    PENDING = ("pending", "enum.ssl_cert_status.pending")
    ACTIVE = ("active", "enum.ssl_cert_status.active")
    EXPIRED = ("expired", "enum.ssl_cert_status.expired")
    REVOKED = ("revoked", "enum.ssl_cert_status.revoked")
    FAILED = ("failed", "enum.ssl_cert_status.failed")


__all__ = ["DomainSslStatus", "DomainType", "SslCertType", "SslCertStatus"]
