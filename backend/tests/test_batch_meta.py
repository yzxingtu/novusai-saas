"""
批量元数据 v2 — 单元测试

覆盖：
- BatchMeta 基础操作（entity_files/shared_files/files_by_owner/summary）
- FileKind 推断
- 从 v1 entity_file_map 转换
- 从生成结果构建（含多 owner 和共享文件）
- 降级兼容
"""

import pytest

from app.codegen.batch_meta import (
    META_VERSION,
    BatchMeta,
    FileKind,
    FileMeta,
    FileRole,
    from_entity_file_map,
    from_generated_files,
    infer_file_kind,
)


# ============================================================
# FileKind 推断
# ============================================================


class TestInferFileKind:
    """文件类型推断"""

    def test_router(self):
        assert infer_file_kind("frontend/src/router/routes.ts") == FileKind.ROUTER

    def test_api(self):
        assert infer_file_kind("frontend/src/api/order.ts") == FileKind.API

    def test_i18n(self):
        assert infer_file_kind("frontend/src/locales/zh-CN/order.json") == FileKind.I18N

    def test_model(self):
        assert infer_file_kind("backend/app/models/order.py") == FileKind.MODEL

    def test_controller(self):
        assert infer_file_kind("backend/app/controllers/order_controller.py") == FileKind.CONTROLLER

    def test_view(self):
        assert infer_file_kind("frontend/src/views/order/index.vue") == FileKind.VIEW

    def test_form(self):
        assert infer_file_kind("frontend/src/views/order/form.vue") == FileKind.FORM

    def test_data(self):
        assert infer_file_kind("frontend/src/views/order/data.ts") == FileKind.DATA

    def test_unknown(self):
        assert infer_file_kind("README.md") == FileKind.OTHER

    def test_windows_path(self):
        assert infer_file_kind("frontend\\src\\router\\routes.ts") == FileKind.ROUTER


# ============================================================
# BatchMeta 基础操作
# ============================================================


class TestBatchMeta:
    """BatchMeta 基础"""

    def _make_meta(self) -> BatchMeta:
        return BatchMeta(
            project_name="test",
            generation_order=["order", "product"],
            files={
                "backend/app/models/order.py": FileMeta(
                    owners=["order"], role=FileRole.ENTITY, kind=FileKind.MODEL,
                ),
                "backend/app/models/product.py": FileMeta(
                    owners=["product"], role=FileRole.ENTITY, kind=FileKind.MODEL,
                ),
                "frontend/src/router/routes.ts": FileMeta(
                    owners=["order", "product"], role=FileRole.SHARED, kind=FileKind.ROUTER,
                ),
                "frontend/src/locales/zh-CN/order.json": FileMeta(
                    owners=["order"], role=FileRole.ENTITY, kind=FileKind.I18N,
                ),
            },
        )

    def test_entity_files(self):
        meta = self._make_meta()
        order_files = meta.entity_files("order")
        assert len(order_files) == 2  # model + i18n
        assert "backend/app/models/order.py" in order_files

    def test_shared_files(self):
        meta = self._make_meta()
        shared = meta.shared_files()
        assert len(shared) == 1
        assert "frontend/src/router/routes.ts" in shared

    def test_files_by_owner(self):
        meta = self._make_meta()
        groups = meta.files_by_owner()
        assert "order" in groups
        assert "product" in groups
        assert "__shared__" in groups
        assert len(groups["__shared__"]) == 1

    def test_summary(self):
        meta = self._make_meta()
        s = meta.summary()
        assert s["version"] == META_VERSION
        assert s["total_files"] == 4
        assert s["shared_files"] == 1
        assert s["multi_owner_files"] == 1
        assert "model" in s["kinds"]

    def test_version(self):
        meta = BatchMeta()
        assert meta.version == META_VERSION


# ============================================================
# 从 v1 entity_file_map 转换
# ============================================================


