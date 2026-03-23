"""Provider adapter registry. / 提供方适配器注册表。"""

from __future__ import annotations

from functools import lru_cache

from .base import OfficialBillAdapter


@lru_cache(maxsize=1)
def _build_adapters() -> dict[str, OfficialBillAdapter]:
    from .aliyun import AliyunOssOfficialBillAdapter
    from .qiniu import QiniuKodoOfficialBillAdapter
    from .tencent import TencentCosOfficialBillAdapter

    return {
        "qiniu-kodo": QiniuKodoOfficialBillAdapter(),
        "aliyun-oss": AliyunOssOfficialBillAdapter(),
        "tencent-cos": TencentCosOfficialBillAdapter(),
    }


def get_provider_adapter(driver_code: str) -> OfficialBillAdapter | None:
    return _build_adapters().get(str(driver_code or "").strip())


def get_supported_provider_codes() -> list[str]:
    return list(_build_adapters().keys())
