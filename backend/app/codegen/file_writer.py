"""
原子文件写入 / Atomic File Writer

临时目录写入 -> 校验 -> 移动到目标，失败则清理
Write to temp dir -> verify -> move to target, cleanup on failure.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.codegen.generator import GeneratedFile


@dataclass
class WriteResult:
    """写入结果 / Write result."""

    success: bool
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    backup_dir: str | None = None


def _normalize_path(p: str | Path, project_root: Path) -> Path:
    """标准化路径，兼容 Windows；校验不逃逸 project_root / Normalize path; ensure within project_root."""
    path = Path(p) if isinstance(p, str) else p
    if not path.is_absolute():
        path = project_root / path
    resolved = path.resolve()
    root_resolved = project_root.resolve()
    if not resolved.is_relative_to(root_resolved):
        raise ValueError(f"Path escapes project root: {p}")
    return resolved


class SmartAppender:
    """
    智能追加器 / Smart appender.

    幂等操作：重复运行不会重复追加
    Idempotent: repeated runs do not duplicate content.
    """

    @staticmethod
    def append_python_import(file_path: Path, import_line: str, all_export: str | None = None) -> bool:
        """
        幂等追加 Python import / Idempotent append Python import.

        Args:
            file_path: 目标文件
            import_line: import 行，如 "from .department import Department"
            all_export: 若需追加到 __all__，传导出的符号名

        Returns:
            是否实际追加了内容
        """
        if not file_path.exists():
            return False
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if import_line.strip() in [ln.strip() for ln in text.splitlines()]:
            return False
        # 在最后一个 import 之后插入，跳过多行 import 块 / Insert after last import, skip multiline blocks
        lines = text.splitlines()
        last_import_idx = -1
        i = 0
        while i < len(lines):
            s = line = lines[i]
            stripped = s.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                if "(" in stripped and stripped.rstrip().endswith("("):
                    # 多行 import 块，找到闭合 ) 再继续 / Multiline block, find closing )
                    i += 1
                    while i < len(lines):
                        if lines[i].strip().startswith(")"):
                            last_import_idx = i
                            break
                        i += 1
                else:
                    last_import_idx = i
            i += 1
        insert_at = last_import_idx + 1 if last_import_idx >= 0 else 0
        new_line = import_line if import_line.endswith("\n") else import_line + "\n"
        lines.insert(insert_at, new_line.strip())
        if all_export and "__all__" in text:
            # 精确解析 __all__ 列表，检查是否已包含 all_export
            _all_match = re.search(
                r'__all__\s*=\s*\[(.*?)\]',
                text,
                re.DOTALL,
            )
            if _all_match:
                _all_content = _all_match.group(1)
                if re.search(rf'["\']({re.escape(all_export)})["\']', _all_content):
                    pass  # 已存在 / already present
                else:
                    for i, line in enumerate(lines):
                        if "__all__" in line and "=" in line:
                            for j in range(i + 1, len(lines)):
                                if "]" in lines[j]:
                                    lines[j] = lines[j].replace("]", f'    "{all_export}",\n]', 1)
                                    break
                            break
        file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True

    @staticmethod
    def append_to_import_block(file_path: Path, import_prefix: str, symbol: str) -> bool:
        """
        幂等追加到多行 import 块 / Idempotent append to multi-line import block.

        在 `{import_prefix} (...)` 块的 `)` 之前插入 symbol。
        """
        if not file_path.exists():
            return False
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if symbol in text:
            return False
        lines = text.splitlines()
        in_block = False
        insert_idx = -1
        indent = "    "
        for i, line in enumerate(lines):
            if import_prefix in line and "(" in line:
                in_block = True
                continue
            if in_block:
                stripped = line.strip()
                if stripped.startswith(")"):
                    insert_idx = i
                    break
                if stripped and not stripped.startswith("#") and not stripped.startswith(")"):
                    indent = line[: len(line) - len(line.lstrip())]
        if insert_idx < 0:
            return False
        lines.insert(insert_idx, f"{indent}{symbol},")
        file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True

    @staticmethod
    def append_to_tenant_import_block(file_path: Path, symbol: str, all_export: str | None = None) -> bool:
        """
        幂等追加到 app.models.tenant import 块 / Idempotent append to tenant import block.

        在 `from app.models.tenant import (...)` 块内添加 symbol，避免错误插入独立 import 行。
        """
        if not file_path.exists():
            return False
        text = file_path.read_text(encoding="utf-8", errors="replace")
        lines_list = text.splitlines()
        for ln in lines_list:
            if ln.strip().rstrip(",").strip() == symbol:
                return False
        lines = text.splitlines()
        in_tenant_block = False
        insert_idx = -1
        indent = "    "
        for i, line in enumerate(lines):
            if "from app.models.tenant import" in line and "(" in line:
                in_tenant_block = True
                continue
            if in_tenant_block:
                stripped = line.strip()
                if stripped.startswith(")"):
                    insert_idx = i
                    break
                if stripped and not stripped.startswith(")"):
                    indent = line[: len(line) - len(line.lstrip())]
        if insert_idx < 0:
            return False
        new_line = f"{indent}{symbol},"
        lines.insert(insert_idx, new_line)
        # __all__ 追加（若未包含）/ Append to __all__ if not present
        if all_export and f'"{all_export}"' not in text:
            for i, line in enumerate(lines):
                if "__all__" in line and "=" in line:
                    for j in range(i + 1, len(lines)):
                        if "]" in lines[j]:
                            pad = len(lines[j]) - len(lines[j].lstrip())
                            lines.insert(j, " " * pad + f'"{all_export}",')
                            break
                    break
        file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True

    @staticmethod
    def append_router_registration(
        file_path: Path,
        import_line: str,
        include_line: str,
        controller_name: str,
        comment: str = "",
    ) -> bool:
        """
        幂等追加路由注册 / Idempotent append router registration.

        智能插入：import 到 import 区，include_router 到路由注册区，Controller 到 __all__。
        """
        if not file_path.exists():
            return False
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if include_line.strip() in text:
            return False
        if f'"{controller_name}"' in text or f"'{controller_name}'" in text:
            return False
        lines = text.splitlines()
        import_lines = [ln.strip() for ln in import_line.strip().split("\n") if ln.strip()]
        if not import_lines:
            return False

        # 1. 找到最后一个 from app.api.{scope} 的 import 行后插入
        last_scope_import_idx = -1
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("from app.api.") and (" import " in stripped):
                last_scope_import_idx = i
        insert_import_at = last_scope_import_idx + 1 if last_scope_import_idx >= 0 else 0

        # 2. 找到最后一个 include_router 行后插入
        router_var = "tenant_router" if "tenant_router" in include_line else "admin_router"
        last_include_idx = -1
        for i, line in enumerate(lines):
            if f"{router_var}.include_router(" in line:
                last_include_idx = i
        insert_include_at = last_include_idx + 1 if last_include_idx >= 0 else len(lines)

        # 3. 找到 __all__ 中 ] 前插入 controller_name
        all_insert_idx = -1
        all_indent = "    "
        for i, line in enumerate(lines):
            if "__all__" in line and "=" in line:
                for j in range(i + 1, len(lines)):
                    if "]" in lines[j]:
                        indent = ""
                        for c in lines[j]:
                            if c in " \t":
                                indent += c
                            else:
                                break
                        all_indent = indent or "    "
                        if f'"{controller_name}"' not in lines[j] and f"'{controller_name}'" not in lines[j]:
                            all_insert_idx = j
                        break
                break

        # 插入 import
        for idx, imp in enumerate(reversed(import_lines)):
            lines.insert(insert_import_at, imp)
        insert_include_at += len(import_lines)
        if all_insert_idx >= 0:
            all_insert_idx += len(import_lines)

        # 插入 include_router（在注释后）
        include_block = [comment] if comment else []
        include_block.append(include_line)
        for idx, inc in enumerate(reversed(include_block)):
            if inc.strip():
                lines.insert(insert_include_at, inc)
        if all_insert_idx >= 0:
            all_insert_idx += len([x for x in include_block if x.strip()])

        # 插入 __all__
        if all_insert_idx >= 0:
            lines.insert(all_insert_idx, f'{all_indent}"{controller_name}",')

        file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True

    @staticmethod
    def merge_json(file_path: Path, new_data: dict) -> list[str]:
        """
        深度合并 JSON / Deep merge JSON.

        Args:
            file_path: JSON 文件路径
            new_data: 要合并的顶层 key -> value

        Returns:
            本次合并新增的 key 列表
        """
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8", errors="replace")
            try:
                existing = json.loads(content)
            except json.JSONDecodeError:
                existing = {}
        else:
            existing = {}
        merged = _deep_merge(existing, new_data)
        added: list[str] = []
        for k in new_data:
            if k not in existing or existing[k] != merged.get(k):
                added.append(k)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return added

    @staticmethod
    def append_ts_export(file_path: Path, export_line: str) -> bool:
        """
        幂等追加 TypeScript export / Idempotent append TS export.

        Args:
            file_path: index.ts 路径
            export_line: 如 "export * from './department';"

        Returns:
            是否实际追加
        """
        if not file_path.exists():
            return False
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if export_line.strip() in text:
            return False
        file_path.write_text(text.rstrip() + "\n" + export_line + "\n", encoding="utf-8")
        return True

    @staticmethod
    def insert_before_last(file_path: Path, marker: str, content: str) -> bool:
        """
        在最后一次出现 marker 之前插入 content / Insert content before last occurrence of marker.

        幂等：若 content.strip() 已存在则跳过
        Idempotent: skip if content.strip() already present.
        """
        if not file_path.exists():
            return False
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if content.strip() in text:
            return False
        last_idx = text.rfind(marker)
        if last_idx < 0:
            return False
        new_text = text[:last_idx] + content.rstrip() + "\n" + text[last_idx:]
        file_path.write_text(new_text, encoding="utf-8")
        return True


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并字典 / Deep merge dict."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


class FileWriter:
    """
    原子文件写入器 / Atomic file writer.

    先写入临时目录，全部成功后移动到目标
    Writes to temp dir first, moves to target on success.
    """

    def __init__(self, project_root: Path | None = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()

    def write_atomic(
        self,
        files: list[GeneratedFile],
        project_root: Path | None = None,
        force: bool = True,
    ) -> WriteResult:
        """
        原子写入 / Atomic write.

        流程：.novus_codegen_tmp/{ts}/ -> 移动 -> 覆盖前备份到 .novus_codegen_backup/{ts}/
        Flow: .novus_codegen_tmp/{ts}/ -> move -> backup to .novus_codegen_backup/{ts}/ before overwrite

        Args:
            files: 生成文件列表
            project_root: 项目根目录
            force: True=覆盖已存在文件；False=已存在则记录 conflict 且不覆盖

        Returns:
            WriteResult
        """
        root = project_root or self.project_root
        ts = int(time.time() * 1000)
        tmp_dir = root / ".novus_codegen_tmp" / str(ts)
        backup_dir = root / ".novus_codegen_backup" / str(ts)
        result = WriteResult(success=False)
        original_backups: dict[Path, Path] = {}
        created_paths: set[Path] = set()

        def _remember_backup(dest: Path, rel_for_backup: Path | str) -> None:
            if not dest.exists() or dest in original_backups or not dest.is_file():
                return
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_rel = rel_for_backup if isinstance(rel_for_backup, Path) else Path(rel_for_backup)
            backup_path = backup_dir / backup_rel
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, backup_path)
            original_backups[dest] = backup_path

        def _rollback_changes() -> None:
            for dest, backup_path in original_backups.items():
                if backup_path.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_path, dest)
            for created_path in sorted(created_paths, key=lambda p: len(p.parts), reverse=True):
                try:
                    if created_path.exists():
                        created_path.unlink()
                except OSError:
                    pass

        try:
            tmp_dir.mkdir(parents=True, exist_ok=True)
            created: list[str] = []
            modified: list[str] = []

            for f in files:
                dest = _normalize_path(f.path, root)
                try:
                    rel = dest.relative_to(root)
                except ValueError:
                    rel = Path(f.path)
                tmp_file = tmp_dir / rel
                tmp_file.parent.mkdir(parents=True, exist_ok=True)

                if f.action == "create_if_missing":
                    if not dest.exists():
                        tmp_file.write_text(f.content or "# Codegen module init\n", encoding="utf-8")
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(tmp_file, dest)
                        created_paths.add(dest)
                        rel_str = str(rel).replace("\\", "/") if isinstance(rel, Path) else f.path
                        created.append(rel_str)
                elif f.action == "create":
                    existed_before = dest.exists()
                    if dest.exists():
                        rel_path = str(rel).replace("\\", "/") if isinstance(rel, Path) else f.path
                        result.conflicts.append({"path": rel_path, "reason": "file_exists"})
                        if not force:
                            continue
                        _remember_backup(dest, rel)
                        modified.append(str(rel).replace("\\", "/") if isinstance(rel, Path) else f.path)
                    tmp_file.write_text(f.content, encoding="utf-8")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(tmp_file, dest)
                    rel_str = str(rel).replace("\\", "/") if isinstance(rel, Path) else f.path
                    if not existed_before:
                        created.append(rel_str)
                        created_paths.add(dest)
                elif f.action == "register_model" and f.model_meta:
                    rel_str = str(rel).replace("\\", "/") if isinstance(rel, Path) else f.path
                    meta = f.model_meta
                    module = meta.get("module", "")
                    resource = meta.get("resource", "")
                    pascal = meta.get("pascal", "")
                    target = meta.get("target", "module")
                    if module and resource and pascal:
                        if not dest.exists():
                            result.errors.append(
                                f"register_model failed: target file does not exist: {rel_str}. "
                                "Ensure models/{module}/__init__.py exists for new modules."
                            )
                        elif target == "module":
                            _remember_backup(dest, rel)
                            import_line = f"from app.models.{module}.{resource} import {pascal}"
                            if SmartAppender.append_python_import(dest, import_line, all_export=pascal):
                                modified.append(rel_str)
                        elif target == "root":
                            _remember_backup(dest, rel)
                            if module == "tenant":
                                if SmartAppender.append_to_tenant_import_block(dest, pascal, all_export=pascal):
                                    modified.append(rel_str)
                            else:
                                import_line = f"from app.models.{module}.{resource} import {pascal}"
                                if SmartAppender.append_python_import(dest, import_line, all_export=pascal):
                                    modified.append(rel_str)
                        elif target == "env":
                            _remember_backup(dest, rel)
                            if SmartAppender.append_to_import_block(dest, "from app.models import", pascal):
                                modified.append(rel_str)
                elif f.action == "register_route" and f.route_meta:
                    rel_str = str(rel).replace("\\", "/") if isinstance(rel, Path) else f.path
                    scope = f.route_meta.get("scope", "")
                    resource = f.route_meta.get("resource", "")
                    if scope and resource:
                        if not dest.exists():
                            result.errors.append(
                                f"register_route failed: target file does not exist: {rel_str}. "
                                f"Ensure api/{scope}/__init__.py exists."
                            )
                        else:
                            pascal = "".join(
                                w.capitalize() for w in str(resource).replace("-", "_").split("_")
                            )
                            prefix = "Admin" if scope == "admin" else "Tenant"
                            controller_name = f"{prefix}{pascal}Controller"
                            router_var = f"{scope}_router"
                            import_line = (
                                f"from app.api.{scope}.{resource} import {controller_name}\n"
                                f"from app.api.{scope}.{resource} import router as {resource}_router"
                            )
                            include_line = f"{router_var}.include_router({resource}_router)"
                            comment = f"# Codegen auto-registered: {resource}"
                            _remember_backup(dest, rel)
                            if SmartAppender.append_router_registration(
                                dest, import_line, include_line, controller_name, comment
                            ):
                                modified.append(rel_str)
                elif f.action == "append" and f.appended_content:
                    rel_str = str(rel).replace("\\", "/") if isinstance(rel, Path) else f.path
                    if dest.exists():
                        content = dest.read_text(encoding="utf-8", errors="replace")
                        if f.appended_content.strip() not in content:
                            _remember_backup(dest, rel)
                            if f.insert_before_last_marker:
                                if SmartAppender.insert_before_last(
                                    dest, f.insert_before_last_marker, f.appended_content
                                ):
                                    modified.append(rel_str)
                            else:
                                dest.write_text(content.rstrip() + "\n" + f.appended_content + "\n", encoding="utf-8")
                                modified.append(rel_str)
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_text(f.appended_content + "\n", encoding="utf-8")
                        created_paths.add(dest)
                        created.append(rel_str)
                elif f.action == "merge_json" and f.merged_keys:
                    rel_str = str(rel).replace("\\", "/") if isinstance(rel, Path) else f.path
                    try:
                        data = json.loads(f.content) if f.content else {}
                    except (json.JSONDecodeError, TypeError):
                        data = {}
                    # Ensure top-level merged_keys present; skip nested (e.g. "tenant.article") / 仅合并顶层键，跳过嵌套（如 tenant.article）
                    for k in f.merged_keys:
                        if "." not in k and k not in data:
                            data[k] = {}
                    existed_before = dest.exists()
                    if existed_before:
                        _remember_backup(dest, rel)
                    SmartAppender.merge_json(dest, data)
                    if not existed_before:
                        created_paths.add(dest)
                        created.append(rel_str)
                    else:
                        modified.append(rel_str)

            result.files_created = list(dict.fromkeys(created))
            result.files_modified = list(dict.fromkeys(modified))
            if not force and result.conflicts:
                result.errors.append("Files exist and force=False, skipped overwrite")
            result.success = not ((not force and result.conflicts) or result.errors)
            if not result.success:
                _rollback_changes()
                result.files_created = []
                result.files_modified = []
                if backup_dir.exists():
                    shutil.rmtree(backup_dir, ignore_errors=True)
                result.backup_dir = None
            else:
                result.backup_dir = str(backup_dir) if backup_dir.exists() else None
        except Exception as e:
            result.errors.append(str(e))
            _rollback_changes()
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)
        finally:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

        return result


__all__ = ["FileWriter", "WriteResult", "SmartAppender", "GeneratedFile"]
