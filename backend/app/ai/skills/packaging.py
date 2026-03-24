"""
Skill Package Packaging and Import Utilities
技能包打包与导入工具

Defines Skill ZIP package format, provides SKILL.md frontmatter parsing,
validation, and extraction functionality.
定义 Skill ZIP 包格式，提供解析 SKILL.md 前置元数据、校验、解压功能。

Skill ZIP package structure / Skill ZIP 包结构：
├── SKILL.md           — Skill metadata (YAML frontmatter) + docs (required) / 元数据与文档（必填）
├── README.md          — User documentation (optional) / 用户文档（可选）
├── .clawignore        — Ignore rules (optional) / 忽略规则（可选）
├── server/            — Skill server code (required) / 服务代码（必填）
│   ├── pyproject.toml — Python project config / 项目配置
│   └── {package}/     — Python package directory / 包目录
│       ├── __init__.py
│       ├── main.py    — FastAPI entry point / 入口
│       └── ...
└── references/        — Reference docs (optional) / 参考文档（可选）
    └── *.md
"""

from __future__ import annotations

import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from app.core.logging import LogManager

logger = LogManager.get_logger("app")

# SKILL.md YAML frontmatter required fields / 必需字段
SKILL_REQUIRED_FIELDS = {"name", "description", "version"}

# Allowed skill package extensions / 允许上传的技能包扩展名
ALLOWED_SKILL_EXTENSIONS = {".zip"}

# ZIP upload security limits / ZIP 上传安全限制
MAX_ZIP_FILE_SIZE = int(os.environ.get("SKILL_MAX_ZIP_SIZE_MB", "50")) * 1024 * 1024
MAX_ZIP_UNCOMPRESSED_SIZE = int(os.environ.get("SKILL_MAX_UNCOMPRESSED_SIZE_MB", "200")) * 1024 * 1024
MAX_ZIP_FILE_COUNT = int(os.environ.get("SKILL_MAX_FILE_COUNT", "500"))
MAX_ZIP_RATIO = float(os.environ.get("SKILL_MAX_COMPRESSION_RATIO", "100"))

# Semantic version regex / 语义化版本正则
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

# Skill package storage root directory (relative to backend/)
# 技能包存储根目录（相对于 backend/）
SKILLS_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "storage" / "skills"


class SkillPackageError(Exception):
    """Skill package packaging/validation error / 技能包打包/校验错误"""


def parse_skill_md(content: str) -> dict[str, Any]:
    """
    Parse YAML frontmatter from SKILL.md.
    解析 SKILL.md 的 YAML frontmatter。

    Args:
        content: Full text of SKILL.md / SKILL.md 文件全文

    Returns:
        Parsed metadata dictionary / 解析后的元数据字典

    Raises:
        SkillPackageError: Raised when format is incorrect / 格式不正确时抛出
    """
    content = content.strip()
    if not content.startswith("---"):
        raise SkillPackageError(
            "SKILL.md must start with YAML frontmatter delimited by '---'"
        )

    # Find the second --- / 找到第二个 ---
    end_idx = content.find("---", 3)
    if end_idx == -1:
        raise SkillPackageError(
            "SKILL.md frontmatter missing closing '---'"
        )

    yaml_block = content[3:end_idx].strip()

    try:
        import yaml
        metadata = yaml.safe_load(yaml_block)
    except Exception as exc:
        raise SkillPackageError(
            f"Failed to parse SKILL.md YAML frontmatter: {exc}"
        ) from exc

    if not isinstance(metadata, dict):
        raise SkillPackageError(
            "SKILL.md frontmatter must be a YAML mapping (key-value pairs)"
        )

    return metadata


def validate_skill_metadata(metadata: dict[str, Any]) -> list[str]:
    """
    Validate skill package metadata.
    校验技能包元数据。

    Args:
        metadata: Metadata dict parsed from SKILL.md / 从 SKILL.md 解析的元数据字典

    Returns:
        List of errors (empty list means passed) / 错误列表（空列表表示通过）
    """
    errors: list[str] = []

    for field in SKILL_REQUIRED_FIELDS:
        if field not in metadata or not metadata[field]:
            errors.append(f"Missing required field in SKILL.md: {field}")

    if errors:
        return errors

    version = metadata.get("version", "")
    if isinstance(version, (int, float)):
        version = str(version)
    if not SEMVER_RE.match(version):
        errors.append(
            f"Invalid version: '{version}'. Must follow semver (e.g. 1.0.0)."
        )

    return errors


