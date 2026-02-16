"""
插件打包与解压单元测试

覆盖：
- validate_manifest: 正常、缺字段、名称/版本格式错误
- validate_package: 正常包、非 zip、无 manifest、zip slip
- pack_plugin: 打包 → 内容完整
- extract_package: 正常解压、子目录格式解压
- scaffold_plugin: 生成脚手架
- generate_manifest: 生成 manifest 内容
"""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest

from app.plugins.packaging import (
    PackageError,
    extract_package,
    generate_manifest,
    pack_plugin,
    scaffold_plugin,
    validate_manifest,
    validate_package,
)


# ========================================
# validate_manifest
# ========================================

class TestValidateManifest:
    def test_valid_manifest(self) -> None:
        manifest = {
            "name": "my-plugin",
            "display_name": "My Plugin",
            "version": "1.0.0",
            "entry_point": "plugin.MyPlugin",
        }
        errors = validate_manifest(manifest)
        assert errors == []

    def test_missing_required_fields(self) -> None:
        errors = validate_manifest({})
        assert len(errors) == 4
        assert any("name" in e for e in errors)
        assert any("display_name" in e for e in errors)
        assert any("version" in e for e in errors)
        assert any("entry_point" in e for e in errors)

    def test_invalid_name_uppercase(self) -> None:
        manifest = {
            "name": "MyPlugin",
            "display_name": "My Plugin",
            "version": "1.0.0",
            "entry_point": "plugin.MyPlugin",
        }
        errors = validate_manifest(manifest)
        assert any("Invalid plugin name" in e for e in errors)

    def test_invalid_name_starts_with_number(self) -> None:
        manifest = {
            "name": "1plugin",
            "display_name": "Plugin",
            "version": "1.0.0",
            "entry_point": "plugin.P",
        }
        errors = validate_manifest(manifest)
        assert any("Invalid plugin name" in e for e in errors)

    def test_invalid_version(self) -> None:
        manifest = {
            "name": "my-plugin",
            "display_name": "My Plugin",
            "version": "not-semver",
            "entry_point": "plugin.MyPlugin",
        }
        errors = validate_manifest(manifest)
        assert any("Invalid version" in e for e in errors)

    def test_valid_prerelease_version(self) -> None:
        manifest = {
            "name": "my-plugin",
            "display_name": "My Plugin",
            "version": "1.0.0-beta.1",
            "entry_point": "plugin.MyPlugin",
        }
        errors = validate_manifest(manifest)
        assert errors == []

    def test_invalid_entry_point_no_dot(self) -> None:
        manifest = {
            "name": "my-plugin",
            "display_name": "My Plugin",
            "version": "1.0.0",
            "entry_point": "MyPlugin",
        }
        errors = validate_manifest(manifest)
        assert any("Invalid entry_point" in e for e in errors)

    def test_config_schema_must_be_dict(self) -> None:
        manifest = {
            "name": "my-plugin",
            "display_name": "My Plugin",
            "version": "1.0.0",
            "entry_point": "plugin.MyPlugin",
            "config_schema": "not-a-dict",
        }
        errors = validate_manifest(manifest)
        assert any("config_schema must be" in e for e in errors)

    def test_dependencies_must_be_dict(self) -> None:
        manifest = {
            "name": "my-plugin",
            "display_name": "My Plugin",
            "version": "1.0.0",
            "entry_point": "plugin.MyPlugin",
            "dependencies": ["dep1"],
        }
        errors = validate_manifest(manifest)
        assert any("dependencies must be" in e for e in errors)

    def test_conflicts_must_be_list(self) -> None:
        manifest = {
            "name": "my-plugin",
            "display_name": "My Plugin",
            "version": "1.0.0",
            "entry_point": "plugin.MyPlugin",
            "conflicts": {"a": "1"},
        }
        errors = validate_manifest(manifest)
        assert any("conflicts must be" in e for e in errors)

    def test_skill_requires_skill_type(self) -> None:
        manifest = {
            "name": "my-skill",
            "display_name": "My Skill",
            "version": "1.0.0",
            "entry_point": "plugin.MySkill",
            "provides": ["skill"],
        }
        errors = validate_manifest(manifest)
        assert any("skill_type is required" in e for e in errors)

    def test_skill_with_valid_skill_type(self) -> None:
        manifest = {
            "name": "my-skill",
            "display_name": "My Skill",
            "version": "1.0.0",
            "entry_point": "plugin.MySkill",
            "provides": ["skill"],
            "skill_type": "custom_skill",
        }
        errors = validate_manifest(manifest)
        assert errors == []


# ========================================
# validate_package
# ========================================

