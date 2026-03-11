"""Dependency whitelist helpers for plugin pip install safety checks.
/ 插件 pip 安装安全检查的依赖白名单工具。"""

from __future__ import annotations

import re

_REQ_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)")

ALLOWED_PACKAGES: set[str] = {
    "aiohttp",
    "anthropic",
    "beautifulsoup4",
    "boto3",
    "click",
    "cryptography",
    "httpx",
    "jinja2",
    "numpy",
    "openai",
    "pandas",
    "pillow",
    "pydantic",
    "pyjwt",
    "pyyaml",
    "redis",
    "requests",
    "tenacity",
}


def _parse_package_name(requirement_line: str) -> str:
    """Extract normalized package name from a requirement line.
    / 从 requirement 行中提取规范化的包名。"""
    line = (requirement_line or "").strip()
    if not line or line.startswith("#"):
        return ""

    if ";" in line:
        line = line.split(";", 1)[0].strip()
    if "#" in line:
        line = line.split("#", 1)[0].strip()
    if not line:
        return ""

    match = _REQ_NAME_RE.match(line)
    if not match:
        return ""

    name = match.group(1)
    if "[" in name:
        name = name.split("[", 1)[0]
    return name.lower().replace("_", "-")


def validate_requirements(requirements: list[str]) -> tuple[list[str], list[str]]:
    """Split requirements into (allowed_lines, rejected_package_names).
    / 将依赖列表拆分为（允许的行, 被拒绝的包名）。"""
    allowed: list[str] = []
    rejected: list[str] = []

    for dep in requirements:
        package_name = _parse_package_name(dep)
        if not package_name:
            continue
        if package_name in ALLOWED_PACKAGES:
            allowed.append(dep)
        else:
            rejected.append(package_name)

    return allowed, rejected


__all__ = ["ALLOWED_PACKAGES", "_parse_package_name", "validate_requirements"]
