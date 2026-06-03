"""Storage billing plugin enums. / 对象存储对账计费插件枚举。"""

from app.enums.base import StrEnum


class StorageProviderCodeEnum(StrEnum):
    QINIU_KODO = "qiniu-kodo"
    ALIYUN_OSS = "aliyun-oss"
    TENCENT_COS = "tencent-cos"


class StorageBillingRunStatusEnum(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_GAPS = "completed_with_gaps"
    FAILED = "failed"
    SKIPPED = "skipped"


class StorageBillingSourceStatusEnum(StrEnum):
    PENDING = "pending"
    FETCHED = "fetched"
    COMPLETED_WITH_GAPS = "completed_with_gaps"
    EMPTY = "empty"
    SKIPPED = "skipped"
    FAILED = "failed"
    NOT_IMPLEMENTED = "not_implemented"


class StorageBillingStatementStatusEnum(StrEnum):
    DRAFT = "draft"
    GENERATED = "generated"
    PUBLISHED = "published"


class StorageBillingChargeBasisEnum(StrEnum):
    EGRESS_TRAFFIC = "egress_traffic"
    CDN_ORIGIN_EGRESS = "cdn_origin_egress"
    TRANSFER_ACCELERATION_EGRESS = "transfer_acceleration_egress"
    DATA_PROCESSING = "data_processing"


class StorageBillingPeriodTypeEnum(StrEnum):
    DAILY = "daily"
    MONTHLY = "monthly"


class StorageBillingModeEnum(StrEnum):
    OFFICIAL_RECONCILED = "official_reconciled"
    OFFICIAL_PASS_THROUGH = "official_pass_through"


class StorageBillingScopeTypeEnum(StrEnum):
    BUCKET = "bucket"
    DOMAIN = "domain"
    ACCOUNT = "account"
    TAG = "tag"


class StorageBillingValidationStatusEnum(StrEnum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"


__all__ = [
    "StorageBillingChargeBasisEnum",
    "StorageBillingModeEnum",
    "StorageBillingPeriodTypeEnum",
    "StorageBillingRunStatusEnum",
    "StorageBillingScopeTypeEnum",
    "StorageBillingSourceStatusEnum",
    "StorageBillingStatementStatusEnum",
    "StorageBillingValidationStatusEnum",
    "StorageProviderCodeEnum",
]
