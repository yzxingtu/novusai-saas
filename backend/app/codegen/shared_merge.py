"""
共享文件确定性合并引擎

多表批量生成时，多个实体会同时修改"共享聚合文件"：
- 前端 router index (import + route 注册)
- 前端 API export index (re-export)
- 后端 API 路由注册 __init__.py (import + include_router)
- i18n JSON (已有 deep merge，此处不重复)

核心规则：
- 插入点可定位（marker comment 或尾部追加）
- 去重（按模块名/路径去重，重复 merge 不产生重复）
- 稳定排序（按模块名字母序，同一输入多次 merge 结果一致）
- 合并失败返回结构化错误
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ============================================================
# 共享文件类型
# ============================================================


class SharedFileType(str, Enum):
    """共享文件类型"""

    FRONTEND_ROUTER = "frontend_router"
    FRONTEND_API_EXPORT = "frontend_api_export"
    BACKEND_ROUTER_INIT = "backend_router_init"
    I18N_JSON = "i18n_json"
    UNKNOWN = "unknown"


# ============================================================
# 共享文件路径模式
# ============================================================

# 前端路由聚合文件
_FRONTEND_ROUTER_PATTERNS = (
    re.compile(r"frontend/apps/web-antd/src/router/routes/(admin|tenant)/index\.ts$"),
)

# 前端 API export 聚合文件
_FRONTEND_API_EXPORT_PATTERNS = (
    re.compile(r"frontend/apps/web-antd/src/api/(admin|tenant)/index\.ts$"),
)

# 后端路由注册聚合文件
_BACKEND_ROUTER_INIT_PATTERNS = (
    re.compile(r"backend/app/api/(admin|tenant)/__init__\.py$"),
)


def classify_shared_file(rel_path: str) -> SharedFileType:
    """判断文件是否为共享聚合文件并返回类型"""
    normalized = rel_path.replace("\\", "/")

    if normalized.endswith(".json") and "locales" in normalized:
        return SharedFileType.I18N_JSON

    for pattern in _FRONTEND_ROUTER_PATTERNS:
        if pattern.search(normalized):
            return SharedFileType.FRONTEND_ROUTER

    for pattern in _FRONTEND_API_EXPORT_PATTERNS:
        if pattern.search(normalized):
            return SharedFileType.FRONTEND_API_EXPORT

    for pattern in _BACKEND_ROUTER_INIT_PATTERNS:
        if pattern.search(normalized):
            return SharedFileType.BACKEND_ROUTER_INIT

    return SharedFileType.UNKNOWN


def is_shared_file(rel_path: str) -> bool:
    """判断是否为共享聚合文件"""
    return classify_shared_file(rel_path) != SharedFileType.UNKNOWN


# ============================================================
# 合并结果
# ============================================================


class SharedMergeResult(BaseModel):
    """共享文件合并结果"""

    success: bool = Field(True)
    content: str = Field("", description="合并后的内容")
    added: list[str] = Field(default_factory=list, description="新增的条目")
    skipped: list[str] = Field(default_factory=list, description="跳过的重复条目")
    error: str = Field("", description="错误信息")


# ============================================================
# TypeScript 代码片段提取
# ============================================================

# import 语句匹配
_TS_IMPORT_RE = re.compile(
    r"^import\s+.*?\s+from\s+['\"]([^'\"]+)['\"];?\s*$",
    re.MULTILINE,
)

# export 语句匹配
_TS_EXPORT_RE = re.compile(
    r"^export\s+\{[^}]*\}\s+from\s+['\"]([^'\"]+)['\"];?\s*$",
    re.MULTILINE,
)

# re-export: export * from '...'
_TS_REEXPORT_RE = re.compile(
    r"^export\s+\*\s+from\s+['\"]([^'\"]+)['\"];?\s*$",
    re.MULTILINE,
)


def _extract_import_source(line: str) -> str | None:
    """从 import 行提取 source path"""
    m = _TS_IMPORT_RE.match(line.strip())
    return m.group(1) if m else None


def _extract_export_source(line: str) -> str | None:
    """从 export/re-export 行提取 source path"""
    m = _TS_EXPORT_RE.match(line.strip())
    if m:
        return m.group(1)
    m = _TS_REEXPORT_RE.match(line.strip())
    return m.group(1) if m else None


# ============================================================
# Python 代码片段提取
# ============================================================

# from app.api.xxx import XxxController
_PY_IMPORT_RE = re.compile(
    r"^from\s+([\w.]+)\s+import\s+(\w+)",
    re.MULTILINE,
)

# router.include_router(xxx.router, ...)
_PY_INCLUDE_ROUTER_RE = re.compile(
    r"^(\s*)router\.include_router\(\s*(\w+)\.router",
    re.MULTILINE,
)


# ============================================================
# 前端 Router 合并
# ============================================================

# Marker comments for insertion points
_ROUTER_MARKER_START = "// --- CRUD Generator Routes Start ---"
_ROUTER_MARKER_END = "// --- CRUD Generator Routes End ---"


def merge_frontend_router(
    existing: str,
    new_content: str,
) -> SharedMergeResult:
    """合并前端路由文件

    策略：
    1. 收集现有 + 新增的所有 import 行
    2. 去重（按 import source path）
    3. 按 source path 字母序重新排序所有 import 行
    4. 非 import 行保持原位
    5. 非 import 的 route 注册代码通过 marker 区域追加

    Args:
        existing: 现有文件内容
        new_content: 新生成的路由内容（完整文件或片段）

    Returns:
        SharedMergeResult
    """
    result = SharedMergeResult()

    # 收集现有 import 行（source → line）
    all_imports: dict[str, str] = {}
    non_import_lines: list[str] = []

    for line in existing.splitlines():
        source = _extract_import_source(line)
        if source:
            all_imports[source] = line.strip()
        else:
            non_import_lines.append(line)

    existing_sources = set(all_imports.keys())

    # 提取新内容中的 import 行和其他行
    new_other_lines: list[str] = []

    for line in new_content.splitlines():
        source = _extract_import_source(line)
        if source:
            if source in existing_sources:
                result.skipped.append(source)
            else:
                all_imports[source] = line.strip()
                result.added.append(source)
        elif line.strip() and not line.strip().startswith("//"):
            new_other_lines.append(line)

    if not result.added and not new_other_lines:
        result.content = existing
        return result

    # 重组：找到第一个非 import 行的位置，在它之前放所有排序后的 import
    sorted_imports = [line for _, line in sorted(all_imports.items())]
    lines = sorted_imports + non_import_lines

    # 对于非 import 的 route 注册代码，检查 marker 区域
    if new_other_lines:
        content_str = "\n".join(lines)
        if _ROUTER_MARKER_START in content_str and _ROUTER_MARKER_END in content_str:
            start_idx = None
            end_idx = None
            for i, line in enumerate(lines):
                if _ROUTER_MARKER_START in line:
                    start_idx = i
                if _ROUTER_MARKER_END in line:
                    end_idx = i

            if start_idx is not None and end_idx is not None:
                existing_block = "\n".join(lines[start_idx + 1:end_idx])
                for new_line in new_other_lines:
                    if new_line.strip() not in existing_block:
                        lines.insert(end_idx, new_line)
                        end_idx += 1

    result.content = "\n".join(lines)
    if existing.endswith("\n") and not result.content.endswith("\n"):
        result.content += "\n"
    return result


# ============================================================
# 前端 API Export 合并
# ============================================================


def merge_frontend_api_export(
    existing: str,
    new_content: str,
) -> SharedMergeResult:
    """合并前端 API export 聚合文件

    策略：
    1. 收集现有 + 新增的所有 export 行
    2. 去重（按 source path）
    3. 按 source path 字母序重新排序所有 export 行
    4. 非 export 行保持原位

    Args:
        existing: 现有文件内容
        new_content: 新生成的 export 内容

    Returns:
        SharedMergeResult
    """
    result = SharedMergeResult()

    # 收集现有 export 行（source → line）
    all_exports: dict[str, str] = {}
    non_export_lines: list[str] = []

    for line in existing.splitlines():
        source = _extract_export_source(line)
        if source:
            all_exports[source] = line.strip()
        else:
            non_export_lines.append(line)

    existing_sources = set(all_exports.keys())

    # 合并新的 export 行
    for line in new_content.splitlines():
        source = _extract_export_source(line)
        if source:
            if source in existing_sources:
                result.skipped.append(source)
            else:
                all_exports[source] = line.strip()
                result.added.append(source)

    if not result.added:
        result.content = existing
        return result

    # 按 source 字母序排序所有 export 行
    sorted_exports = [line for _, line in sorted(all_exports.items())]

    # 重组：非 export 行 + 排序后的 export 行
    final_lines = non_export_lines + sorted_exports

    result.content = "\n".join(final_lines) + "\n"
    return result


# ============================================================
# 后端路由注册 __init__.py 合并
# ============================================================


def merge_backend_router_init(
    existing: str,
    new_content: str,
) -> SharedMergeResult:
    """合并后端路由注册聚合文件

    策略：
    1. 收集现有 + 新增的所有 import 和 include_router 行
    2. 去重（按 module path / var name）
    3. 分别按模块名字母序重新排序 import 区和 include_router 区
    4. 非 import / include_router 行保持原位

    Args:
        existing: 现有文件内容
        new_content: 新生成的路由注册内容

    Returns:
        SharedMergeResult
    """
    result = SharedMergeResult()

    # 分类现有行
    all_imports: dict[str, str] = {}   # module → full line
    all_routers: dict[str, str] = {}   # var_name → full line
    other_lines: list[tuple[str, str]] = []  # (zone, line)
    # zone: "pre_import", "between", "post_router"

    zone = "pre_import"
    found_import = False
    found_router = False

    for line in existing.splitlines():
        im = _PY_IMPORT_RE.match(line.strip())
        ir = _PY_INCLUDE_ROUTER_RE.match(line)

        if im:
            all_imports[im.group(1)] = line.rstrip()
            found_import = True
            zone = "between"
        elif ir:
            all_routers[ir.group(2)] = line.rstrip()
            found_router = True
            zone = "post_router"
        else:
            other_lines.append((zone, line))

    existing_modules = set(all_imports.keys())
    existing_router_vars = set(all_routers.keys())

    # 合并新内容
    for line in new_content.splitlines():
        im = _PY_IMPORT_RE.match(line.strip())
        if im:
            module = im.group(1)
            if module not in existing_modules:
                all_imports[module] = line.strip()
                result.added.append(f"import:{module}")
            else:
                result.skipped.append(f"import:{module}")
            continue

        ir = _PY_INCLUDE_ROUTER_RE.match(line)
        if ir:
            var_name = ir.group(2)
            if var_name not in existing_router_vars:
                all_routers[var_name] = line.rstrip()
                result.added.append(f"include_router:{var_name}")
            else:
                result.skipped.append(f"include_router:{var_name}")

    if not result.added:
        result.content = existing
        return result

    # 重组文件：pre_import lines → sorted imports → between lines → sorted routers → post lines
    final_lines: list[str] = []

    for zone, line in other_lines:
        if zone == "pre_import":
            final_lines.append(line)

    # 排序后的 imports
    for _, imp_line in sorted(all_imports.items()):
        final_lines.append(imp_line)

    for zone, line in other_lines:
        if zone == "between":
            final_lines.append(line)

    # 排序后的 include_routers
    for _, router_line in sorted(all_routers.items()):
        final_lines.append(router_line)

    for zone, line in other_lines:
        if zone == "post_router":
            final_lines.append(line)

    result.content = "\n".join(final_lines)
    if existing.endswith("\n") and not result.content.endswith("\n"):
        result.content += "\n"
    return result


# ============================================================
# 统一合并入口
# ============================================================


def merge_shared_file(
    rel_path: str,
    existing: str,
    new_content: str,
) -> SharedMergeResult:
    """统一的共享文件合并入口

    根据文件类型自动选择合并策略。

    Args:
        rel_path: 相对路径
        existing: 现有文件内容
        new_content: 新生成的内容

    Returns:
        SharedMergeResult
    """
    file_type = classify_shared_file(rel_path)

    if file_type == SharedFileType.FRONTEND_ROUTER:
        return merge_frontend_router(existing, new_content)
    elif file_type == SharedFileType.FRONTEND_API_EXPORT:
        return merge_frontend_api_export(existing, new_content)
    elif file_type == SharedFileType.BACKEND_ROUTER_INIT:
        return merge_backend_router_init(existing, new_content)
    elif file_type == SharedFileType.I18N_JSON:
        # i18n JSON 由 writer 的 _deep_merge 处理
        return SharedMergeResult(
            success=True,
            content=new_content,
            error="i18n JSON should use writer._merge_i18n_json()",
        )
    else:
        return SharedMergeResult(
            success=False,
            content=existing,
            error=f"Unknown shared file type for '{rel_path}'",
        )


__all__ = [
    "SharedFileType",
    "SharedMergeResult",
    "classify_shared_file",
    "is_shared_file",
    "merge_shared_file",
    "merge_frontend_router",
    "merge_frontend_api_export",
    "merge_backend_router_init",
]