def _find_skill_md_in_zip(zf: zipfile.ZipFile) -> str | None:
    """
    Find SKILL.md path in zip archive.
    在 zip 中查找 SKILL.md 路径。

    Supports two structures / 支持两种结构：
    1. SKILL.md in root directory / SKILL.md 在根目录
    2. SKILL.md in the only top-level subdirectory / SKILL.md 在唯一的顶层子目录中
    """
    names = zf.namelist()

    if "SKILL.md" in names:
        return "SKILL.md"

    candidates = [
        n for n in names
        if n.endswith("/SKILL.md") and n.count("/") == 1
    ]
    if len(candidates) == 1:
        return candidates[0]

    return None


def _get_zip_prefix(skill_md_path: str) -> str:
    """Derive prefix from SKILL.md zip path / 从 SKILL.md 的 zip 路径推导出前缀"""
    idx = skill_md_path.rfind("/")
    return skill_md_path[: idx + 1] if idx >= 0 else ""


def validate_skill_package(zip_path: str | Path) -> list[str]:
    """
    Validate skill ZIP package integrity.
    校验技能 ZIP 包完整性。

    Args:
        zip_path: ZIP file path / ZIP 文件路径

    Returns:
        List of errors (empty list means passed) / 错误列表（空列表表示通过）
    """
    zip_path = Path(zip_path)
    errors: list[str] = []

    if not zip_path.exists():
        return [f"File not found: {zip_path}"]

    if zip_path.suffix.lower() not in ALLOWED_SKILL_EXTENSIONS:
        errors.append(
            f"File extension must be .zip, got '{zip_path.suffix}'"
        )

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # ZIP bomb protection / ZIP bomb 防护
            zip_safety_errors = validate_zip_safety(zip_path, zf)
            if zip_safety_errors:
                errors.extend(zip_safety_errors)
                return errors

            skill_md_path = _find_skill_md_in_zip(zf)
            if not skill_md_path:
                errors.append(
                    "Missing SKILL.md in package root "
                    "(also checked single subdirectory)"
                )
                return errors

            # Parse and validate SKILL.md / 解析并校验 SKILL.md
            skill_md_data = zf.read(skill_md_path).decode("utf-8")
            try:
                metadata = parse_skill_md(skill_md_data)
            except SkillPackageError as e:
                errors.append(str(e))
                return errors

            metadata_errors = validate_skill_metadata(metadata)
            errors.extend(metadata_errors)

            # Check if server/ directory exists / 检查 server/ 目录是否存在
            prefix = _get_zip_prefix(skill_md_path)
            server_entries = [
                n for n in zf.namelist()
                if n.startswith(f"{prefix}server/")
            ]
            if not server_entries:
                errors.append("Missing 'server/' directory in skill package")

            # Path traversal check / 路径遍历检查
            for name in zf.namelist():
                normalized = os.path.normpath(name)
                if (
                    normalized.startswith("..")
                    or normalized.startswith("/")
                    or normalized.startswith("\\")
                    or os.path.isabs(normalized)
                ):
                    errors.append(f"Suspicious path in archive: {name}")

    except zipfile.BadZipFile:
        errors.append("File is not a valid zip archive")

    return errors


