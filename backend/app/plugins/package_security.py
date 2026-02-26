"""插件 ZIP 包安全校验与解压工具。"""

from __future__ import annotations

import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

from app.core.config import settings
from app.plugins.exceptions import PluginInstallError, PluginManifestError

_WINDOWS_DRIVE_RE = re.compile(r"^[a-zA-Z]:")


def ensure_package_size_limit(size_bytes: int) -> None:
    """校验压缩包大小是否超限。"""
    limit = settings.PLUGIN_MAX_PACKAGE_SIZE
    if size_bytes > limit:
        raise PluginInstallError(
            message=(
                "Plugin package too large: "
                f"{size_bytes} bytes exceeds limit {limit} bytes"
            ),
        )


def validate_plugin_zip_archive(zip_path: Path) -> None:
    """对插件 ZIP 包做安全校验（不解压）。"""
    zip_size = zip_path.stat().st_size
    ensure_package_size_limit(zip_size)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            _validate_zip_entries(zf, zip_size)
    except zipfile.BadZipFile as exc:
        raise PluginInstallError(message=f"Invalid plugin archive: {exc}") from exc


def extract_plugin_zip_safely(zip_path: Path, extract_dir: Path) -> Path:
    """安全解压插件 ZIP，返回插件根目录。"""
    zip_size = zip_path.stat().st_size
    ensure_package_size_limit(zip_size)

    extract_root = extract_dir.resolve()
    extract_root.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            entries = _validate_zip_entries(zf, zip_size)

            total_written = 0
            for info, normalized in entries:
                target_path = (extract_root / Path(*normalized.parts)).resolve()
                if extract_root != target_path and extract_root not in target_path.parents:
                    raise PluginInstallError(
                        message=f"Illegal archive entry path: {info.filename}",
                    )

                if info.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                    continue

                target_path.parent.mkdir(parents=True, exist_ok=True)

                written = 0
                with zf.open(info, "r") as src, target_path.open("wb") as dst:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        written += len(chunk)
                        total_written += len(chunk)
                        if written > settings.PLUGIN_MAX_ARCHIVE_SINGLE_FILE_SIZE:
                            raise PluginInstallError(
                                message=(
                                    "Archive member exceeds per-file limit: "
                                    f"{info.filename}"
                                ),
                            )
                        if total_written > settings.PLUGIN_MAX_UNCOMPRESSED_SIZE:
                            raise PluginInstallError(
                                message=(
                                    "Archive exceeds uncompressed size limit: "
                                    f"{settings.PLUGIN_MAX_UNCOMPRESSED_SIZE} bytes"
                                ),
                            )
                        dst.write(chunk)
    except zipfile.BadZipFile as exc:
        raise PluginInstallError(message=f"Invalid plugin archive: {exc}") from exc

    plugin_dir = _locate_plugin_root(extract_root)
    if plugin_dir is None:
        raise PluginManifestError(message="No plugin.yaml found in plugin archive")
    return plugin_dir


def _validate_zip_entries(
    zf: zipfile.ZipFile,
    zip_size: int,
) -> list[tuple[zipfile.ZipInfo, PurePosixPath]]:
    """校验 ZIP 成员列表并返回规范化路径。"""
    infos = zf.infolist()
    if len(infos) > settings.PLUGIN_MAX_ARCHIVE_FILES:
        raise PluginInstallError(
            message=(
                "Archive contains too many members: "
                f"{len(infos)} > {settings.PLUGIN_MAX_ARCHIVE_FILES}"
            ),
        )

    total_uncompressed = 0
    entries: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []

    for info in infos:
        normalized = _normalize_member_path(info.filename)
        if normalized is None:
            raise PluginInstallError(
                message=f"Illegal archive member path: {info.filename}",
            )

        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            raise PluginInstallError(
                message=f"Symlink is not allowed in archive: {info.filename}",
            )

        if not info.is_dir():
            if info.file_size > settings.PLUGIN_MAX_ARCHIVE_SINGLE_FILE_SIZE:
                raise PluginInstallError(
                    message=(
                        "Archive member too large: "
                        f"{info.filename} ({info.file_size} bytes)"
                    ),
                )
            total_uncompressed += info.file_size

        entries.append((info, normalized))

    if total_uncompressed > settings.PLUGIN_MAX_UNCOMPRESSED_SIZE:
        raise PluginInstallError(
            message=(
                "Archive uncompressed size too large: "
                f"{total_uncompressed} > {settings.PLUGIN_MAX_UNCOMPRESSED_SIZE}"
            ),
        )

    if zip_size > 0 and total_uncompressed > 0:
        ratio = total_uncompressed / zip_size
        if ratio > settings.PLUGIN_MAX_COMPRESSION_RATIO:
            raise PluginInstallError(
                message=(
                    "Archive compression ratio too high: "
                    f"{ratio:.1f} > {settings.PLUGIN_MAX_COMPRESSION_RATIO}"
                ),
            )

    return entries


def _normalize_member_path(raw_name: str) -> PurePosixPath | None:
    """规范化成员路径，非法路径返回 None。"""
    name = (raw_name or "").replace("\\", "/").strip()
    if not name:
        return None
    if name.startswith("/") or _WINDOWS_DRIVE_RE.match(name):
        return None

    normalized = PurePosixPath(name)
    if normalized.is_absolute():
        return None

    for part in normalized.parts:
        if part in {"", ".", ".."}:
            return None

    return normalized


def _locate_plugin_root(extract_dir: Path) -> Path | None:
    """定位包含 plugin.yaml 的插件根目录。"""
    for child in extract_dir.iterdir():
        if child.is_dir() and (child / "plugin.yaml").is_file():
            return child
    if (extract_dir / "plugin.yaml").is_file():
        return extract_dir
    return None


__all__ = [
    "ensure_package_size_limit",
    "validate_plugin_zip_archive",
    "extract_plugin_zip_safely",
]
