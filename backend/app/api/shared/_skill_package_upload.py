"""
技能包上传共享逻辑 / Skill Package Upload Shared Logic
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path as FilePath
from typing import TYPE_CHECKING, Any

from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import resolve_public_error_message
from app.exceptions import ValidationException

if TYPE_CHECKING:
    from fastapi import UploadFile
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.base_service import BaseService

logger = LogManager.get_logger("ai")


async def process_skill_package_upload(
    *,
    db: AsyncSession,
    file: UploadFile,
    package_service: BaseService,
    skill_service: BaseService,
    tenant_id: int | None,
    is_system: bool = False,
) -> tuple[Any, str, str]:
    if not file.filename:
        raise ValidationException(
            message=_("skill_package.error.file_required"),
            code=4001,
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = FilePath(tmp_dir) / file.filename
        content = await file.read()
        zip_path.write_bytes(content)
        return await process_skill_package_archive(
            db=db,
            archive_path=zip_path,
            original_filename=file.filename,
            package_service=package_service,
            skill_service=skill_service,
            tenant_id=tenant_id,
            is_system=is_system,
        )


async def process_skill_package_archive(
    *,
    db: AsyncSession,
    archive_path: FilePath,
    original_filename: str,
    package_service: BaseService,
    skill_service: BaseService,
    tenant_id: int | None,
    is_system: bool = False,
    extra_skill_fields: dict[str, Any] | None = None,
) -> tuple[Any, str, str]:
    from app.ai.skills.env_parser import parse_env_example
    from app.ai.skills.packaging import (
        ALLOWED_SKILL_EXTENSIONS,
        MAX_ZIP_FILE_SIZE,
        SkillPackageError,
        extract_skill_package,
        get_skill_storage_dir,
        read_env_example,
    )

    ext = FilePath(original_filename).suffix.lower()
    if ext not in ALLOWED_SKILL_EXTENSIONS:
        raise ValidationException(
            message=_("skill_package.error.file_must_be_zip"),
            code=4001,
        )

    file_size = archive_path.stat().st_size if archive_path.exists() else 0
    if file_size > MAX_ZIP_FILE_SIZE:
        size_mb = file_size / (1024 * 1024)
        limit_mb = MAX_ZIP_FILE_SIZE / (1024 * 1024)
        raise ValidationException(
            message=f"ZIP file too large: {size_mb:.1f}MB (limit: {limit_mb:.0f}MB)",
            code=4001,
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            extract_dir = FilePath(tmp_dir) / "extracted"
            metadata = extract_skill_package(archive_path, extract_dir)
        except SkillPackageError as exc:
            raise ValidationException(
                message=resolve_public_error_message(
                    exc,
                    fallback_message=_("common.validation_error"),
                )
            ) from exc

        skill_name = metadata.get("name", "")
        skill_version = str(metadata.get("version", "") or "")
        skill_desc = metadata.get("description", "")
        raw_icon = metadata.get("icon", "")
        skill_icon = raw_icon if isinstance(raw_icon, str) and ":" in raw_icon else ""

        env_requires: list[str] = []
        meta_block = metadata.get("metadata", {})
        if isinstance(meta_block, dict):
            clawdbot = meta_block.get("clawdbot", {})
            if isinstance(clawdbot, dict):
                requires = clawdbot.get("requires", {})
                if isinstance(requires, dict):
                    env_requires = requires.get("env", [])

        valves_schema = None
        env_example_content = read_env_example(extract_dir)
        if env_example_content:
            valves_schema = parse_env_example(
                env_example_content,
                required_vars=env_requires,
            ) or None

        pkg_data: dict[str, Any] = {
            "name": skill_name,
            "description": skill_desc,
            "avatar": skill_icon,
            "is_system": is_system,
            "is_active": True,
            "valves_schema": valves_schema,
        }
        if tenant_id is not None:
            pkg_data["tenant_id"] = tenant_id

        pkg = await package_service.create(pkg_data)
        await db.flush()

        from app.ai.skills.server_converter import convert_server_to_toolkit

        server_dir = extract_dir / "server"
        toolkit_content = ""
        if server_dir.exists():
            toolkit_content = convert_server_to_toolkit(
                server_dir,
                metadata,
                env_schema=valves_schema,
            )

        skill_payload: dict[str, Any] = {
            "package_id": pkg.id,
            "name": skill_name,
            "description": skill_desc,
            "avatar": skill_icon,
            "type": "toolkit",
            "version": skill_version or "1.0.0",
            "is_system": is_system,
            "is_active": True,
            "toolkit_content": toolkit_content,
            "config": {
                "version": skill_version,
                "env_requires": env_requires,
            },
        }
        if extra_skill_fields:
            merged = dict(extra_skill_fields)
            extra_config = merged.pop("config", None)
            if isinstance(extra_config, dict):
                skill_payload["config"] = {
                    **(skill_payload.get("config") or {}),
                    **extra_config,
                }
            skill_payload.update(merged)

        await skill_service.create(skill_payload)
        await db.flush()

        storage_dir = get_skill_storage_dir(pkg.id)
        if storage_dir.exists():
            shutil.rmtree(storage_dir)
        shutil.copytree(extract_dir, storage_dir)

    await db.flush()
    return pkg, skill_name, skill_version


__all__ = [
    "process_skill_package_archive",
    "process_skill_package_upload",
]
