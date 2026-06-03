from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import app.core.base_service as base_service_module
from app.core.base_service import BaseService
from app.core.dependency_checker import DependencyCheckResult, DependencyInfo
from app.exceptions import DependencyBlockedException


class _DummyModel:
    __delete_deps__ = [object()]

    def __init__(self, id: int):
        self.id = id
        self.deleted_with: str | None = None

    def soft_delete(self, level: str) -> None:
        self.deleted_with = level


class _DummyService(BaseService[_DummyModel, AsyncMock]):
    model = _DummyModel
    repository_class = AsyncMock


@pytest.mark.asyncio
async def test_delete_soft_propagates_dependency_block_exception(
    mock_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _DummyService.__new__(_DummyService)
    service.db = mock_db
    service.repo = AsyncMock()
    service._before_delete = AsyncMock()
    service._after_delete = AsyncMock()

    instance = _DummyModel(7)
    service.repo.get_by_id = AsyncMock(return_value=instance)

    blocked_result = DependencyCheckResult(
        blocked=True,
        blockers=[
            DependencyInfo(
                model_name="deletion.model.agent",
                count=2,
                items=[{"id": 3, "label": "child-agent"}],
                strategy="block",
            )
        ],
    )
    monkeypatch.setattr(
        base_service_module,
        "check_deletion_deps",
        AsyncMock(return_value=blocked_result),
    )

    with pytest.raises(DependencyBlockedException) as exc_info:
        await service.delete(7, soft=True)

    error = exc_info.value
    assert error.code == 4221
    assert error.dependencies == [
        {
            "type": "deletion.model.agent",
            "count": 2,
            "items": [{"id": 3, "label": "child-agent"}],
        }
    ]
    assert error.to_dict()["dependencies"] == error.dependencies
    assert instance.deleted_with is None
    mock_db.flush.assert_not_called()
    service._after_delete.assert_not_called()
