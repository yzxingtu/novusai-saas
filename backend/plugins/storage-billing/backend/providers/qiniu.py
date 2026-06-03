"""Qiniu Kodo official billing adapter. / 七牛云 Kodo 官方账单适配器。"""

from __future__ import annotations

import base64
import hmac
from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha1
from typing import Any
from urllib.parse import urlencode

import httpx

from ..models import StorageBillingChargeBasisEnum, StorageBillingPeriodTypeEnum
from .base import BillingChargeItem, BillingFetchRequest, BillingFetchResult

_API_HOST = "https://api.qiniu.com"
_API_PATH = "/billing-api/v2/bill/detail"
_TIMEOUT = 60.0
_QINIU_MONEY_SCALE = Decimal("100000000")


def _stringify(value: Any) -> str:
    return str(value or "").strip()


def _decimal_from_money(value: Any) -> Decimal:
    text = _stringify(value)
    if not text:
        return Decimal("0")
    try:
        return Decimal(text) / _QINIU_MONEY_SCALE
    except (InvalidOperation, ValueError, ZeroDivisionError):
        return Decimal("0")


def _decimal_from_value(value: Any) -> Decimal:
    text = _stringify(value)
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _usage_bytes(value: Any, coefficient: Any, usage_unit: Any) -> int:
    raw_value = _decimal_from_value(value)
    raw_coefficient = _decimal_from_value(coefficient)
    normalized_unit = _stringify(usage_unit).lower()
    unit_map = {
        "byte": Decimal("1"),
        "bytes": Decimal("1"),
        "b": Decimal("1"),
        "kb": Decimal("1024"),
        "mb": Decimal("1048576"),
        "gb": Decimal("1073741824"),
        "tb": Decimal("1099511627776"),
    }
    unit_bytes = unit_map.get(normalized_unit)
    if raw_value == Decimal("0"):
        return 0
    if unit_bytes is None:
        try:
            return int(raw_value)
        except (InvalidOperation, OverflowError, ValueError):
            return 0
    if raw_coefficient <= 0:
        raw_coefficient = unit_bytes
    try:
        return int((raw_value / raw_coefficient) * unit_bytes)
    except (InvalidOperation, OverflowError, ValueError, ZeroDivisionError):
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


def _urlsafe_base64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _qiniu_management_token(
    *,
    access_key: str,
    secret_key: str,
    url: str,
) -> str:
    signature_data = url.split("://", 1)[-1]
    path_start = signature_data.find("/")
    signature_payload = signature_data[path_start:] if path_start >= 0 else "/"
    signature_payload = f"{signature_payload}\n".encode()
    digest = hmac.new(secret_key.encode("utf-8"), signature_payload, sha1).digest()
    return f"{access_key}:{_urlsafe_base64_encode(digest)}"


def _month_bounds(target_date: date) -> tuple[date, date]:
    period_start = target_date.replace(day=1)
    next_month = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    period_end = next_month - timedelta(days=1)
    return period_start, period_end


