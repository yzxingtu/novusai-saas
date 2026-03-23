"""Shared constants for storage billing plugin."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import StorageBillingPeriodTypeEnum, StorageProviderCodeEnum

SUPPORTED_CLOUD_DRIVERS = [
    StorageProviderCodeEnum.QINIU_KODO.value,
    StorageProviderCodeEnum.ALIYUN_OSS.value,
    StorageProviderCodeEnum.TENCENT_COS.value,
]
EXCLUDED_DRIVERS = ["local"]

DEFAULT_PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    StorageProviderCodeEnum.QINIU_KODO.value: {
        "enabled": False,
        "profile_code": "qiniu-default",
        "bill_source": "finance_api",
        "access_key": "",
        "secret_key": "",
        "account_identifier": "",
    },
    StorageProviderCodeEnum.ALIYUN_OSS.value: {
        "enabled": False,
        "profile_code": "aliyun-default",
        "bill_source": "bss_openapi",
        "region": "",
        "access_key_id": "",
        "access_key_secret": "",
        "bill_bucket": "",
        "bill_prefix": "",
        "account_identifier": "",
    },
    StorageProviderCodeEnum.TENCENT_COS.value: {
        "enabled": False,
        "profile_code": "tencent-default",
        "bill_source": "describe_bill_detail",
        "region": "",
        "secret_id": "",
        "secret_key": "",
        "bill_bucket": "",
        "bill_prefix": "",
        "account_identifier": "",
    },
}

PROVIDER_SECRET_FIELDS: dict[str, list[str]] = {
    StorageProviderCodeEnum.QINIU_KODO.value: ["access_key", "secret_key"],
    StorageProviderCodeEnum.ALIYUN_OSS.value: ["access_key_id", "access_key_secret"],
    StorageProviderCodeEnum.TENCENT_COS.value: ["secret_id", "secret_key"],
}

PROVIDER_REQUIRED_FIELDS_BY_BILL_SOURCE: dict[str, dict[str, list[str]]] = {
    StorageProviderCodeEnum.QINIU_KODO.value: {
        "finance_api": [
            "profile_code",
            "bill_source",
            "access_key",
            "secret_key",
            "account_identifier",
        ],
    },
    StorageProviderCodeEnum.ALIYUN_OSS.value: {
        "oss_subscription": [
            "profile_code",
            "bill_source",
            "region",
            "access_key_id",
            "access_key_secret",
            "bill_bucket",
        ],
        "bss_openapi": [
            "profile_code",
            "bill_source",
            "region",
            "access_key_id",
            "access_key_secret",
        ],
    },
    StorageProviderCodeEnum.TENCENT_COS.value: {
        "cos_bill_bucket": [
            "profile_code",
            "bill_source",
            "region",
            "secret_id",
            "secret_key",
            "bill_bucket",
        ],
        "describe_bill_detail": [
            "profile_code",
            "bill_source",
            "region",
            "secret_id",
            "secret_key",
        ],
    },
}

PROVIDER_BILL_SOURCES: dict[str, list[str]] = {
    StorageProviderCodeEnum.QINIU_KODO.value: ["finance_api"],
    StorageProviderCodeEnum.ALIYUN_OSS.value: ["oss_subscription", "bss_openapi"],
    StorageProviderCodeEnum.TENCENT_COS.value: ["cos_bill_bucket", "describe_bill_detail"],
}

COLLECTOR_IMPLEMENTATION_STATUS: dict[str, bool] = {
    StorageProviderCodeEnum.QINIU_KODO.value: True,
    StorageProviderCodeEnum.ALIYUN_OSS.value: True,
    StorageProviderCodeEnum.TENCENT_COS.value: True,
}

PROVIDER_IMPLEMENTED_BILL_SOURCES: dict[str, list[str]] = {
    StorageProviderCodeEnum.QINIU_KODO.value: ["finance_api"],
    StorageProviderCodeEnum.ALIYUN_OSS.value: ["bss_openapi"],
    StorageProviderCodeEnum.TENCENT_COS.value: ["describe_bill_detail"],
}

PROVIDER_BILL_SOURCE_CAPABILITIES: dict[str, dict[str, dict[str, Any]]] = {
    StorageProviderCodeEnum.QINIU_KODO.value: {
        "finance_api": {
            "implemented": True,
            "settlement_mode": "monthly_settled",
            "settlement_cycle": StorageBillingPeriodTypeEnum.MONTHLY.value,
            "strict_daily_reconciliation_supported": False,
            "manual_pull_supported": True,
            "scheduled_daily_supported": False,
            "supported_period_types": [StorageBillingPeriodTypeEnum.MONTHLY.value],
            "recommended_scope_types": ["account"],
            "capability_message": (
                "Qiniu official billing is monthly-settled only. "
                "Strict daily reconciliation is unsupported. "
                "Use a dedicated Qiniu account with account-scope bindings."
            ),
        },
    },
    StorageProviderCodeEnum.ALIYUN_OSS.value: {
        "oss_subscription": {
            "implemented": False,
            "settlement_mode": "unsupported",
            "settlement_cycle": StorageBillingPeriodTypeEnum.DAILY.value,
            "strict_daily_reconciliation_supported": False,
            "manual_pull_supported": False,
            "scheduled_daily_supported": False,
            "supported_period_types": [],
            "recommended_scope_types": [],
            "capability_message": "Aliyun OSS bill subscription ingestion is not implemented yet.",
        },
        "bss_openapi": {
            "implemented": True,
            "settlement_mode": "strict_daily_reconciliation",
            "settlement_cycle": StorageBillingPeriodTypeEnum.DAILY.value,
            "strict_daily_reconciliation_supported": True,
            "manual_pull_supported": True,
            "scheduled_daily_supported": True,
            "supported_period_types": [StorageBillingPeriodTypeEnum.DAILY.value],
            "recommended_scope_types": ["bucket", "domain", "account", "tag"],
            "capability_message": (
                "Aliyun OSS official billing follows the strict daily D-2 reconciliation path."
            ),
        },
    },
    StorageProviderCodeEnum.TENCENT_COS.value: {
        "cos_bill_bucket": {
            "implemented": False,
            "settlement_mode": "unsupported",
            "settlement_cycle": StorageBillingPeriodTypeEnum.DAILY.value,
            "strict_daily_reconciliation_supported": False,
            "manual_pull_supported": False,
            "scheduled_daily_supported": False,
            "supported_period_types": [],
            "recommended_scope_types": [],
            "capability_message": "Tencent COS bill-bucket ingestion is not implemented yet.",
        },
        "describe_bill_detail": {
            "implemented": True,
            "settlement_mode": "strict_daily_reconciliation",
            "settlement_cycle": StorageBillingPeriodTypeEnum.DAILY.value,
            "strict_daily_reconciliation_supported": True,
            "manual_pull_supported": True,
            "scheduled_daily_supported": True,
            "supported_period_types": [StorageBillingPeriodTypeEnum.DAILY.value],
            "recommended_scope_types": ["bucket", "domain", "account", "tag"],
            "capability_message": (
                "Tencent COS official billing follows the strict daily D-2 reconciliation path."
            ),
        },
    },
}


def get_provider_required_fields(
    provider: str,
    bill_source: str | None = None,
) -> list[str]:
    source_map = PROVIDER_REQUIRED_FIELDS_BY_BILL_SOURCE.get(provider) or {}
    normalized_source = str(bill_source or "").strip()
    if normalized_source and normalized_source in source_map:
        return list(source_map[normalized_source])

    if not source_map:
        return []

    first_source = next(iter(source_map.values()))
    return list(first_source)


def get_provider_implemented_bill_sources(provider: str) -> list[str]:
    return list(PROVIDER_IMPLEMENTED_BILL_SOURCES.get(provider) or [])


def get_provider_bill_source_capability(
    provider: str,
    bill_source: str | None = None,
) -> dict[str, Any]:
    source_map = PROVIDER_BILL_SOURCE_CAPABILITIES.get(provider) or {}
    normalized_source = str(bill_source or "").strip()
    if normalized_source and normalized_source in source_map:
        return deepcopy(source_map[normalized_source])

    if not source_map:
        return {
            "implemented": False,
            "settlement_mode": "unsupported",
            "settlement_cycle": StorageBillingPeriodTypeEnum.DAILY.value,
            "strict_daily_reconciliation_supported": False,
            "manual_pull_supported": False,
            "scheduled_daily_supported": False,
            "supported_period_types": [],
            "recommended_scope_types": [],
            "capability_message": "",
        }

    first_source = next(iter(source_map.values()))
    return deepcopy(first_source)


def get_default_provider_profiles() -> dict[str, dict[str, Any]]:
    return deepcopy(DEFAULT_PROVIDER_PROFILES)
