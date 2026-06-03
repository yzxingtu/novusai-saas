from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.repository_parts.query import RepositoryQueryMixin
from app.repositories.common.notification_template_repository import (
    NotificationTemplateRepository,
)
from app.schemas.common.query import FilterOp, FilterRule, QuerySpec


@pytest.mark.asyncio
async def test_query_list_translates_is_override_filter(monkeypatch) -> None:
    captured: dict[str, list[FilterRule]] = {}

    async def fake_base_query_list(
        self,
        spec,
        scope=None,
        forced_filters=None,
        include_deleted=False,
    ):
        _ = (self, scope, forced_filters, include_deleted)
        captured["filters"] = spec.filters
        return [], 0

    monkeypatch.setattr(
        RepositoryQueryMixin,
        "query_list",
        fake_base_query_list,
    )

    repo = NotificationTemplateRepository(SimpleNamespace())
    await repo.query_list(
        QuerySpec(
            filters=[
                FilterRule(
                    field="is_override",
                    op=FilterOp.eq,
                    value="false",
                )
            ]
        )
    )

    assert captured["filters"] == [
        FilterRule(field="override_of", op=FilterOp.isnull, value=True)
    ]
