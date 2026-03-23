from __future__ import annotations

from datetime import date
from decimal import Decimal
import importlib
import json

import pytest


class _FakeAliyunClient:
    def __init__(self, calls: list[dict[str, object]], payload: dict):
        self._calls = calls
        self._payload = payload

    def do_action_with_exception(self, request):
        self._calls.append(dict(request.get_query_params()))
        return json.dumps(self._payload).encode("utf-8")


class _FakeHttpxResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeHttpxClient:
    def __init__(self, payload: dict):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, *args, **kwargs):
        return _FakeHttpxResponse(self._payload)


@pytest.mark.asyncio
async def test_qiniu_adapter_normalizes_monthly_finance_bill(monkeypatch) -> None:
    module = importlib.import_module("plugins.storage-billing.backend.providers.qiniu")

    payload = {
        "code": 0,
        "message": "",
        "data": {
            "currency": "CNY",
            "list": [
                {
                    "product": "对象存储 Kodo",
                    "item": "下行流量",
                    "zone": "z0",
                    "total_usage": "2147483648",
                    "usage_coefficient": "1073741824",
                    "usage_unit": "GB",
                    "item_money": "125000000",
                    "total_money": "125000000",
                }
            ],
        },
    }
    monkeypatch.setattr(
        module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeHttpxClient(payload),
    )

    adapter = module.QiniuKodoOfficialBillAdapter()
    result = await adapter.fetch_official_bill(
        module.BillingFetchRequest(
            billing_date=date(2026, 3, 21),
            driver_code="qiniu-kodo",
            period_type="monthly",
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            profile={
                "bill_source": "finance_api",
                "access_key": "ak",
                "secret_key": "sk",
                "account_identifier": "qiniu-main-account",
            },
        )
    )

    assert result.provider_code == "qiniu-kodo"
    assert result.driver_code == "qiniu-kodo"
    assert result.source_status == "fetched"
    assert result.period_type == "monthly"
    assert result.period_start == date(2026, 3, 1)
    assert result.period_end == date(2026, 3, 31)
    assert result.amount_total == Decimal("1.25")
    assert result.charge_items[0].usage_bytes == 2147483648
    assert result.charge_items[0].account_identifier == "qiniu-main-account"


@pytest.mark.asyncio
async def test_aliyun_adapter_reports_not_implemented_for_unsupported_bill_source() -> None:
    module = importlib.import_module("plugins.storage-billing.backend.providers.aliyun")

    adapter = module.AliyunOssOfficialBillAdapter()
    result = await adapter.fetch_official_bill(
        module.BillingFetchRequest(
            billing_date=date(2026, 3, 21),
            driver_code="aliyun-oss",
            profile={"bill_source": "oss_subscription", "access_key_id": "id", "access_key_secret": "secret"},
        )
    )

    assert result.provider_code == "aliyun-oss"
    assert result.driver_code == "aliyun-oss"
    assert result.source_status == "not_implemented"
    assert "not implemented" in (result.error_message or "").lower()
    assert result.raw_payload_json.get("state") == "source_not_implemented"


@pytest.mark.asyncio
async def test_aliyun_adapter_normalizes_bss_openapi_split_items(monkeypatch) -> None:
    module = importlib.import_module("plugins.storage-billing.backend.providers.aliyun")

    calls: list[dict[str, object]] = []
    payload = {
        "Code": "Success",
        "Message": "Successful!",
        "Success": True,
        "Data": {
            "NextToken": "",
            "TotalCount": 1,
            "Items": {
                "Item": [
                    {
                        "ProductCode": "oss",
                        "ProductName": "对象存储 OSS",
                        "ProductDetail": "对象存储",
                        "SplitProductDetail": "对象存储 Bucket",
                        "SplitItemID": "bucket-123",
                        "SplitItemName": "tenant-a-bucket",
                        "ItemName": "tenant-a-bucket",
                        "BillingItem": "公网下行流量",
                        "BillingItemCode": "InternetOut",
                        "PretaxAmount": "0.880000",
                        "Usage": "2",
                        "UsageUnit": "GB",
                        "Currency": "CNY",
                        "BillAccountID": "20001",
                        "BillingDate": "2026-03-21",
                        "SplitBillingDate": "2026-03-21",
                        "Tag": "key:tenant value:alpha; key:env value:prod",
                    }
                ]
            },
        },
    }

    monkeypatch.setattr(
        module,
        "AcsClient",
        lambda *args, **kwargs: _FakeAliyunClient(calls, payload),
    )

    adapter = module.AliyunOssOfficialBillAdapter()
    result = await adapter.fetch_official_bill(
        module.BillingFetchRequest(
            billing_date=date(2026, 3, 21),
            driver_code="aliyun-oss",
            profile={
                "bill_source": "bss_openapi",
                "access_key_id": "akid",
                "access_key_secret": "aksecret",
                "region": "cn-hangzhou",
                "account_identifier": "20001",
            },
        )
    )

    assert result.source_status == "fetched"
    assert len(result.charge_items) == 1
    assert result.charge_items[0].bucket_name == "tenant-a-bucket"
    assert result.charge_items[0].amount_total == Decimal("0.880000")
    assert result.charge_items[0].tag_values == {"tenant": "alpha", "env": "prod"}
    assert calls[0]["BillingDate"] == "2026-03-21"
    assert calls[0]["Granularity"] == "DAILY"
    assert calls[0]["ProductCode"] == "oss"
