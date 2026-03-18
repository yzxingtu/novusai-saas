"""
ZIP 导出与代码格式化 / Zip Exporter and Code Formatting

将生成文件打包为 zip，调用 ruff + prettier 格式化
Packs generated files as zip, invokes ruff + prettier for formatting.
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.codegen.generator import GeneratedFile


def export_zip(files: list[GeneratedFile]) -> bytes:
    """
    将生成文件打包为 zip / Pack generated files into zip.

    Args:
        files: 生成文件列表

    Returns:
        zip 文件二进制内容
    """
    buf = io.BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as zf:
        for f in files:
            if f.content is not None:
                zf.writestr(f.path.replace("\\", "/"), f.content)
    return buf.getvalue()


def format_code(project_root: Path, files: list[GeneratedFile]) -> tuple[bool, list[str]]:
    """
    调用 ruff format + prettier 格式化代码 / Format code with ruff + prettier.

    Args:
        project_root: 项目根目录
        files: 生成的文件列表，用于确定需格式化的路径

    Returns:
        (是否成功, 错误消息列表)
    """
    errors: list[str] = []
    py_files: list[Path] = []
    fe_files: list[Path] = []

    for f in files:
        p = project_root / f.path
        if not p.exists():
            continue
        if f.path.endswith(".py"):
            py_files.append(p)
        elif f.path.endswith((".ts", ".vue", ".json")):
            fe_files.append(p)

    # ruff format 格式化 Python 代码 / ruff format Python code
    if py_files:
        try:
            paths = [str(p) for p in py_files[:20]]
            subprocess.run(
                ["ruff", "format", "--quiet"] + paths,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            pass
        except subprocess.TimeoutExpired:
            errors.append("ruff format timed out")
        except Exception as e:
            errors.append(f"ruff format error: {e}")

    # prettier 格式化前端代码（可选，可能未安装）/ prettier format frontend (optional)
    if fe_files:
        try:
            paths = [str(p) for p in fe_files[:20]]
            subprocess.run(
                ["npx", "prettier", "--write"] + paths,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError:
            pass
        except subprocess.TimeoutExpired:
            errors.append("prettier timed out")
        except Exception as e:
            errors.append(f"prettier error: {e}")

    return len(errors) == 0, errors


__all__ = ["export_zip", "format_code"]
