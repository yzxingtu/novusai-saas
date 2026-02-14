"""
BatchCrudProject 快照导入/导出 — 单元测试

覆盖：
- 导出格式正确（version/schema/metadata）
- 导入有效快照
- 导入无效 JSON
- 导入版本不兼容
- 导入缺少 project
- 导入 schema guard 失败
- export→import→export 幂等回环
- schema_version 不匹配 warning
"""

import json

import pytest

from app.codegen.snapshot import (
    COMPATIBLE_SNAPSHOT_VERSIONS,
    SCHEMA_VERSION,
    SNAPSHOT_VERSION,
    export_snapshot,
    export_snapshot_dict,
    import_snapshot,
)


def _entity(module: str = "order") -> dict:
    return {
        "module": module,
        "table_name": f"{module}s",
        "display_name": module.title(),
        "display_name_en": module.title(),
        "parent_menu": "test",
        "fields": [
            {
                "name": "title",
                "type": "string",
                "label": "Title",
                "label_zh": "标题",
                "label_en": "Title",
            },
        ],
    }


def _valid_project() -> dict:
    return {
        "project_name": "test_project",
        "entities": [_entity("order"), _entity("product")],
    }


class TestExport:
    """快照导出"""

    def test_export_json_string(self):
        """导出为 JSON 字符串"""
        result = export_snapshot(_valid_project(), description="Test snapshot")
        data = json.loads(result)

        assert data["snapshot_version"] == SNAPSHOT_VERSION
        assert data["schema_version"] == SCHEMA_VERSION
        assert "created_at" in data
        assert data["project"]["project_name"] == "test_project"
        assert data["metadata"]["description"] == "Test snapshot"
        assert data["metadata"]["entity_count"] == 2

    def test_export_dict(self):
        """导出为 dict"""
        result = export_snapshot_dict(_valid_project(), created_by="admin")
        assert result["snapshot_version"] == SNAPSHOT_VERSION
        assert result["metadata"]["created_by"] == "admin"

    def test_export_preserves_all_entities(self):
        """导出保留所有实体"""
        project = _valid_project()
        result = export_snapshot_dict(project)
        assert len(result["project"]["entities"]) == 2


class TestImport:
    """快照导入"""

    def test_import_valid_snapshot(self):
        """导入有效快照"""
        json_str = export_snapshot(_valid_project())
        result = import_snapshot(json_str)

        assert result.success is True
        assert result.project["project_name"] == "test_project"
        assert len(result.errors) == 0
        assert result.snapshot_version == SNAPSHOT_VERSION

    def test_import_from_dict(self):
        """从 dict 导入"""
        snapshot = export_snapshot_dict(_valid_project())
        result = import_snapshot(snapshot)
        assert result.success is True

    def test_import_invalid_json(self):
        """无效 JSON"""
        result = import_snapshot("{invalid json")
        assert result.success is False
        assert result.errors[0].code == "INVALID_JSON"

    def test_import_non_object(self):
        """非对象 JSON"""
        result = import_snapshot("[1,2,3]")
        assert result.success is False
        assert result.errors[0].code == "INVALID_FORMAT"

    def test_import_missing_version(self):
        """缺少版本号"""
        result = import_snapshot({"project": _valid_project()})
        assert result.success is False
        assert result.errors[0].code == "MISSING_VERSION"

    def test_import_incompatible_version(self):
        """不兼容版本"""
        result = import_snapshot({
            "snapshot_version": "99.0.0",
            "project": _valid_project(),
        })
        assert result.success is False
        assert result.errors[0].code == "INCOMPATIBLE_VERSION"

    def test_import_missing_project(self):
        """缺少 project 字段"""
        result = import_snapshot({
            "snapshot_version": SNAPSHOT_VERSION,
        })
        assert result.success is False
        assert result.errors[0].code == "MISSING_PROJECT"

    def test_import_invalid_project(self):
        """project 校验失败"""
        result = import_snapshot({
            "snapshot_version": SNAPSHOT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "project": {"fake_field": True},
        })
        assert result.success is False
        assert len(result.errors) > 0

    def test_import_schema_version_mismatch_warning(self):
        """schema_version 不匹配时产生 warning"""
        snapshot = export_snapshot_dict(_valid_project())
        snapshot["schema_version"] = "1.0.0"  # 旧版本
        result = import_snapshot(snapshot)
        assert result.success is True
        assert len(result.warnings) > 0
        assert "mismatch" in result.warnings[0].lower()


class TestRoundTrip:
    """导出→导入→导出 幂等回环"""

    def test_roundtrip_stable(self):
        """export→import→export 结果一致"""
        project = _valid_project()

        # 第一次导出
        json1 = export_snapshot(project, description="round 1")
        data1 = json.loads(json1)

        # 导入
        import_result = import_snapshot(json1)
        assert import_result.success is True

        # 第二次导出（使用导入的 project）
        json2 = export_snapshot(import_result.project, description="round 2")
        data2 = json.loads(json2)

        # project 内容一致
        assert data1["project"] == data2["project"]

    def test_roundtrip_multi_entity(self):
        """多实体回环"""
        project = {
            "project_name": "multi",
            "entities": [_entity("a"), _entity("b"), _entity("c")],
            "cross_relations": [
                {"source_entity": "b", "target_entity": "a", "relation_type": "belongs_to"},
            ],
        }

        json_str = export_snapshot(project)
        result = import_snapshot(json_str)
        assert result.success is True
        assert len(result.project["entities"]) == 3
        assert len(result.project["cross_relations"]) == 1
