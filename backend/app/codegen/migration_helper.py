"""
迁移文件元数据注入 / Migration Helper

为生成的迁移文件注入 codegen 元数据变量
Injects codegen metadata variables into generated migration files.
"""

from __future__ import annotations


def inject_migration_metadata(
    content: str,
    resource: str,
    source: str = "codegen",
    version: str = "1",
) -> str:
    """
    为迁移文件内容注入元数据变量 / Inject metadata variables into migration content.

    Args:
        content: 迁移文件原始内容
        resource: 资源名
        source: 来源标识，默认 codegen
        version: 版本号

    Returns:
        注入元数据后的内容
    """
    meta = f"""
# Codegen metadata / 代码生成器元数据
codegen_source = {repr(source)}
codegen_resource = {repr(resource)}
codegen_version = {repr(version)}
"""
    # 在 revision 变量之后插入
    if "revision" in content and "codegen_source" not in content:
        lines = content.split("\n")
        insert_at = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("revision") and "=" in line:
                insert_at = i + 1
                break
        lines.insert(insert_at, meta)
        return "\n".join(lines)
    return content


__all__ = ["inject_migration_metadata"]