def extract_skill_package(
    zip_path: str | Path,
    target_dir: str | Path,
) -> dict[str, Any]:
    """
    Extract skill ZIP package to target directory.
    解压技能 ZIP 包到目标目录。

    Args:
        zip_path: ZIP file path / ZIP 文件路径
        target_dir: Extraction target directory / 解压目标目录

    Returns:
        Metadata dict parsed from SKILL.md / 从 SKILL.md 解析的元数据字典

    Raises:
        SkillPackageError: Validation failed or extraction error / 校验失败或解压错误
    """
    zip_path = Path(zip_path)
    target_dir = Path(target_dir)

    errors = validate_skill_package(zip_path)
    if errors:
        raise SkillPackageError(
            "Skill package validation failed:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        skill_md_path = _find_skill_md_in_zip(zf)
        prefix = _get_zip_prefix(skill_md_path or "SKILL.md")

        for member in zf.infolist():
            if prefix and not member.filename.startswith(prefix):
                continue

            relative = member.filename[len(prefix):]
            if not relative:
                continue

            out_path = (target_dir / relative).resolve()
            if not str(out_path).startswith(str(target_dir.resolve())):
                raise SkillPackageError(
                    f"Unsafe path in archive: {member.filename}"
                )

            if member.is_dir():
                out_path.mkdir(parents=True, exist_ok=True)
            else:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(out_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    # Read extracted SKILL.md / 读取解压后的 SKILL.md
    skill_md_file = target_dir / "SKILL.md"
    metadata = parse_skill_md(skill_md_file.read_text(encoding="utf-8"))

    logger.info(
        "Skill package extracted: {} -> {} ({} v{})",
        zip_path, target_dir,
        metadata.get("name"), metadata.get("version"),
    )
    return metadata


def get_skill_storage_dir(package_id: int) -> Path:
    """
    Get the permanent storage directory for a skill package.
    获取技能包的永久存储目录。

    Args:
        package_id: Database ID of SkillPackage / SkillPackage 的数据库 ID

    Returns:
        Storage directory path / 存储目录路径
    """
    return SKILLS_STORAGE_DIR / str(package_id)


def cleanup_skill_storage(package_id: int) -> None:
    """
    Clean up the storage directory of a skill package.
    清理技能包的存储目录。

    Args:
        package_id: Database ID of SkillPackage / SkillPackage 的数据库 ID
    """
    storage_dir = get_skill_storage_dir(package_id)
    if storage_dir.exists():
        shutil.rmtree(storage_dir, ignore_errors=True)
        logger.info("Skill storage cleaned: {}", storage_dir)


def read_env_example(extract_dir: Path) -> str | None:
    """
    Read .env.example file content from extracted directory.
    从解压目录中读取 .env.example 文件内容。

    Search order / 查找顺序：
    1. server/.env.example
    2. .env.example (root directory / 根目录)

    Args:
        extract_dir: Extracted directory / 解压后的目录

    Returns:
        File content string, returns None if not found /
        文件内容字符串，未找到返回 None
    """
    candidates = [
        extract_dir / "server" / ".env.example",
        extract_dir / ".env.example",
    ]
    for path in candidates:
        if path.exists() and path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
                logger.info("Found .env.example at {}", path)
                return content
            except Exception as exc:
                logger.warning("Failed to read .env.example: {}", exc)
    return None


def validate_zip_safety(
    zip_path: Path,
    zf: zipfile.ZipFile | None = None,
) -> list[str]:
    """
    Validate ZIP file safety: file size, uncompressed size, file count, compression ratio.
    校验 ZIP 文件安全性：文件大小、解压大小、文件数量、压缩比。

    Args:
        zip_path: ZIP file path / ZIP 文件路径
        zf: Already opened ZipFile object (optional, avoids re-opening) /
            已打开的 ZipFile 对象（可选，避免重复打开）

    Returns:
        List of errors (empty list means safe) / 错误列表（空列表表示安全）
    """
    errors: list[str] = []
    zip_path = Path(zip_path)

    # 1. Compressed file size check / 压缩文件大小检查
    file_size = zip_path.stat().st_size
    if file_size > MAX_ZIP_FILE_SIZE:
        size_mb = file_size / (1024 * 1024)
        limit_mb = MAX_ZIP_FILE_SIZE / (1024 * 1024)
        errors.append(
            f"ZIP file too large: {size_mb:.1f}MB (limit: {limit_mb:.0f}MB)"
        )
        return errors

    # 2. Uncompressed size + file count + compression ratio check
    # 解压大小 + 文件数量 + 压缩比检查
    should_close = False
    if zf is None:
        zf = zipfile.ZipFile(zip_path, "r")
        should_close = True

    try:
        total_uncompressed = sum(info.file_size for info in zf.infolist())
        file_count = len(zf.infolist())

        if total_uncompressed > MAX_ZIP_UNCOMPRESSED_SIZE:
            size_mb = total_uncompressed / (1024 * 1024)
            limit_mb = MAX_ZIP_UNCOMPRESSED_SIZE / (1024 * 1024)
            errors.append(
                f"ZIP uncompressed size too large: {size_mb:.1f}MB "
                f"(limit: {limit_mb:.0f}MB)"
            )

        if file_count > MAX_ZIP_FILE_COUNT:
            errors.append(
                f"ZIP contains too many files: {file_count} "
                f"(limit: {MAX_ZIP_FILE_COUNT})"
            )

        if file_size > 0:
            ratio = total_uncompressed / file_size
            if ratio > MAX_ZIP_RATIO:
                errors.append(
                    f"Suspicious compression ratio: {ratio:.0f}x "
                    f"(limit: {MAX_ZIP_RATIO:.0f}x, possible ZIP bomb)"
                )
    finally:
        if should_close:
            zf.close()

    return errors


__all__ = [
    "ALLOWED_SKILL_EXTENSIONS",
    "MAX_ZIP_FILE_SIZE",
    "MAX_ZIP_UNCOMPRESSED_SIZE",
    "MAX_ZIP_FILE_COUNT",
    "SKILLS_STORAGE_DIR",
    "SkillPackageError",
    "cleanup_skill_storage",
    "extract_skill_package",
    "get_skill_storage_dir",
    "parse_skill_md",
    "read_env_example",
    "validate_skill_metadata",
    "validate_skill_package",
    "validate_zip_safety",
]