class TestFromEntityFileMap:
    """v1 → v2 转换"""

    def test_basic_conversion(self):
        v1 = {
            "backend/app/models/order.py": "order",
            "backend/app/models/product.py": "product",
        }
        meta = from_entity_file_map(v1, project_name="test")

        assert meta.project_name == "test"
        assert len(meta.files) == 2
        assert meta.files["backend/app/models/order.py"].owners == ["order"]
        assert meta.files["backend/app/models/order.py"].role == FileRole.ENTITY

    def test_shared_file_empty_module(self):
        """空 module → shared"""
        v1 = {"frontend/src/router/routes.ts": ""}
        meta = from_entity_file_map(v1)

        f = meta.files["frontend/src/router/routes.ts"]
        assert f.role == FileRole.SHARED
        assert f.owners == []

    def test_shared_file_explicit(self):
        """__shared__ → shared"""
        v1 = {"frontend/src/router/routes.ts": "__shared__"}
        meta = from_entity_file_map(v1)

        f = meta.files["frontend/src/router/routes.ts"]
        assert f.role == FileRole.SHARED

    def test_kind_inferred(self):
        """kind 自动推断"""
        v1 = {"backend/app/models/order.py": "order"}
        meta = from_entity_file_map(v1)
        assert meta.files["backend/app/models/order.py"].kind == FileKind.MODEL

    def test_generation_order_preserved(self):
        v1 = {"a.py": "a"}
        meta = from_entity_file_map(v1, generation_order=["a", "b"])
        assert meta.generation_order == ["a", "b"]


# ============================================================
# 从生成结果构建
# ============================================================


class TestFromGeneratedFiles:
    """从 generator 输出构建 meta v2"""

    def test_single_entity(self):
        entity_files = {
            "order": [
                {"path": "backend/app/models/order.py", "content": "..."},
                {"path": "frontend/src/views/order/index.vue", "content": "..."},
            ],
        }
        meta = from_generated_files(entity_files, project_name="test")
        assert len(meta.files) == 2
        assert meta.files["backend/app/models/order.py"].owners == ["order"]

    def test_multi_entity(self):
        entity_files = {
            "order": [{"path": "backend/app/models/order.py"}],
            "product": [{"path": "backend/app/models/product.py"}],
        }
        meta = from_generated_files(entity_files)
        assert len(meta.files) == 2

    def test_multi_owner_becomes_shared(self):
        """同一路径被多个实体生成 → 多 owner + shared"""
        entity_files = {
            "order": [{"path": "frontend/src/router/routes.ts"}],
            "product": [{"path": "frontend/src/router/routes.ts"}],
        }
        meta = from_generated_files(entity_files)

        f = meta.files["frontend/src/router/routes.ts"]
        assert set(f.owners) == {"order", "product"}
        assert f.role == FileRole.SHARED

    def test_explicit_shared_files(self):
        """显式 shared_files 列表"""
        entity_files = {
            "order": [{"path": "backend/app/models/order.py"}],
        }
        shared = [{"path": "frontend/src/router/routes.ts"}]

        meta = from_generated_files(entity_files, shared_files=shared)
        f = meta.files["frontend/src/router/routes.ts"]
        assert f.role == FileRole.SHARED
        assert f.owners == []

    def test_shared_overlap_with_entity(self):
        """shared_files 中的路径也被实体生成 → 标记为 shared"""
        entity_files = {
            "order": [{"path": "frontend/src/router/routes.ts"}],
        }
        shared = [{"path": "frontend/src/router/routes.ts"}]

        meta = from_generated_files(entity_files, shared_files=shared)
        f = meta.files["frontend/src/router/routes.ts"]
        assert f.role == FileRole.SHARED

    def test_empty_path_skipped(self):
        """空路径跳过"""
        entity_files = {"order": [{"path": ""}]}
        meta = from_generated_files(entity_files)
        assert len(meta.files) == 0
