"""Tencent COS official billing adapter. / 腾讯云 COS 官方账单适配器。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from ..models import StorageBillingChargeBasisEnum
from .base import BillingChargeItem, BillingFetchRequest, BillingFetchResult

_API_ACTION = "DescribeBillDetail"
_API_ENDPOINT = "https://billing.tencentcloudapi.com"
_API_HOST = "billing.tencentcloudapi.com"
_API_SERVICE = "billing"
_API_VERSION = "2018-07-09"
_MAX_PAGE_LIMIT = 300
_TIMEOUT = 60.0
_COS_BUSINESS_CODES = {"p_cos"}


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


def _normalize_config_pairs(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        result.append(
            {
                "name": _stringify(item.get("Name")),
                "value": _stringify(item.get("Value")),
            }
        )
    return result


def _normalize_tags(value: Any) -> dict[str, str]:
    if not isinstance(value, list):
        return {}

    result: dict[str, str] = {}
    for item in value:
        if not isinstance(item, Mapping):
            continue
        key = _stringify(
            item.get("TagKey") or item.get("Key") or item.get("Name") or item.get("tagKey")
        )
        if not key:
            continue
        result[key] = _stringify(
            item.get("TagValue")
            or item.get("Value")
            or item.get("tagValue")
            or item.get("value")
        )
    return result


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


class TencentCosOfficialBillAdapter:
    provider_code = "tencent-cos"

    async def fetch_official_bill(
        self,
        request: BillingFetchRequest,
    ) -> BillingFetchResult:
        profile = dict(request.profile or {})
        bill_source = _stringify(profile.get("bill_source"))
        if bill_source != "describe_bill_detail":
            return BillingFetchResult(
                provider_code=self.provider_code,
                driver_code=request.driver_code,
                billing_date=request.billing_date,
                source_status="not_implemented",
                error_message=(
                    f"Tencent official bill source '{bill_source or '-'}' is not implemented yet."
                ),
                raw_payload_json={
                    "provider": self.provider_code,
                    "bill_source": bill_source,
                    "state": "source_not_implemented",
                },
            )

        secret_id = _stringify(profile.get("secret_id"))
        secret_key = _stringify(profile.get("secret_key"))
        region = _stringify(profile.get("region"))
        payer_uin = _stringify(profile.get("account_identifier"))

        missing = [
            field
            for field, value in (
                ("secret_id", secret_id),
                ("secret_key", secret_key),
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
                error_message=f"Missing Tencent billing config fields: {', '.join(missing)}",
                raw_payload_json={
                    "provider": self.provider_code,
                    "bill_source": bill_source,
                    "missing_fields": missing,
                },
            )

        try:
            charge_items, page_count, total_count = await self._collect_month_details(
                billing_date=request.billing_date,
                secret_id=secret_id,
                secret_key=secret_key,
                region=region,
                payer_uin=payer_uin,
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
            source_ref=f"describe_bill_detail:{request.billing_date.strftime('%Y-%m')}",
            currency="CNY",
            amount_total=sum((item.amount_total for item in charge_items), Decimal("0")),
            usage_bytes=sum(item.usage_bytes for item in charge_items),
            charge_items=charge_items,
            raw_payload_json={
                "provider": self.provider_code,
                "bill_source": bill_source,
                "target_date": request.billing_date.isoformat(),
                "month": request.billing_date.strftime("%Y-%m"),
                "page_count": page_count,
                "record_total": total_count,
                "item_count": len(charge_items),
                "charge_items": [_serialize_charge_item(item) for item in charge_items],
            },
        )

    async def _collect_month_details(
        self,
        *,
        billing_date: date,
        secret_id: str,
        secret_key: str,
        region: str,
        payer_uin: str,
    ) -> tuple[list[BillingChargeItem], int, int]:
        offset = 0
        total = 0
        context_token = ""
        page_count = 0
        normalized_items: list[BillingChargeItem] = []

        while True:
            payload = {
                "Offset": offset,
                "Limit": _MAX_PAGE_LIMIT,
                "Month": billing_date.strftime("%Y-%m"),
                "NeedRecordNum": 1 if page_count == 0 else 0,
            }
            if context_token:
                payload["Context"] = context_token
            if payer_uin:
                payload["PayerUin"] = payer_uin

            response = await self._request_api(
                payload=payload,
                secret_id=secret_id,
                secret_key=secret_key,
                region=region,
            )
            page_count += 1
            details = response.get("DetailSet") or []
            if page_count == 1:
                try:
                    total = int(response.get("Total") or len(details))
                except (TypeError, ValueError):
                    total = len(details)
            context_token = _stringify(response.get("Context"))

            for detail in details:
                normalized_items.extend(
                    self._normalize_detail_for_date(detail, billing_date)
                )

            offset += len(details)
            if not details or (total and offset >= total):
                break

        return normalized_items, page_count, total

    async def _request_api(
        self,
        *,
        payload: dict[str, Any],
        secret_id: str,
        secret_key: str,
        region: str,
    ) -> dict[str, Any]:
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        timestamp = int(time.time())
        date_stamp = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
            "%Y-%m-%d"
        )

        hashed_payload = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        canonical_headers = (
            "content-type:application/json; charset=utf-8\n"
            f"host:{_API_HOST}\n"
            f"x-tc-action:{_API_ACTION.lower()}\n"
        )
        signed_headers = "content-type;host;x-tc-action"
        canonical_request = (
            f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"
        )
        credential_scope = f"{date_stamp}/{_API_SERVICE}/tc3_request"
        string_to_sign = (
            "TC3-HMAC-SHA256\n"
            f"{timestamp}\n"
            f"{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )

        secret_date = hmac.new(
            f"TC3{secret_key}".encode("utf-8"),
            date_stamp.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        secret_service = hmac.new(
            secret_date,
            _API_SERVICE.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        secret_signing = hmac.new(
            secret_service,
            b"tc3_request",
            hashlib.sha256,
        ).digest()
        signature = hmac.new(
            secret_signing,
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        authorization = (
            "TC3-HMAC-SHA256 "
            f"Credential={secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": _API_HOST,
            "X-TC-Action": _API_ACTION,
            "X-TC-Version": _API_VERSION,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Region": region,
        }

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                _API_ENDPOINT,
                headers=headers,
                content=payload_json.encode("utf-8"),
            )
            response.raise_for_status()
            payload_json = response.json()

        body = payload_json.get("Response") if isinstance(payload_json, Mapping) else None
        if not isinstance(body, Mapping):
            raise RuntimeError("Tencent billing API returned invalid payload.")

        error_data = body.get("Error")
        if isinstance(error_data, Mapping):
            code = _stringify(error_data.get("Code"))
            message = _stringify(error_data.get("Message"))
            raise RuntimeError(f"Tencent billing API error: {code or 'Unknown'} {message}".strip())

        return dict(body)

    def _normalize_detail_for_date(
        self,
        detail: Any,
        billing_date: date,
    ) -> list[BillingChargeItem]:
        if not isinstance(detail, Mapping):
            return []

        if _stringify(detail.get("BusinessCode")) not in _COS_BUSINESS_CODES:
            return []

        bill_day = _stringify(detail.get("BillDay"))[:10]
        if bill_day != billing_date.isoformat():
            return []

        component_set = detail.get("ComponentSet")
        if not isinstance(component_set, list):
            component_set = []

        normalized_tags = _normalize_tags(detail.get("Tags"))
        normalized_items: list[BillingChargeItem] = []
        for component in component_set:
            if not isinstance(component, Mapping):
                continue

            charge_basis = self._detect_charge_basis(detail, component)
            if not charge_basis:
                continue

            config_pairs = _normalize_config_pairs(component.get("ComponentConfig"))
            bucket_aliases = self._extract_bucket_aliases(detail, config_pairs)
            amount_total = _decimal_from_value(
                component.get("RealCost")
                or component.get("Cost")
                or component.get("CashPayAmount")
            )
            usage_value = component.get("UsedAmount") or component.get("RealTotalMeasure")
            usage_unit = component.get("UsedAmountUnit")
            usage_bytes = _bytes_from_usage(usage_value, usage_unit)

            if amount_total == Decimal("0") and usage_bytes == 0:
                continue

            normalized_items.append(
                BillingChargeItem(
                    charge_basis=charge_basis,
                    amount_total=amount_total,
                    usage_bytes=usage_bytes,
                    currency="CNY",
                    resource_id=_stringify(detail.get("ResourceId")),
                    resource_name=_stringify(detail.get("ResourceName")),
                    bucket_name=bucket_aliases[0] if bucket_aliases else "",
                    account_identifier=_stringify(
                        detail.get("PayerUin")
                        or detail.get("OwnerUin")
                        or detail.get("OperateUin")
                    ),
                    tag_values=normalized_tags,
                    details_json={
                        "bill_day": bill_day,
                        "bill_id": _stringify(detail.get("BillId")),
                        "order_id": _stringify(detail.get("OrderId")),
                        "business_code": _stringify(detail.get("BusinessCode")),
                        "business_code_name": _stringify(detail.get("BusinessCodeName")),
                        "product_code": _stringify(detail.get("ProductCode")),
                        "product_code_name": _stringify(detail.get("ProductCodeName")),
                        "action_type": _stringify(detail.get("ActionTypeName") or detail.get("ActionType")),
                        "region_name": _stringify(detail.get("RegionName")),
                        "zone_name": _stringify(detail.get("ZoneName")),
                        "component_code": _stringify(component.get("ComponentCode")),
                        "component_code_name": _stringify(component.get("ComponentCodeName")),
                        "item_code": _stringify(component.get("ItemCode")),
                        "item_code_name": _stringify(component.get("ItemCodeName")),
                        "used_amount": _stringify(usage_value),
                        "used_amount_unit": _stringify(usage_unit),
                        "bucket_aliases": bucket_aliases,
                        "component_config": config_pairs,
                    },
                )
            )

        return normalized_items

    def _detect_charge_basis(
        self,
        detail: Mapping[str, Any],
        component: Mapping[str, Any],
    ) -> str:
        texts = [
            _stringify(detail.get("BusinessCodeName")).lower(),
            _stringify(detail.get("ProductCodeName")).lower(),
            _stringify(detail.get("ActionTypeName") or detail.get("ActionType")).lower(),
            _stringify(component.get("ComponentCodeName")).lower(),
            _stringify(component.get("ItemCodeName")).lower(),
            _stringify(component.get("ComponentCode")).lower(),
            _stringify(component.get("ItemCode")).lower(),
        ]
        joined = " ".join(item for item in texts if item)

        if any(keyword in joined for keyword in ("传输加速", "acceleration")):
            return "transfer_acceleration_egress"
        if any(keyword in joined for keyword in ("回源", "origin")):
            return "cdn_origin_egress"
        if any(keyword in joined for keyword in ("数据处理", "process")):
            return "data_processing"
        if any(
            keyword in joined
            for keyword in (
                "下行",
                "流出",
                "公网流量",
                "外网流量",
                "download",
                "egress",
                "traffic",
            )
        ):
            return StorageBillingChargeBasisEnum.EGRESS_TRAFFIC.value
        return ""

    def _extract_bucket_aliases(
        self,
        detail: Mapping[str, Any],
        config_pairs: Iterable[dict[str, str]],
    ) -> list[str]:
        aliases = [
            _stringify(detail.get("ResourceName")),
        ]

        for pair in config_pairs:
            name = _stringify(pair.get("name")).lower()
            value = _stringify(pair.get("value"))
            if not value:
                continue
            if any(keyword in name for keyword in ("bucket", "存储桶", "桶")):
                aliases.append(value)

        aliases.append(_stringify(detail.get("ResourceId")))

        result: list[str] = []
        seen: set[str] = set()
        for item in aliases:
            if not item or item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result
