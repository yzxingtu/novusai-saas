"""Table policy sync service tests / AI 表策略同步服务测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_mapper(cls):
    return SimpleNamespace(class_=cls)


def _make_policy(
    *,
    table_name: str,
    max_rows: int = 200,
    allow_create: bool = False,
    allow_update: bool = False,
    allow_delete: bool = False,
    column_descriptions: dict[str, str] | None = None,
    is_active: bool = True,
    sort_order: int = 0,
):
    from app.models.ai.table_policy import AITablePolicy

    now = datetime.now(timezone.utc)
    return AITablePolicy(
        table_name=table_name,
        label=table_name.title(),
        description="desc",
        keywords=["demo"],
        column_descriptions=column_descriptions or {},
        allow_read=True,
        allow_create=allow_create,
        allow_update=allow_update,
        allow_delete=allow_delete,
        max_rows=max_rows,
        blocked_columns=[],
        readonly_columns=[],
        permission_code="article:read",
        sort_order=sort_order,
        is_active=is_active,
        is_deleted=False,
        created_at=now,
        updated_at=now,
    )


class TestGetDeclaredTableNames:

    def test_get_declared_table_names_returns_only_declared_non_abstract_models(self):
        from app.services.ai import table_policy_sync_service as module

        class DeclaredModel:
            __tablename__ = "articles"
            __ai_policy__ = True

        class HiddenModel:
            __tablename__ = "hidden"

        class AbstractModel:
            __abstract__ = True
            __tablename__ = "abstracts"
            __ai_policy__ = True

        fake_base = SimpleNamespace(
            registry=SimpleNamespace(
                mappers=[
                    _make_mapper(DeclaredModel),
                    _make_mapper(HiddenModel),
                    _make_mapper(AbstractModel),
                ]
            )
        )

        with patch.object(module, "Base", fake_base):
            assert module.get_declared_table_names() == {"articles"}

    def test_get_declared_table_names_returns_empty_when_nothing_declared(self):
        from app.services.ai import table_policy_sync_service as module

        class PlainModel:
            __tablename__ = "plain"

        fake_base = SimpleNamespace(
            registry=SimpleNamespace(mappers=[_make_mapper(PlainModel)])
        )

        with patch.object(module, "Base", fake_base):
            assert module.get_declared_table_names() == set()


class TestSyncTablePolicies:

    @pytest.mark.asyncio
    async def test_sync_table_policies_rebuilds_and_restores_admin_custom_fields(
        self, mock_db
    ):
        from app.services.ai import table_policy_sync_service as module

        class ArticleModel:
            __tablename__ = "articles"
            __ai_policy__ = {"label": "Articles"}

        old_result = MagicMock()
        old_result.scalars.return_value.all.return_value = [
            _make_policy(
                table_name="articles",
                max_rows=300,
                allow_create=True,
                allow_update=True,
                column_descriptions={
                    "manual_col": "Manual description",
                    "status": "enum.article.status",
                },
                is_active=False,
                sort_order=9,
            )
        ]

        mock_db.execute = AsyncMock(side_effect=[old_result, MagicMock()])
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        added: list[object] = []
        mock_db.add.side_effect = added.append

        fake_base = SimpleNamespace(
            registry=SimpleNamespace(mappers=[_make_mapper(ArticleModel)])
        )

        with patch.object(module, "Base", fake_base), patch.object(
            module,
            "_build_default_policy_from_declaration",
            return_value={
                "table_name": "articles",
                "label": "Articles",
                "description": "default description",
                "keywords": ["articles"],
                "column_descriptions": {
                    "status": "Generated status",
                    "fresh_col": "Fresh description",
                },
                "allow_read": True,
                "allow_create": False,
                "allow_update": False,
                "allow_delete": False,
                "max_rows": 200,
                "blocked_columns": [],
                "readonly_columns": ["id"],
                "permission_code": "article:read",
                "sort_order": 0,
                "is_active": True,
                "is_deleted": False,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        ):
            result = await module.sync_table_policies(mock_db)

        assert result == {"synced": 1, "declared_tables": ["articles"]}
        assert len(added) == 1
        new_policy = added[0]
        assert new_policy.max_rows == 300
        assert new_policy.allow_create is True
        assert new_policy.allow_update is True
        assert new_policy.is_active is False
        assert new_policy.sort_order == 9
        assert new_policy.column_descriptions == {
            "manual_col": "Manual description",
            "status": "Generated status",
            "fresh_col": "Fresh description",
        }
        mock_db.flush.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_table_policies_returns_empty_when_no_model_declares_ai_policy(
        self, mock_db
    ):
        from app.services.ai import table_policy_sync_service as module

        class PlainModel:
            __tablename__ = "plain"

        old_result = MagicMock()
        old_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[old_result, MagicMock()])
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        fake_base = SimpleNamespace(
            registry=SimpleNamespace(mappers=[_make_mapper(PlainModel)])
        )

        with patch.object(module, "Base", fake_base):
            result = await module.sync_table_policies(mock_db)

        assert result == {"synced": 0, "declared_tables": []}
        mock_db.add.assert_not_called()
        mock_db.commit.assert_awaited_once()
