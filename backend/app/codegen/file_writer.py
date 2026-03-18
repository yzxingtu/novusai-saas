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
        # 在最后一个 import 之后插入，或文件开头 / Insert after last import or at file start
        lines = text.splitlines()
        last_import_idx = -1
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith("import ") or s.startswith("from "):
                last_import_idx = i
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
    def append_router_registration(
        file_path: Path,
        import_line: str,
        include_line: str,
        comment: str = "",
    ) -> bool:
        """
        幂等追加路由注册 / Idempotent append router registration.

        Args:
            file_path: __init__.py 路径
            import_line: Controller import
            include_line: router.include_router(...)
            comment: 注释

        Returns:
            是否实际追加
        """
        if not file_path.exists():
            return False
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if include_line.strip() in text or import_line.strip() in text:
            return False
        block = f"\n{comment}\n{import_line}\n{include_line}\n" if comment else f"\n{import_line}\n{include_line}\n"
        file_path.write_text(text.rstrip() + block, encoding="utf-8")
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

        流程：.codegen_tmp/{ts}/ -> 移动 -> 覆盖前备份到 .codegen_backup/{ts}/
        Flow: .codegen_tmp/{ts}/ -> move -> backup to .codegen_backup/{ts}/ before overwrite

        Args:
            files: 生成文件列表
            project_root: 项目根目录
            force: True=覆盖已存在文件；False=已存在则记录 conflict 且不覆盖

        Returns:
            WriteResult
        """
        root = project_root or self.project_root
        ts = int(time.time() * 1000)
        tmp_dir = root / ".codegen_tmp" / str(ts)
        backup_dir = root / ".codegen_backup" / str(ts)
        result = WriteResult(success=False)

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

                if f.action == "create":
                    if dest.exists():
                        rel_path = str(rel).replace("\\", "/") if isinstance(rel, Path) else f.path
                        result.conflicts.append({"path": rel_path, "reason": "file_exists"})
                        if not force:
                            continue
                        if dest.is_file():
                            backup_dir.mkdir(parents=True, exist_ok=True)
                            try:
                                backup_rel = dest.relative_to(root)
                            except ValueError:
                                backup_rel = Path(f.path)
                            backup_path = backup_dir / backup_rel
                            backup_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(dest, backup_path)
                            modified.append(str(rel).replace("\\", "/") if isinstance(rel, Path) else f.path)
                    tmp_file.write_text(f.content, encoding="utf-8")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(tmp_file, dest)
                    rel_str = str(rel).replace("\\", "/") if isinstance(rel, Path) else f.path
                    if rel_str not in modified:
                        created.append(rel_str)
                elif f.action == "append" and f.appended_content:
                    rel_str = str(rel).replace("\\", "/") if isinstance(rel, Path) else f.path
                    if dest.exists():
                        content = dest.read_text(encoding="utf-8", errors="replace")
                        if f.appended_content.strip() not in content:
                            dest.write_text(content.rstrip() + "\n" + f.appended_content + "\n", encoding="utf-8")
                            modified.append(rel_str)
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_text(f.appended_content + "\n", encoding="utf-8")
                        created.append(rel_str)
                elif f.action == "merge_json" and f.merged_keys:
                    rel_str = str(rel).replace("\\", "/") if isinstance(rel, Path) else f.path
                    try:
                        data = json.loads(f.content) if f.content else {}
                    except (json.JSONDecodeError, TypeError):
                        data = {}
                    # Ensure all merged_keys present; fill missing with {}
                    for k in f.merged_keys:
                        if k not in data:
                            data[k] = {}
                    SmartAppender.merge_json(dest, data)
                    modified.append(rel_str)

            result.files_created = list(dict.fromkeys(created))
            result.files_modified = list(dict.fromkeys(modified))
            if not force and result.conflicts:
                result.success = False
                result.errors.append("Files exist and force=False, skipped overwrite")
            else:
                result.success = True
            result.backup_dir = str(backup_dir) if backup_dir.exists() else None
        except Exception as e:
            result.errors.append(str(e))
        finally:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

        return result


__all__ = ["FileWriter", "WriteResult", "SmartAppender", "GeneratedFile"]
