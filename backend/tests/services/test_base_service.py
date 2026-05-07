"""BaseService delete semantics tests / BaseService 删除语义测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.base_service import BaseService


class _DummyService(BaseService[MagicMock, AsyncMock]):
    model = MagicMock()
    repository_class = AsyncMock


class TestBaseServiceDelete:
    @pytest.mark.asyncio
    async def test_delete_soft_missing_raises_not_found(self, mock_db):
        from app.exceptions import NotFoundException

        service = _DummyService.__new__(_DummyService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)
        service._before_delete = AsyncMock()
        service._after_delete = AsyncMock()

        with pytest.raises(NotFoundException):
            await service.delete(999, soft=True)

        service._after_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_hard_missing_raises_not_found(self, mock_db):
        from app.exceptions import NotFoundException

        service = _DummyService.__new__(_DummyService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.delete = AsyncMock(return_value=False)
        service._before_delete = AsyncMock()
        service._after_delete = AsyncMock()

        with pytest.raises(NotFoundException):
            await service.delete(999, soft=False)

        service.repo.delete.assert_awaited_once_with(999, soft=False)
        service._after_delete.assert_not_called()
