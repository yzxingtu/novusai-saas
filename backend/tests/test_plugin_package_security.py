"""插件 ZIP 包安全校验回归测试。 / Plugin."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest


def _get_install_error():
    """延迟导入避免循环依赖。 / 。"""
    from app.plugins.package_security import PluginInstallError  # re-exported
    return PluginInstallError


def _import_funcs():
    from app.plugins.package_security import (
        extract_plugin_zip_safely,
        validate_plugin_zip_archive,
    )
    return extract_plugin_zip_safely, validate_plugin_zip_archive

_MINIMAL_PLUGIN_YAML = (
    "name: demo-plugin\n"
    "version: \"1.0.0\"\n"
    "display_name:\n"
    "  en: Demo Plugin\n"
    "scope: all_tenants"
).encode("utf-8")


def _build_zip(zip_path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for member_name, content in members.items():
            zf.writestr(member_name, content)


def test_validate_zip_rejects_path_traversal_member(tmp_path: Path) -> None:
    _, validate_plugin_zip_archive = _import_funcs()
    zip_path = tmp_path / "traversal.zip"
    _build_zip(
        zip_path,
        {
            "../escape.txt": b"boom",
            "demo-plugin/plugin.yaml": _MINIMAL_PLUGIN_YAML,
        },
    )

    with pytest.raises(_get_install_error(), match="Illegal archive member path"):
        validate_plugin_zip_archive(zip_path)


def test_validate_zip_rejects_compression_ratio_bomb(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, validate_plugin_zip_archive = _import_funcs()
    monkeypatch.setattr(
        "app.plugins.package_security.settings.PLUGIN_MAX_COMPRESSION_RATIO",
        1.0,
        raising=False,
    )

    zip_path = tmp_path / "ratio.zip"
    _build_zip(
        zip_path,
        {
            "demo-plugin/plugin.yaml": _MINIMAL_PLUGIN_YAML,
            "demo-plugin/blob.txt": b"a" * (128 * 1024),
        },
    )

    with pytest.raises(_get_install_error(), match="compression ratio too high"):
        validate_plugin_zip_archive(zip_path)


def test_validate_zip_rejects_uncompressed_size_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, validate_plugin_zip_archive = _import_funcs()
    monkeypatch.setattr(
        "app.plugins.package_security.settings.PLUGIN_MAX_UNCOMPRESSED_SIZE",
        64,
        raising=False,
    )

    zip_path = tmp_path / "uncompressed.zip"
    _build_zip(
        zip_path,
        {
            "demo-plugin/plugin.yaml": _MINIMAL_PLUGIN_YAML,
            "demo-plugin/data.bin": b"x" * 128,
        },
    )

    with pytest.raises(_get_install_error(), match="uncompressed size too large"):
        validate_plugin_zip_archive(zip_path)


def test_validate_zip_rejects_member_count_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, validate_plugin_zip_archive = _import_funcs()
    monkeypatch.setattr(
        "app.plugins.package_security.settings.PLUGIN_MAX_ARCHIVE_FILES",
        2,
        raising=False,
    )

    zip_path = tmp_path / "many-files.zip"
    _build_zip(
        zip_path,
        {
            "demo-plugin/plugin.yaml": _MINIMAL_PLUGIN_YAML,
            "demo-plugin/a.txt": b"a",
            "demo-plugin/b.txt": b"b",
        },
    )

    with pytest.raises(_get_install_error(), match="too many members"):
        validate_plugin_zip_archive(zip_path)


def test_extract_zip_rejects_single_file_size_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extract_plugin_zip_safely, _ = _import_funcs()
    monkeypatch.setattr(
        "app.plugins.package_security.settings.PLUGIN_MAX_ARCHIVE_SINGLE_FILE_SIZE",
        32,
        raising=False,
    )

    zip_path = tmp_path / "single-file-limit.zip"
    _build_zip(
        zip_path,
        {
            "demo-plugin/plugin.yaml": _MINIMAL_PLUGIN_YAML,
            "demo-plugin/large.bin": b"z" * 64,
        },
    )

    with pytest.raises(_get_install_error(), match="Archive member too large"):
        extract_plugin_zip_safely(zip_path, tmp_path / "extracted")


def test_extract_zip_returns_plugin_root_for_valid_archive(tmp_path: Path) -> None:
    extract_plugin_zip_safely, _ = _import_funcs()
    zip_path = tmp_path / "valid.zip"
    _build_zip(
        zip_path,
        {
            "demo-plugin/plugin.yaml": _MINIMAL_PLUGIN_YAML,
            "demo-plugin/backend/main.py": b"# plugin backend\n",
        },
    )

    plugin_dir = extract_plugin_zip_safely(zip_path, tmp_path / "extracted")

    assert plugin_dir.name == "demo-plugin"
    assert (plugin_dir / "plugin.yaml").is_file()