class TestValidatePackage:
    def test_file_not_found(self, tmp_path: Path) -> None:
        errors = validate_package(tmp_path / "nonexistent.nap")
        assert any("File not found" in e for e in errors)

    def test_not_a_zip(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.nap"
        bad_file.write_text("not a zip file")
        errors = validate_package(bad_file)
        assert any("not a valid zip" in e for e in errors)

    def test_no_manifest(self, tmp_path: Path) -> None:
        pkg = tmp_path / "no-manifest.nap"
        with zipfile.ZipFile(pkg, "w") as zf:
            zf.writestr("plugin.py", "# nothing")
        errors = validate_package(pkg)
        assert any("Missing manifest.json" in e for e in errors)

    def test_valid_package(self, tmp_path: Path) -> None:
        manifest = {
            "name": "test-pkg",
            "display_name": "Test Package",
            "version": "1.0.0",
            "entry_point": "plugin.TestPkg",
        }
        pkg = tmp_path / "test.nap"
        with zipfile.ZipFile(pkg, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("plugin.py", "# plugin code")
        errors = validate_package(pkg)
        assert errors == []

    def test_zip_slip_detection(self, tmp_path: Path) -> None:
        manifest = {
            "name": "evil-plugin",
            "display_name": "Evil",
            "version": "1.0.0",
            "entry_point": "plugin.Evil",
        }
        pkg = tmp_path / "evil.nap"
        with zipfile.ZipFile(pkg, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("../../../etc/passwd", "hacked")
        errors = validate_package(pkg)
        assert any("Suspicious path" in e for e in errors)

    def test_subdirectory_format(self, tmp_path: Path) -> None:
        """manifest.json 在子目录中也应能被发现"""
        manifest = {
            "name": "sub-plugin",
            "display_name": "Sub Plugin",
            "version": "1.0.0",
            "entry_point": "plugin.SubPlugin",
        }
        pkg = tmp_path / "sub.nap"
        with zipfile.ZipFile(pkg, "w") as zf:
            zf.writestr("sub-plugin/manifest.json", json.dumps(manifest))
            zf.writestr("sub-plugin/plugin.py", "# code")
        errors = validate_package(pkg)
        assert errors == []

    def test_wrong_extension(self, tmp_path: Path) -> None:
        pkg = tmp_path / "bad.tar.gz"
        pkg.write_bytes(b"not zip")
        errors = validate_package(pkg)
        assert any("extension" in e.lower() for e in errors)


# ========================================
# pack_plugin
# ========================================

class TestPackPlugin:
    def test_pack_creates_nap(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        manifest = {
            "name": "my-plugin",
            "display_name": "My Plugin",
            "version": "1.0.0",
            "entry_point": "plugin.MyPlugin",
        }
        (plugin_dir / "manifest.json").write_text(json.dumps(manifest))
        (plugin_dir / "plugin.py").write_text("# plugin code")

        result = pack_plugin(plugin_dir)
        assert result.exists()
        assert result.suffix == ".nap"
        assert result.name == "my-plugin-1.0.0.nap"

        # 验证包内容
        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
            assert "manifest.json" in names
            assert "plugin.py" in names

    def test_pack_skips_pycache(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        manifest = {
            "name": "my-plugin",
            "display_name": "My Plugin",
            "version": "1.0.0",
            "entry_point": "plugin.MyPlugin",
        }
        (plugin_dir / "manifest.json").write_text(json.dumps(manifest))
        (plugin_dir / "plugin.py").write_text("# code")
        pycache = plugin_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "plugin.cpython-312.pyc").write_bytes(b"bytecode")

        result = pack_plugin(plugin_dir)
        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
            assert not any("__pycache__" in n for n in names)
            assert not any(".pyc" in n for n in names)

    def test_pack_missing_manifest_raises(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "no-manifest"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.py").write_text("# code")

        with pytest.raises(PackageError, match="Missing manifest.json"):
            pack_plugin(plugin_dir)

    def test_pack_invalid_manifest_raises(self, tmp_path: Path) -> None:
        plugin_dir = tmp_path / "bad-manifest"
        plugin_dir.mkdir()
        (plugin_dir / "manifest.json").write_text(json.dumps({"name": ""}))
        (plugin_dir / "plugin.py").write_text("# code")

        with pytest.raises(PackageError, match="Manifest validation failed"):
            pack_plugin(plugin_dir)

    def test_pack_source_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(PackageError, match="Source directory not found"):
            pack_plugin(tmp_path / "nonexistent")


# ========================================
# extract_package
# ========================================

class TestExtractPackage:
    def test_extract_root_format(self, tmp_path: Path) -> None:
        """manifest.json 在 zip 根目录"""
        manifest = {
            "name": "root-plugin",
            "display_name": "Root Plugin",
            "version": "2.0.0",
            "entry_point": "plugin.RootPlugin",
        }
        pkg = tmp_path / "root.nap"
        with zipfile.ZipFile(pkg, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("plugin.py", "# root code")
            zf.writestr("src/helper.py", "# helper")

        target = tmp_path / "extracted"
        result_manifest = extract_package(pkg, target)

        assert result_manifest["name"] == "root-plugin"
        assert (target / "manifest.json").exists()
        assert (target / "plugin.py").exists()
        assert (target / "src" / "helper.py").exists()

    def test_extract_subdirectory_format(self, tmp_path: Path) -> None:
        """manifest.json 在子目录中（如 GitHub zip 下载）"""
        manifest = {
            "name": "sub-plugin",
            "display_name": "Sub Plugin",
            "version": "1.0.0",
            "entry_point": "plugin.SubPlugin",
        }
        pkg = tmp_path / "sub.nap"
        with zipfile.ZipFile(pkg, "w") as zf:
            zf.writestr("sub-plugin/manifest.json", json.dumps(manifest))
            zf.writestr("sub-plugin/plugin.py", "# sub code")

        target = tmp_path / "extracted-sub"
        result_manifest = extract_package(pkg, target)

        assert result_manifest["name"] == "sub-plugin"
        assert (target / "manifest.json").exists()
        assert (target / "plugin.py").exists()

    def test_extract_zip_slip_blocked(self, tmp_path: Path) -> None:
        """zip slip 攻击应被阻止"""
        manifest = {
            "name": "evil-zip",
            "display_name": "Evil",
            "version": "1.0.0",
            "entry_point": "plugin.Evil",
        }
        pkg = tmp_path / "evil.nap"
        with zipfile.ZipFile(pkg, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("../../../etc/passwd", "hacked")

        target = tmp_path / "extracted-evil"
        with pytest.raises(PackageError):
            extract_package(pkg, target)

    def test_extract_invalid_package_raises(self, tmp_path: Path) -> None:
        pkg = tmp_path / "invalid.nap"
        pkg.write_text("not a zip")
        target = tmp_path / "extracted-invalid"

        with pytest.raises(PackageError):
            extract_package(pkg, target)


# ========================================
# pack + extract round-trip
# ========================================

class TestRoundTrip:
    def test_pack_then_extract(self, tmp_path: Path) -> None:
        """打包 → 解压 → 内容完整"""
        source = tmp_path / "source-plugin"
        source.mkdir()
        manifest = {
            "name": "roundtrip",
            "display_name": "Round Trip",
            "version": "3.0.0",
            "entry_point": "plugin.RoundTrip",
        }
        (source / "manifest.json").write_text(json.dumps(manifest, indent=2))
        (source / "plugin.py").write_text("class RoundTrip: pass\n")
        (source / "__init__.py").write_text('"""roundtrip"""\n')

        nap = pack_plugin(source)
        assert nap.exists()

        target = tmp_path / "extracted-roundtrip"
        result = extract_package(nap, target)

        assert result["name"] == "roundtrip"
        assert result["version"] == "3.0.0"
        assert (target / "manifest.json").exists()
        assert (target / "plugin.py").exists()
        assert (target / "__init__.py").exists()

        # 内容一致
        assert (target / "plugin.py").read_text() == "class RoundTrip: pass\n"


# ========================================
# generate_manifest
# ========================================

class TestGenerateManifest:
    def test_basic_manifest(self) -> None:
        m = generate_manifest("my-tool", "My Tool", version="1.2.3")
        assert m["name"] == "my-tool"
        assert m["display_name"] == "My Tool"
        assert m["version"] == "1.2.3"
        assert m["entry_point"] == "plugin.MyToolPlugin"

    def test_skill_manifest(self) -> None:
        m = generate_manifest(
            "slack-notify",
            "Slack Notify",
            plugin_type="skill",
            skill_type="slack",
        )
        assert m["provides"] == ["skill"]
        assert m["skill_type"] == "slack"

    def test_custom_entry_point(self) -> None:
        m = generate_manifest(
            "custom",
            "Custom",
            entry_point="my.module.CustomPlugin",
        )
        assert m["entry_point"] == "my.module.CustomPlugin"


# ========================================
# scaffold_plugin
# ========================================

class TestScaffoldPlugin:
    def test_scaffold_creates_files(self, tmp_path: Path) -> None:
        plugin_dir = scaffold_plugin(tmp_path, "test-scaffold")
        assert plugin_dir.is_dir()
        assert (plugin_dir / "manifest.json").exists()
        assert (plugin_dir / "plugin.py").exists()
        assert (plugin_dir / "__init__.py").exists()
        assert (plugin_dir / "README.md").exists()
        assert (plugin_dir / "CHANGELOG.md").exists()

        # manifest is valid
        with open(plugin_dir / "manifest.json") as f:
            m = json.load(f)
        errors = validate_manifest(m)
        assert errors == []

    def test_scaffold_skill_type(self, tmp_path: Path) -> None:
        plugin_dir = scaffold_plugin(tmp_path, "test-skill", plugin_type="skill")
        plugin_py = (plugin_dir / "plugin.py").read_text()
        assert "get_skill_type" in plugin_py
        assert "get_skill_config_schema" in plugin_py