class QiniuKodoOfficialBillAdapter:
    provider_code = "qiniu-kodo"

    async def fetch_official_bill(
        self,
        request: BillingFetchRequest,
    ) -> BillingFetchResult:
        profile = dict(request.profile or {})
        bill_source = _stringify(profile.get("bill_source"))
        if bill_source != "finance_api":
            return BillingFetchResult(
                provider_code=self.provider_code,
                driver_code=request.driver_code,
                billing_date=request.billing_date,
                period_type=StorageBillingPeriodTypeEnum.MONTHLY.value,
                period_start=request.period_start or request.billing_date,
                period_end=request.period_end or request.billing_date,
                source_status="not_implemented",
                error_message=(
                    f"Qiniu official bill source '{bill_source or '-'}' is not implemented yet."
                ),
                raw_payload_json={
                    "provider": self.provider_code,
                    "bill_source": bill_source,
                    "state": "source_not_implemented",
                },
            )

        access_key = _stringify(profile.get("access_key"))
        secret_key = _stringify(profile.get("secret_key"))
        account_identifier = _stringify(profile.get("account_identifier"))
        missing = [
            field
            for field, value in (
                ("access_key", access_key),
                ("secret_key", secret_key),
                ("account_identifier", account_identifier),
            )
            if not value
        ]
        period_start, period_end = _month_bounds(
            request.period_start or request.billing_date
        )
        if missing:
            return BillingFetchResult(
                provider_code=self.provider_code,
                driver_code=request.driver_code,
                billing_date=period_start,
                period_type=StorageBillingPeriodTypeEnum.MONTHLY.value,
                period_start=period_start,
                period_end=period_end,
                source_status="failed",
                error_message=f"Missing Qiniu billing config fields: {', '.join(missing)}",
                raw_payload_json={
                    "provider": self.provider_code,
                    "bill_source": bill_source,
                    "missing_fields": missing,
                },
            )

        try:
            payload = await self._request_monthly_bill_detail(
                period_start=period_start,
                access_key=access_key,
                secret_key=secret_key,
            )
        except Exception as exc:
            return BillingFetchResult(
                provider_code=self.provider_code,
                driver_code=request.driver_code,
                billing_date=period_start,
                period_type=StorageBillingPeriodTypeEnum.MONTHLY.value,
                period_start=period_start,
                period_end=period_end,
                source_status="failed",
                error_message=str(exc),
                raw_payload_json={
                    "provider": self.provider_code,
                    "bill_source": bill_source,
                    "state": "api_failed",
                },
            )

        charge_items = self._normalize_items(
            payload=payload,
            account_identifier=account_identifier,
        )
        source_status = "fetched" if charge_items else "empty"
        data = payload.get("data")
        payload_currency = (
            _stringify(data.get("currency")) if isinstance(data, Mapping) else ""
        ) or "CNY"
        return BillingFetchResult(
            provider_code=self.provider_code,
            driver_code=request.driver_code,
            billing_date=period_start,
            period_type=StorageBillingPeriodTypeEnum.MONTHLY.value,
            period_start=period_start,
            period_end=period_end,
            source_status=source_status,
            source_ref=f"qiniu_bill_detail:{period_start.strftime('%Y-%m')}",
            currency=payload_currency,
            amount_total=sum(
                (item.amount_total for item in charge_items), Decimal("0")
            ),
            usage_bytes=sum(item.usage_bytes for item in charge_items),
            charge_items=charge_items,
            raw_payload_json={
                "provider": self.provider_code,
                "bill_source": bill_source,
                "period_month": period_start.strftime("%Y-%m"),
                "item_count": len(charge_items),
                "charge_items": [_serialize_charge_item(item) for item in charge_items],
                "raw_payload": payload,
            },
        )

    async def _request_monthly_bill_detail(
        self,
        *,
        period_start: date,
        access_key: str,
        secret_key: str,
    ) -> dict[str, Any]:
        next_month_start = (period_start.replace(day=28) + timedelta(days=4)).replace(
            day=1
        )
        params = {
            "start": period_start.isoformat(),
            "end": next_month_start.isoformat(),
        }
        query_string = urlencode(params)
        url = f"{_API_HOST}{_API_PATH}?{query_string}"
        authorization = f"Qiniu {_qiniu_management_token(access_key=access_key, secret_key=secret_key, url=url)}"
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, Mapping):
            raise RuntimeError("Qiniu finance API returned invalid payload.")
        if int(payload.get("code") or 0) != 0:
            message = (
                _stringify(payload.get("message"))
                or "Qiniu finance API request failed."
            )
            raise RuntimeError(message)
        return dict(payload)

    def _normalize_items(
        self,
        *,
        payload: Mapping[str, Any],
        account_identifier: str,
    ) -> list[BillingChargeItem]:
        data = payload.get("data")
        if not isinstance(data, Mapping):
            return []
        raw_items = data.get("list")
        if not isinstance(raw_items, list):
            return []

        currency = _stringify(data.get("currency")) or "CNY"
        result: list[BillingChargeItem] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, Mapping):
                continue
            charge_basis = self._detect_charge_basis(raw_item)
            if not charge_basis:
                continue
            amount_total = _decimal_from_money(
                raw_item.get("item_money") or raw_item.get("total_money")
            )
            usage_bytes = _usage_bytes(
                raw_item.get("total_usage"),
                raw_item.get("usage_coefficient"),
                raw_item.get("usage_unit"),
            )
            if amount_total == Decimal("0") and usage_bytes == 0:
                continue

            product_name = _stringify(raw_item.get("product"))
            item_name = _stringify(raw_item.get("item"))
            zone = _stringify(raw_item.get("zone"))
            result.append(
                BillingChargeItem(
                    charge_basis=charge_basis,
                    amount_total=amount_total,
                    usage_bytes=usage_bytes,
                    currency=currency,
                    resource_id=product_name or item_name,
                    resource_name=item_name or product_name,
                    account_identifier=account_identifier,
                    details_json={
                        "product": product_name,
                        "item": item_name,
                        "zone": zone,
                        "price": _stringify(raw_item.get("price")),
                        "price_unit": _stringify(raw_item.get("price_unit")),
                        "usage_unit": _stringify(raw_item.get("usage_unit")),
                        "usage_coefficient": _stringify(
                            raw_item.get("usage_coefficient")
                        ),
                        "usage_amount": _stringify(raw_item.get("usage_amount")),
                        "total_usage": _stringify(raw_item.get("total_usage")),
                        "item_money": _stringify(raw_item.get("item_money")),
                        "total_money": _stringify(raw_item.get("total_money")),
                    },
                )
            )
        return result

    def _detect_charge_basis(self, raw_item: Mapping[str, Any]) -> str | None:
        product_name = _stringify(raw_item.get("product"))
        item_name = _stringify(raw_item.get("item"))
        text = f"{product_name} {item_name}".lower()
        if "回源" in text:
            return StorageBillingChargeBasisEnum.CDN_ORIGIN_EGRESS.value
        if "加速" in text and "流" in text:
            return StorageBillingChargeBasisEnum.TRANSFER_ACCELERATION_EGRESS.value
        if "处理" in text:
            return StorageBillingChargeBasisEnum.DATA_PROCESSING.value
        if ("对象存储" in text or "kodo" in text or "流量" in text) and "流" in text:
            return StorageBillingChargeBasisEnum.EGRESS_TRAFFIC.value
        return None


__all__ = ["QiniuKodoOfficialBillAdapter"]
