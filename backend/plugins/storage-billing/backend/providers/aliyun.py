"""Alibaba Cloud OSS official billing adapter. / 阿里云 OSS 官方账单适配器。"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest

from ..models import StorageBillingChargeBasisEnum
from .base import BillingChargeItem, BillingFetchRequest, BillingFetchResult

_API_ACTION = "DescribeSplitItemBill"
_API_DOMAIN = "business.aliyuncs.com"
_API_PRODUCT = "BssOpenApi"
_API_VERSION = "2017-12-14"
_DEFAULT_REGION = "cn-hangzhou"
_MAX_PAGE_LIMIT = 300
_OSS_PRODUCT_CODES = {"oss"}


def _stringify(value: Any) -> str:
    return str(value or "").strip()


def _decimal_from_value(value: Any) -> Decimal:
    text = _stringify(value)
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _int_from_value(value: Any) -> int:
    text = _stringify(value)
    if not text:
        return 0
    try:
        return int(Decimal(text))
    except (InvalidOperation, ValueError):
        return 0


def _bytes_from_usage(value: Any, unit: Any) -> int:
    amount = _decimal_from_value(value)
    normalized_unit = _stringify(unit).lower()
    unit_map = {
        "byte": Decimal("1"),
        "bytes": Decimal("1"),
        "b": Decimal("1"),
        "kb": Decimal("1024"),
        "kib": Decimal("1024"),
        "mb": Decimal("1048576"),
        "mib": Decimal("1048576"),
        "gb": Decimal("1073741824"),
        "gib": Decimal("1073741824"),
        "tb": Decimal("1099511627776"),
        "tib": Decimal("1099511627776"),
    }
    multiplier = unit_map.get(normalized_unit)
    if multiplier is None:
        return 0
    try:
        return int(amount * multiplier)
    except (InvalidOperation, OverflowError, ValueError):
        return 0


def _serialize_charge_item(item: BillingChargeItem) -> dict[str, Any]:
    return {
        "charge_basis": item.charge_basis,
        "amount_total": str(item.amount_total),
        "usage_bytes": item.usage_bytes,
        "currency": item.currency,
        "resource_id": item.resource_id,
        "resource_name": item.resource_name,
        "bucket_name": item.bucket_name,
        "domain_name": item.domain_name,
        "account_identifier": item.account_identifier,
        "tag_values": dict(item.tag_values or {}),
        "details_json": dict(item.details_json or {}),
    }


class AliyunOssOfficialBillAdapter:
    provider_code = "aliyun-oss"

    async def fetch_official_bill(
        self,
        request: BillingFetchRequest,
    ) -> BillingFetchResult:
        profile = dict(request.profile or {})
        bill_source = _stringify(profile.get("bill_source"))
        if bill_source != "bss_openapi":
            return BillingFetchResult(
                provider_code=self.provider_code,
                driver_code=request.driver_code,
                billing_date=request.billing_date,
                source_status="not_implemented",
                error_message=(
                    f"Alibaba Cloud official bill source '{bill_source or '-'}' is not implemented yet."
                ),
                raw_payload_json={
                    "provider": self.provider_code,
                    "bill_source": bill_source,
                    "state": "source_not_implemented",
                },
            )

        access_key_id = _stringify(profile.get("access_key_id"))
        access_key_secret = _stringify(profile.get("access_key_secret"))
        region = _stringify(profile.get("region")) or _DEFAULT_REGION
        account_identifier = _stringify(profile.get("account_identifier"))
        missing = [
            field
            for field, value in (
                ("access_key_id", access_key_id),
                ("access_key_secret", access_key_secret),
                ("region", region),
            )
            if not value
        ]
        if missing:
            return BillingFetchResult(
                provider_code=self.provider_code,
                driver_code=request.driver_code,
                billing_date=request.billing_date,
                source_status="failed",
                error_message=f"Missing Aliyun billing config fields: {', '.join(missing)}",
                raw_payload_json={
                    "provider": self.provider_code,
                    "bill_source": bill_source,
                    "missing_fields": missing,
                },
            )

        try:
            charge_items, page_count, total_count = await asyncio.to_thread(
                self._collect_daily_split_items,
                billing_date=request.billing_date,
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                region=region,
                configured_account_identifier=account_identifier,
            )
        except Exception as exc:
            return BillingFetchResult(
                provider_code=self.provider_code,
                driver_code=request.driver_code,
                billing_date=request.billing_date,
                source_status="failed",
                error_message=str(exc),
                raw_payload_json={
                    "provider": self.provider_code,
                    "bill_source": bill_source,
                    "state": "api_failed",
                },
            )

        source_status = "fetched" if charge_items else "empty"
        return BillingFetchResult(
            provider_code=self.provider_code,
            driver_code=request.driver_code,
            billing_date=request.billing_date,
            source_status=source_status,
            source_ref=f"describe_split_item_bill:{request.billing_date.isoformat()}",
            currency="CNY",
            amount_total=sum(
                (item.amount_total for item in charge_items), Decimal("0")
            ),
            usage_bytes=sum(item.usage_bytes for item in charge_items),
            charge_items=charge_items,
            raw_payload_json={
                "provider": self.provider_code,
                "bill_source": bill_source,
                "target_date": request.billing_date.isoformat(),
                "page_count": page_count,
                "record_total": total_count,
                "item_count": len(charge_items),
                "charge_items": [_serialize_charge_item(item) for item in charge_items],
            },
        )

    def _collect_daily_split_items(
        self,
        *,
        billing_date: date,
        access_key_id: str,
        access_key_secret: str,
        region: str,
        configured_account_identifier: str,
    ) -> tuple[list[BillingChargeItem], int, int]:
        client = AcsClient(access_key_id, access_key_secret, region)
        next_token = ""
        page_count = 0
        total_count = 0
        items: list[BillingChargeItem] = []

        while True:
            request = CommonRequest()
            request.set_accept_format("json")
            request.set_protocol_type("https")
            request.set_method("GET")
            request.set_domain(_API_DOMAIN)
            request.set_product(_API_PRODUCT)
            request.set_version(_API_VERSION)
            request.set_action_name(_API_ACTION)
            request.add_query_param("BillingCycle", billing_date.strftime("%Y-%m"))
            request.add_query_param("Granularity", "DAILY")
            request.add_query_param("BillingDate", billing_date.isoformat())
            request.add_query_param("ProductCode", "oss")
            request.add_query_param("MaxResults", _MAX_PAGE_LIMIT)
            request.add_query_param("IsHideZeroCharge", "false")
            if next_token:
                request.add_query_param("NextToken", next_token)
            if configured_account_identifier.isdigit():
                request.add_query_param(
                    "BillOwnerId", int(configured_account_identifier)
                )

            raw_payload = client.do_action_with_exception(request)
            payload = json.loads(
                raw_payload.decode("utf-8")
                if isinstance(raw_payload, (bytes, bytearray))
                else str(raw_payload or "")
            )
            if not isinstance(payload, Mapping):
                raise RuntimeError("Aliyun BSS OpenAPI returned invalid payload.")
            if _stringify(payload.get("Success")).lower() not in {"true", "1"}:
                code = _stringify(payload.get("Code"))
                message = (
                    _stringify(payload.get("Message"))
                    or "Aliyun BSS OpenAPI request failed."
                )
                raise RuntimeError(
                    f"Aliyun BSS OpenAPI error: {code or 'Unknown'} {message}".strip()
                )

            data = payload.get("Data")
            if not isinstance(data, Mapping):
                raise RuntimeError("Aliyun BSS OpenAPI returned invalid data payload.")

            raw_items = self._extract_items(data.get("Items"))
            page_count += 1
            if page_count == 1:
                total_count = _int_from_value(data.get("TotalCount")) or len(raw_items)
            items.extend(
                self._normalize_items(
                    raw_items,
                    configured_account_identifier=configured_account_identifier,
                )
            )

            next_token = _stringify(data.get("NextToken"))
            if not raw_items or not next_token:
                break

        return items, page_count, total_count

    def _extract_items(self, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, Mapping)]
        if not isinstance(value, Mapping):
            return []
        item_value = value.get("Item")
        if isinstance(item_value, list):
            return [dict(item) for item in item_value if isinstance(item, Mapping)]
        return []

    def _normalize_items(
        self,
        raw_items: Iterable[dict[str, Any]],
        *,
        configured_account_identifier: str,
    ) -> list[BillingChargeItem]:
        result: list[BillingChargeItem] = []
        for item in raw_items:
            if not self._is_oss_item(item):
                continue

            charge_basis = self._detect_charge_basis(item)
            if not charge_basis:
                continue

            amount_total = _decimal_from_value(
                item.get("PretaxAmount")
                or item.get("AfterDiscountAmount")
                or item.get("PaymentAmount")
            )
            usage_bytes = _bytes_from_usage(item.get("Usage"), item.get("UsageUnit"))
            if amount_total == Decimal("0") and usage_bytes == 0:
                continue

            split_item_id = _stringify(item.get("SplitItemID"))
            split_item_name = _stringify(item.get("SplitItemName"))
            item_name = _stringify(item.get("ItemName"))
            account_identifier = (
                _stringify(item.get("BillAccountID"))
                or _stringify(item.get("OwnerID"))
                or _stringify(item.get("SplitAccountID"))
                or configured_account_identifier
            )
            result.append(
                BillingChargeItem(
                    charge_basis=charge_basis,
                    amount_total=amount_total,
                    usage_bytes=usage_bytes,
                    currency=_stringify(item.get("Currency")) or "CNY",
                    resource_id=split_item_id or split_item_name,
                    resource_name=split_item_name or item_name or split_item_id,
                    bucket_name=split_item_name or item_name,
                    account_identifier=account_identifier,
                    tag_values=self._parse_tags(item.get("Tag")),
                    details_json={
                        "billing_item": _stringify(item.get("BillingItem")),
                        "billing_item_code": _stringify(item.get("BillingItemCode")),
                        "product_name": _stringify(item.get("ProductName")),
                        "product_detail": _stringify(item.get("ProductDetail")),
                        "split_product_detail": _stringify(
                            item.get("SplitProductDetail")
                        ),
                        "subscription_type": _stringify(item.get("SubscriptionType")),
                        "billing_date": _stringify(item.get("BillingDate")),
                        "split_billing_date": _stringify(item.get("SplitBillingDate")),
                        "usage": _stringify(item.get("Usage")),
                        "usage_unit": _stringify(item.get("UsageUnit")),
                        "region": _stringify(item.get("Region")),
                        "zone": _stringify(item.get("Zone")),
                        "bucket_aliases": [
                            alias
                            for alias in (split_item_name, split_item_id, item_name)
                            if alias
                        ],
                    },
                )
            )
        return result

    def _is_oss_item(self, item: Mapping[str, Any]) -> bool:
        product_code = _stringify(item.get("ProductCode")).lower()
        pip_code = _stringify(item.get("PipCode")).lower()
        texts = " ".join(
            filter(
                None,
                [
                    product_code,
                    pip_code,
                    _stringify(item.get("ProductName")).lower(),
                    _stringify(item.get("ProductDetail")).lower(),
                    _stringify(item.get("SplitProductDetail")).lower(),
                ],
            )
        )
        if product_code in _OSS_PRODUCT_CODES or pip_code in _OSS_PRODUCT_CODES:
            return True
        return "对象存储" in texts or "oss" in texts

    def _detect_charge_basis(self, item: Mapping[str, Any]) -> str:
        texts = [
            _stringify(item.get("BillingItem")).lower(),
            _stringify(item.get("BillingItemCode")).lower(),
            _stringify(item.get("ProductName")).lower(),
            _stringify(item.get("ProductDetail")).lower(),
            _stringify(item.get("SplitProductDetail")).lower(),
            _stringify(item.get("ItemName")).lower(),
        ]
        joined = " ".join(text for text in texts if text)

        if any(
            keyword in joined for keyword in ("传输加速", "accelerate", "acceleration")
        ):
            return StorageBillingChargeBasisEnum.TRANSFER_ACCELERATION_EGRESS.value
        if any(keyword in joined for keyword in ("回源", "origin")):
            return StorageBillingChargeBasisEnum.CDN_ORIGIN_EGRESS.value
        if any(keyword in joined for keyword in ("数据处理", "process")):
            return StorageBillingChargeBasisEnum.DATA_PROCESSING.value
        if any(
            keyword in joined
            for keyword in (
                "公网",
                "外网",
                "下行",
                "流出",
                "流量",
                "bandwidth",
                "download",
                "egress",
                "traffic",
            )
        ):
            return StorageBillingChargeBasisEnum.EGRESS_TRAFFIC.value
        return ""

    def _parse_tags(self, value: Any) -> dict[str, str]:
        text = _stringify(value)
        if not text:
            return {}

        result: dict[str, str] = {}
        for key, tag_value in re.findall(
            r"key:(.*?)\s+value:(.*?)(?:;|$)", text, flags=re.IGNORECASE
        ):
            normalized_key = key.strip()
            if not normalized_key:
                continue
            result[normalized_key] = tag_value.strip()
        return result


__all__ = ["AliyunOssOfficialBillAdapter"]
