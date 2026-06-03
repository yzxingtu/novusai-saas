"""Base contracts for official billing adapters. / 官方账单适配器基础契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Protocol


@dataclass(slots=True)
class BillingFetchRequest:
    billing_date: date
    driver_code: str
    period_type: str = "daily"
    period_start: date | None = None
    period_end: date | None = None
    profile: dict[str, Any] = field(default_factory=dict)
    request_scope: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BillingChargeItem:
    charge_basis: str
    amount_total: Decimal
    usage_bytes: int = 0
    currency: str = "CNY"
    resource_id: str = ""
    resource_name: str = ""
    bucket_name: str = ""
    domain_name: str = ""
    account_identifier: str = ""
    tag_values: dict[str, str] = field(default_factory=dict)
    details_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BillingFetchResult:
    provider_code: str
    driver_code: str
    billing_date: date
    source_status: str
    period_type: str = "daily"
    period_start: date | None = None
    period_end: date | None = None
    source_ref: str = ""
    currency: str = "CNY"
    amount_total: Decimal = Decimal("0")
    usage_bytes: int = 0
    charge_items: list[BillingChargeItem] = field(default_factory=list)
    raw_payload_json: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


class OfficialBillAdapter(Protocol):
    provider_code: str

    async def fetch_official_bill(
        self,
        request: BillingFetchRequest,
    ) -> BillingFetchResult:
        """Fetch official provider bill snapshot.
        / 拉取官方账单快照。
        """
