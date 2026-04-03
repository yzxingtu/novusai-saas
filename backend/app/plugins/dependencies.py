"""
Plugin dependency normalization and validation helpers.
/ 插件依赖归一化与校验辅助。
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from importlib import metadata as importlib_metadata
from typing import Any

from packaging.requirements import Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

_PLUGIN_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_NORMALIZE_PKG_NAME_PATTERN = re.compile(r"[-_.]+")


def validate_plugin_dependency_name(name: str) -> str:
    """Validate plugin dependency name. / 校验插件依赖名称。"""
    normalized = str(name or "").strip()
    if not normalized:
        raise ValueError("dependencies.plugins item cannot be empty")
    if not _PLUGIN_NAME_PATTERN.match(normalized):
        raise ValueError(
            f"Invalid plugin dependency name '{normalized}'. "
            "Must be lowercase kebab-case (e.g. 'crm-module')."
        )
    return normalized


def validate_plugin_dependency_version(version: str) -> str:
    """Validate plugin dependency version specifier. / 校验插件依赖版本约束。"""
    normalized = str(version or "*").strip() or "*"
    if normalized == "*":
        return "*"
    try:
        SpecifierSet(normalized)
    except InvalidSpecifier as exc:
        raise ValueError(
            f"Invalid plugin dependency version specifier '{normalized}'"
        ) from exc
    return normalized


def combine_plugin_dependency_versions(left: str, right: str) -> str:
    """Merge two version constraints for the same plugin. / 合并同一插件的两个版本约束。"""
    left_normalized = validate_plugin_dependency_version(left)
    right_normalized = validate_plugin_dependency_version(right)
    if left_normalized == right_normalized:
        return left_normalized
    if left_normalized == "*":
        return right_normalized
    if right_normalized == "*":
        return left_normalized
    merged = ",".join(
        dict.fromkeys(
            [
                part.strip()
                for part in f"{left_normalized},{right_normalized}".split(",")
                if part.strip()
            ]
        )
    )
    validate_plugin_dependency_version(merged)
    return merged


@dataclass(frozen=True)
class PluginDependencyRequirement:
    """Normalized plugin dependency requirement. / 规范化插件依赖要求。"""

    plugin: str
    version: str = "*"
    source: str = "dependencies.plugins"

    def to_dict(self) -> dict[str, str]:
        return {
            "plugin": self.plugin,
            "source": self.source,
            "version": self.version,
        }


@dataclass(frozen=True)
class PluginDependencyState:
    """Runtime state of a plugin dependency. / 插件依赖的运行时状态。"""

    plugin: str
    version: str
    source: str
    installed: bool
    enabled: bool
    installed_version: str | None
    state: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _iter_plugin_dependency_items(
    items: Any,
    *,
    source: str,
) -> list[PluginDependencyRequirement]:
    normalized: list[PluginDependencyRequirement] = []
    if not isinstance(items, list):
        return normalized
    for raw_item in items:
        if isinstance(raw_item, str):
            normalized.append(
                PluginDependencyRequirement(
                    plugin=validate_plugin_dependency_name(raw_item),
                    version="*",
                    source=source,
                )
            )
            continue

        if hasattr(raw_item, "model_dump"):
            raw_item = raw_item.model_dump()
        elif hasattr(raw_item, "__dict__") and not isinstance(raw_item, dict):
            raw_item = vars(raw_item)

        if not isinstance(raw_item, dict):
            raise ValueError(
                f"{source} item must be a string or object, got {type(raw_item).__name__}"
            )

        normalized.append(
            PluginDependencyRequirement(
                plugin=validate_plugin_dependency_name(raw_item.get("plugin", "")),
                version=validate_plugin_dependency_version(
                    raw_item.get("version", "*")
                ),
                source=source,
            )
        )
    return normalized


def normalize_plugin_dependencies(
    manifest_or_data: Any,
    *,
    include_legacy_requires: bool = True,
) -> list[PluginDependencyRequirement]:
    """Normalize plugin dependency declarations from manifest/model/dict.
    / 从 manifest/model/dict 归一化插件依赖声明。
    """
    dependencies_block: Any = {}
    compatibility_block: Any = {}

    if hasattr(manifest_or_data, "dependencies"):
        dependencies_block = manifest_or_data.dependencies
        compatibility_block = getattr(manifest_or_data, "compatibility", None)
    elif isinstance(manifest_or_data, dict):
        dependencies_block = manifest_or_data.get("dependencies") or {}
        compatibility_block = manifest_or_data.get("compatibility") or {}

    if hasattr(dependencies_block, "model_dump"):
        dependencies_block = dependencies_block.model_dump()
    if hasattr(compatibility_block, "model_dump"):
        compatibility_block = compatibility_block.model_dump()

    deps_items: Any = []
    if isinstance(dependencies_block, dict):
        deps_items = dependencies_block.get("plugins") or []
    else:
        deps_items = getattr(dependencies_block, "plugins", []) or []

    requirements = _iter_plugin_dependency_items(
        deps_items,
        source="dependencies.plugins",
    )

    if include_legacy_requires:
        legacy_items: Any = []
        if isinstance(compatibility_block, dict):
            legacy_items = compatibility_block.get("requires") or []
        elif compatibility_block is not None:
            legacy_items = getattr(compatibility_block, "requires", []) or []
        requirements.extend(
            _iter_plugin_dependency_items(
                legacy_items,
                source="compatibility.requires",
            )
        )

    merged: dict[str, PluginDependencyRequirement] = {}
    for requirement in requirements:
        existing = merged.get(requirement.plugin)
        if existing is None:
            merged[requirement.plugin] = requirement
            continue
        merged[requirement.plugin] = PluginDependencyRequirement(
            plugin=requirement.plugin,
            version=combine_plugin_dependency_versions(
                existing.version,
                requirement.version,
            ),
            source=existing.source
            if existing.source == "dependencies.plugins"
            else requirement.source,
        )
    return list(merged.values())


def plugin_dependency_is_version_satisfied(
    expected_version: str,
    actual_version: str | None,
) -> bool:
    """Check whether actual plugin version satisfies expected specifier.
    / 判断实际插件版本是否满足依赖约束。
    """
    if actual_version is None:
        return False
    normalized = validate_plugin_dependency_version(expected_version)
    if normalized == "*":
        return True
    try:
        return Version(actual_version) in SpecifierSet(normalized)
    except (InvalidSpecifier, InvalidVersion):
        return False


def build_plugin_dependency_states(
    requirements: Iterable[PluginDependencyRequirement],
    plugin_rows: dict[str, dict[str, Any]],
    *,
    require_enabled: bool,
) -> list[PluginDependencyState]:
    """Build runtime states for normalized plugin dependencies.
    / 为规范化插件依赖生成运行时状态。
    """
    states: list[PluginDependencyState] = []
    for requirement in requirements:
        row = plugin_rows.get(requirement.plugin)
        installed = row is not None
        enabled = bool(row and row.get("status") == "enabled")
        installed_version = row.get("version") if row else None
        version_ok = plugin_dependency_is_version_satisfied(
            requirement.version,
            installed_version,
        )

        if not installed:
            state = "missing"
            message = f"{requirement.plugin} not installed"
        elif require_enabled and not enabled:
            state = "disabled"
            message = f"{requirement.plugin} not enabled"
        elif not version_ok:
            state = "version_mismatch"
            message = (
                f"{requirement.plugin} requires {requirement.version}, "
                f"installed {installed_version or 'unknown'}"
            )
        else:
            state = "ready"
            if requirement.version == "*":
                message = f"{requirement.plugin} ready"
            else:
                message = (
                    f"{requirement.plugin} {installed_version} satisfies "
                    f"{requirement.version}"
                )

        states.append(
            PluginDependencyState(
                plugin=requirement.plugin,
                version=requirement.version,
                source=requirement.source,
                installed=installed,
                enabled=enabled,
                installed_version=installed_version,
                state=state,
                message=message,
            )
        )
    return states


def normalize_python_package_name(raw_requirement: str) -> str:
    """Normalize requirement/distribution name. / 规范化 Python requirement/distribution 名称。"""
    raw = re.split(r"[><=!~;@\[]", raw_requirement, maxsplit=1)[0].strip()
    return _NORMALIZE_PKG_NAME_PATTERN.sub("-", raw).lower()


def iter_effective_python_requirements(
    requirements: Iterable[str] | None,
) -> list[Requirement]:
    """Parse requirements and skip unmatched markers. / 解析 requirement 并跳过 marker 不命中的项。"""
    effective: list[Requirement] = []
    for raw in requirements or []:
        raw_text = str(raw or "").strip()
        if not raw_text:
            continue
        requirement = Requirement(raw_text)
        if requirement.marker and not requirement.marker.evaluate():
            continue
        effective.append(requirement)
    return effective


def get_installed_distribution_version(distribution_name: str) -> str | None:
    """Return installed distribution version if present. / 返回已安装分发版本。"""
    try:
        return importlib_metadata.version(distribution_name)
    except importlib_metadata.PackageNotFoundError:
        normalized = normalize_python_package_name(distribution_name)
        candidates = {
            normalized,
            normalized.replace("-", "_"),
            normalized.replace("_", "-"),
        }
        for candidate in candidates:
            try:
                return importlib_metadata.version(candidate)
            except importlib_metadata.PackageNotFoundError:
                continue
    return None


def is_python_requirement_satisfied(requirement: Requirement) -> bool:
    """Check whether current environment satisfies a requirement.
    / 判断当前环境是否满足某个 Python requirement。
    """
    installed_version = get_installed_distribution_version(requirement.name)
    if installed_version is None:
        return False
    if not requirement.specifier:
        return True
    try:
        return Version(installed_version) in requirement.specifier
    except InvalidVersion:
        return False


def build_python_dependency_states(
    requirements: Iterable[str] | None,
) -> list[dict[str, str | bool | None]]:
    """Build current-environment states for declared Python requirements.
    / 为声明的 Python requirement 构建当前环境状态。
    """
    states: list[dict[str, str | bool | None]] = []
    for requirement in iter_effective_python_requirements(requirements):
        installed_version = get_installed_distribution_version(requirement.name)
        satisfied = is_python_requirement_satisfied(requirement)
        states.append(
            {
                "requirement": str(requirement),
                "package": normalize_python_package_name(requirement.name),
                "installed": installed_version is not None,
                "installed_version": installed_version,
                "satisfied": satisfied,
                "state": "ready" if satisfied else "missing",
                "message": (
                    f"{requirement.name} ready"
                    if satisfied
                    else f"{requirement.name} missing or version mismatch"
                ),
            }
        )
    return states


@dataclass(frozen=True)
class PythonDependencyConflict:
    """Detected direct Python dependency conflict. / 检测到的 Python 直接依赖冲突。"""

    package: str
    reason: str
    requirements: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["requirements"] = list(self.requirements)
        return payload


def detect_direct_python_dependency_conflicts(
    requirement_groups: dict[str, list[tuple[str, str]]],
    *,
    installed_versions: dict[str, str | None] | None = None,
) -> list[PythonDependencyConflict]:
    """Conservatively detect direct requirement conflicts.
    / 保守检测直接声明 requirement 的冲突。

    This intentionally focuses on direct declared constraints in the shared host env:
    - multiple incompatible exact pins
    - exact pin rejected by another declared specifier
    - current installed version rejected by any retained owner
    / 当前实现聚焦共享宿主环境下的直接声明约束：
    - 多个不一致的精确 pin
    - 精确 pin 被其他声明约束拒绝
    - 当前已安装版本被任一保留依赖方拒绝
    """
    conflicts: list[PythonDependencyConflict] = []
    installed_versions = installed_versions or {}

    for package, entries in sorted(requirement_groups.items()):
        exact_versions: set[str] = set()
        specifiers: list[SpecifierSet] = []
        requirements_payload: list[dict[str, str]] = []

        for owner, requirement_text in entries:
            requirement = Requirement(requirement_text)
            requirements_payload.append(
                {"owner": owner, "requirement": requirement_text}
            )
            if requirement.specifier:
                specifiers.append(requirement.specifier)
                for spec in requirement.specifier:
                    if spec.operator in {"==", "==="}:
                        exact_versions.add(spec.version)

        if len(exact_versions) > 1:
            conflicts.append(
                PythonDependencyConflict(
                    package=package,
                    reason=(
                        "multiple incompatible exact versions declared: "
                        + ", ".join(sorted(exact_versions))
                    ),
                    requirements=requirements_payload,
                )
            )
            continue

        if exact_versions:
            exact = next(iter(exact_versions))
            try:
                exact_version = Version(exact)
            except InvalidVersion:
                conflicts.append(
                    PythonDependencyConflict(
                        package=package,
                        reason=f"invalid exact version '{exact}' in requirement set",
                        requirements=requirements_payload,
                    )
                )
                continue
            rejected = [
                str(specifier)
                for specifier in specifiers
                if exact_version not in specifier
            ]
            if rejected:
                conflicts.append(
                    PythonDependencyConflict(
                        package=package,
                        reason=(
                            f"exact version {exact} does not satisfy: "
                            + "; ".join(rejected)
                        ),
                        requirements=requirements_payload,
                    )
                )
                continue

        installed_version = installed_versions.get(package)
        if installed_version:
            try:
                installed = Version(installed_version)
            except InvalidVersion:
                installed = None
            if installed is not None:
                rejected = [
                    str(specifier)
                    for specifier in specifiers
                    if installed not in specifier
                ]
                if rejected:
                    conflicts.append(
                        PythonDependencyConflict(
                            package=package,
                            reason=(
                                f"installed version {installed_version} does not satisfy: "
                                + "; ".join(rejected)
                            ),
                            requirements=requirements_payload,
                        )
                    )
                    continue

    return conflicts
