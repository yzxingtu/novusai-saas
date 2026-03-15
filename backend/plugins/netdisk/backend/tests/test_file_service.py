"""FileService 单元测试 — pytest + unittest.mock，不依赖真实 DB/Storage/Redis / FileService unit tests — no real DB/Storage/Redis."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

TENANT_ID = 1


def _make_service(mock_db=None):
    """创建 FileService 实例（跳过 __init__） / Create FileService instance (skip __init__)."""
    from ..services.file_service import FileService
    svc = FileService.__new__(FileService)
    svc.db = mock_db or AsyncMock()
    svc.tenant_id = TENANT_ID
    return svc


def _make_node(
    id_=1,
    parent_id=None,
    name="test.pdf",
    node_type="file",
    size_bytes=1024,
    is_deleted=False,
    tenant_id=TENANT_ID,
):
    node = MagicMock()
    node.id         = id_
    node.parent_id  = parent_id
    node.name       = name
    node.node_type  = node_type
    node.size_bytes = size_bytes
    node.is_deleted = is_deleted
    node.is_file    = node_type == "file"
    node.is_folder  = node_type == "folder"
    node.tenant_id  = tenant_id
    node.storage_key = f"netdisk/{tenant_id}/{id_}/{name}"
    return node


# ─── 1. list_dir ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_dir_returns_nodes():
    mock_db  = AsyncMock()
    svc      = _make_service(mock_db)
    expected = [_make_node(), _make_node(id_=2, name="subfolder", node_type="folder")]

    with patch("plugins.netdisk.backend.services.file_service.NodeRepository") as MockRepo:
        MockRepo.return_value.list_dir = AsyncMock(return_value=expected)
        result = await svc.list_dir(parent_id=None)

    assert result == expected
    MockRepo.assert_called_once_with(mock_db, TENANT_ID)


# ─── 2. create_folder ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_folder_success():
    mock_db = AsyncMock()
    svc     = _make_service(mock_db)
    folder  = _make_node(node_type="folder", name="新建文件夹")

    with patch("plugins.netdisk.backend.services.file_service.NodeRepository") as MockRepo:
        MockRepo.return_value.name_exists = AsyncMock(return_value=False)
        with patch("plugins.netdisk.backend.services.file_service.FileNode") as MockNode:
            MockNode.return_value = folder
            mock_db.flush  = AsyncMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            result = await svc.create_folder(parent_id=None, name="新建文件夹")

    assert result == folder


@pytest.mark.asyncio
async def test_create_folder_name_conflict_raises():
    from app.exceptions import BusinessException
    mock_db = AsyncMock()
    svc     = _make_service(mock_db)

    with patch("plugins.netdisk.backend.services.file_service.NodeRepository") as MockRepo:
        MockRepo.return_value.name_exists = AsyncMock(return_value=True)
        MockRepo.return_value.get         = AsyncMock(return_value=_make_node(node_type="folder"))
        with pytest.raises(BusinessException):
            await svc.create_folder(parent_id=1, name="已存在")


# ─── 3. move — 防循环检测 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_move_to_child_raises():
    from app.exceptions import BusinessException
    mock_db = AsyncMock()
    svc     = _make_service(mock_db)
    node    = _make_node(id_=1, node_type="folder")

    with patch("plugins.netdisk.backend.services.file_service.NodeRepository") as MockRepo:
        # 目标节点的祖先包含 node.id（循环）
        ancestor = _make_node(id_=1)
        MockRepo.return_value.get          = AsyncMock(return_value=node)
        MockRepo.return_value.get_ancestors = AsyncMock(return_value=[ancestor])
        MockRepo.return_value.name_exists  = AsyncMock(return_value=False)

        with pytest.raises(BusinessException):
            await svc.move(node_id=1, new_parent_id=2)


@pytest.mark.asyncio
async def test_move_success():
    mock_db = AsyncMock()
    svc     = _make_service(mock_db)
    node    = _make_node(id_=1, node_type="folder")

    with patch("plugins.netdisk.backend.services.file_service.NodeRepository") as MockRepo:
        MockRepo.return_value.get          = AsyncMock(return_value=node)
        MockRepo.return_value.get_ancestors = AsyncMock(return_value=[])
        MockRepo.return_value.name_exists  = AsyncMock(return_value=False)
        mock_db.commit  = AsyncMock()
        mock_db.refresh = AsyncMock()

        await svc.move(node_id=1, new_parent_id=5)

    assert node.parent_id == 5


# ─── 4. delete (soft) ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_soft():
    mock_db = AsyncMock()
    svc     = _make_service(mock_db)
    node    = _make_node()
    node.soft_delete = MagicMock()

    with patch("plugins.netdisk.backend.services.file_service.NodeRepository") as MockRepo:
        MockRepo.return_value.get = AsyncMock(return_value=node)
        mock_db.commit = AsyncMock()

        await svc.delete(node_id=1, permanent=False)

    node.soft_delete.assert_called_once()


# ─── 5. search ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_returns_results():
    mock_db = AsyncMock()
    svc     = _make_service(mock_db)
    results = [_make_node(name="report.pdf")]

    with patch("plugins.netdisk.backend.services.file_service.NodeRepository") as MockRepo:
        MockRepo.return_value.search = AsyncMock(return_value=results)
        found = await svc.search(keyword="report")

    assert found == results


# ─── 6. rename conflict ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rename_conflict_raises():
    from app.exceptions import BusinessException
    mock_db = AsyncMock()
    svc     = _make_service(mock_db)
    node    = _make_node()

    with patch("plugins.netdisk.backend.services.file_service.NodeRepository") as MockRepo:
        MockRepo.return_value.get        = AsyncMock(return_value=node)
        MockRepo.return_value.name_exists = AsyncMock(return_value=True)

        with pytest.raises(BusinessException):
            await svc.rename(node_id=1, new_name="conflict.pdf")
