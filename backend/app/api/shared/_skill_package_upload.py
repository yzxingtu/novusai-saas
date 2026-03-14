"""
技能包上传共享逻辑 / Skill Package Upload Shared Logic

admin/tenant 两端 upload_skill_package 的公共流程提取，
Common upload flow extracted from admin/tenant upload_skill_package,
通过参数区分端（scope / tenant_id / is_system / service 类型）。
differentiated by parameters (scope / tenant_id / is_system / service type).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path as FilePath
from typing import TYPE_CHECKING, Any

from app.core.i18n import _
from app.core.logging import LogManager
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
    scope: str,
    tenant_id: int | None,
    is_system: bool = False,
    source_plugin: bool = False,
) -> tuple[Any, str, str]:
    """
    处理技能包 ZIP 上传的公共流程。
    Common flow for processing skill package ZIP upload.

    Args:
        db: 数据库会话 / Database session
        file: 上传的 ZIP 文件 / Uploaded ZIP file
        package_service: 已实例化的 SkillPackageService（admin 或 tenant） / Instantiated SkillPackageService (admin or tenant)
        skill_service: 已实例化的 SkillService（admin 或 tenant） / Instantiated SkillService (admin or tenant)
        scope: 资源范围 / Resource scope ("admin" / "tenant")
        tenant_id: 企业 ID（admin 端为 None） / Tenant ID (None for admin)
        is_system: 是否系统包（仅 admin 端使用） / Whether system package (admin only)
        source_plugin: 是否设置 source_plugin 字段 / Whether to set source_plugin field

    Returns:
        (pkg, skill_name, skill_version) 元组 / tuple
    """
    from app.ai.skills.env_parser import parse_env_example
    from app.ai.skills.packaging import (
        ALLOWED_SKILL_EXTENSIONS,
        MAX_ZIP_FILE_SIZE,
        SkillPackageError,
        extract_skill_package,
        get_skill_storage_dir,
        read_env_example,
    )

    if not file.filename:
        raise ValidationException(
            message=_("skill_package.error.file_required"),
            code=4001,
        )

    ext = FilePath(file.filename).suffix.lower()
    if ext not in ALLOWED_SKILL_EXTENSIONS:
        raise ValidationException(
            message=_("skill_package.error.file_must_be_zip"),
            code=4001,
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = FilePath(tmp_dir) / file.filename
        content = await file.read()

        if len(content) > MAX_ZIP_FILE_SIZE:
            size_mb = len(content) / (1024 * 1024)
            limit_mb = MAX_ZIP_FILE_SIZE / (1024 * 1024)
            raise ValidationException(
                message=f"ZIP file too large: {size_mb:.1f}MB (limit: {limit_mb:.0f}MB)",
                code=4001,
            )

        zip_path.write_bytes(content)

        try:
            extract_dir = FilePath(tmp_dir) / "extracted"
            metadata = extract_skill_package(zip_path, extract_dir)
        except SkillPackageError as e:
            raise ValidationException(message=str(e), code=4001)

        skill_name = metadata.get("name", "")
        skill_version = metadata.get("version", "")
        skill_desc = metadata.get("description", "")
        raw_icon = metadata.get("icon", "")
        skill_icon = raw_icon if isinstance(raw_icon, str) and ":" in raw_icon else ""

        # 环境变量需求 / Environment variable requirements
        env_requires: list[str] = []
        meta_block = metadata.get("metadata", {})
        if isinstance(meta_block, dict):
            clawdbot = meta_block.get("clawdbot", {})
            if isinstance(clawdbot, dict):
                requires = clawdbot.get("requires", {})
                if isinstance(requires, dict):
                    env_requires = requires.get("env", [])

        # 解析 .env.example → valves_schema / Parse .env.example → valves_schema
        valves_schema = None
        env_example_content = read_env_example(extract_dir)
        if env_example_content:
            valves_schema = parse_env_example(
                env_example_content,
                required_vars=env_requires,
            ) or None

        # 创建 SkillPackage / Create SkillPackage
        pkg_data: dict[str, Any] = {
            "name": skill_name,
            "description": skill_desc,
            "avatar": skill_icon,
            "scope": scope,
            "is_system": is_system,
            "is_active": True,
            "valves_schema": valves_schema,
        }
        if tenant_id is None:
            pkg_data["tenant_id"] = None

        pkg = await package_service.create(pkg_data)
        await db.flush()

        # 从解压目录中提取 toolkit_content / Extract toolkit_content from extracted directory
        from app.ai.skills.server_converter import convert_server_to_toolkit

        server_dir = extract_dir / "server"
        toolkit_content = ""
        if server_dir.exists():
            toolkit_content = convert_server_to_toolkit(
                server_dir, metadata,
                env_schema=valves_schema,
            )

        # 标记来源（admin 端使用） / Mark source (admin only)
        if source_plugin:
            await package_service.update(pkg.id, {"source_plugin": skill_name})

        # 创建 Skill (toolkit type) / Create Skill (toolkit type)
        await skill_service.create({
            "package_id": pkg.id,
            "name": skill_name,
            "description": skill_desc,
            "avatar": skill_icon,
            "type": "toolkit",
            "is_system": is_system,
            "is_active": True,
            "toolkit_content": toolkit_content,
            "config": {
                "version": str(skill_version),
                "env_requires": env_requires,
            },
        })
        await db.flush()

        # 拷贝到永久存储目录 / Copy to permanent storage directory
        storage_dir = get_skill_storage_dir(pkg.id)
        if storage_dir.exists():
            shutil.rmtree(storage_dir)
        shutil.copytree(extract_dir, storage_dir)

    await db.flush()
    return pkg, skill_name, skill_version
