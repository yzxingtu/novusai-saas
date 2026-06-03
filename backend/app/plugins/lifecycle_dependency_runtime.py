"""Dependency/runtime helpers extracted from PluginLifecycle."""

from __future__ import annotations

import json
import os
import shutil
import sys
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.i18n import _
from app.core.logging import get_logger
from app.core.response import resolve_public_error_message
from app.plugins.dependencies import (
    detect_direct_python_dependency_conflicts,
    get_installed_distribution_version,
    iter_effective_python_requirements,
    normalize_python_package_name,
)
from app.plugins.exceptions import PluginDependencyError, PluginError
from app.plugins.lifecycle_support import _IS_WINDOWS, run_subprocess_async
from app.plugins.loader import PLUGINS_DIR

if TYPE_CHECKING:
    pass


logger = get_logger(__name__)


class LifecycleDependencyRuntimeMixin:
    """Host dependency/runtime helpers extracted from PluginLifecycle."""

    def _load_project_pyproject_requirements(self) -> list[str]:
        """Load declared host requirements from pyproject.toml. / 从 pyproject.toml 加载宿主声明的 requirement。"""
        requirements: list[str] = []
        pyproject_path = PLUGINS_DIR.parent / "pyproject.toml"
        if not pyproject_path.is_file():
            return requirements
        try:
            raw = pyproject_path.read_bytes()
            if sys.version_info >= (3, 11):
                import tomllib

                cfg = tomllib.loads(raw.decode(encoding="utf-8"))
            else:
                import tomli

                cfg = tomli.loads(raw.decode(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to parse pyproject.toml: {}", exc)
            return requirements

        project_cfg = cfg.get("project") or {}
        for item in project_cfg.get("dependencies") or []:
            if isinstance(item, str):
                requirements.append(item)
        optional = project_cfg.get("optional-dependencies") or {}
        for deps in optional.values():
            if not isinstance(deps, list):
                continue
            for item in deps:
                if isinstance(item, str):
                    requirements.append(item)
        return list(dict.fromkeys(requirements))

    async def _load_other_plugin_python_requirements(
        self,
        *,
        exclude_plugin_name: str | None = None,
    ) -> dict[str, list[str]]:
        """Load declared Python requirements from installed plugins. / 加载已安装插件声明的 Python requirement。"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel

        filters = [PluginModel.is_deleted.is_(False)]
        if exclude_plugin_name:
            filters.append(PluginModel.name != exclude_plugin_name)
        result = await self._db.execute(
            select(PluginModel.name, PluginModel.manifest).where(*filters)
        )

        requirements_by_owner: dict[str, list[str]] = {}
        for owner, manifest_data in result.all():
            if not manifest_data or not isinstance(manifest_data, dict):
                continue
            deps = manifest_data.get("dependencies") or {}
            raw_python = deps.get("python") if isinstance(deps, dict) else None
            if isinstance(raw_python, list) and raw_python:
                requirements_by_owner[owner] = [
                    str(item).strip() for item in raw_python if str(item or "").strip()
                ]
        return requirements_by_owner

    async def _ensure_python_dependency_preflight(
        self,
        plugin_name: str,
        requirements: list[str],
    ) -> dict[str, object]:
        """Preflight direct Python dependency conflicts in shared host env.
        / 对共享宿主环境做 Python 直接依赖冲突预检。
        """
        normalized_requirements = [
            str(requirement).strip()
            for requirement in requirements
            if str(requirement or "").strip()
        ]
        effective_requirements = iter_effective_python_requirements(
            normalized_requirements
        )

        requirement_groups: dict[str, list[tuple[str, str]]] = {}

        for requirement_text in self._load_project_pyproject_requirements():
            for requirement in iter_effective_python_requirements([requirement_text]):
                package = normalize_python_package_name(requirement.name)
                requirement_groups.setdefault(package, []).append(
                    ("host", str(requirement))
                )

        other_plugin_requirements = await self._load_other_plugin_python_requirements(
            exclude_plugin_name=plugin_name,
        )
        for owner, owner_requirements in other_plugin_requirements.items():
            for requirement in iter_effective_python_requirements(owner_requirements):
                package = normalize_python_package_name(requirement.name)
                requirement_groups.setdefault(package, []).append(
                    (f"plugin:{owner}", str(requirement))
                )

        for requirement in effective_requirements:
            package = normalize_python_package_name(requirement.name)
            requirement_groups.setdefault(package, []).append(
                (f"plugin:{plugin_name}", str(requirement))
            )

        installed_versions = {
            package: get_installed_distribution_version(package)
            for package in requirement_groups
        }
        conflicts = detect_direct_python_dependency_conflicts(
            requirement_groups,
            installed_versions=installed_versions,
        )
        if conflicts:
            details = "; ".join(
                f"{conflict.package}: {conflict.reason}" for conflict in conflicts
            )
            raise PluginDependencyError(
                message=(
                    f"Python dependency conflict for plugin '{plugin_name}': {details}"
                ),
            )

        return {
            "declared": [str(requirement) for requirement in effective_requirements],
            "conflicts": [],
            "installed_versions": installed_versions,
        }

    # ================================================================
    # install / 安装
    # ================================================================

    async def _check_storage_driver_in_use(
        self, plugin_name: str, manifest_data: dict, *, force: bool = False
    ) -> None:
        """
        检查该插件提供的存储驱动是否正在被使用 / Check if this plugin provides storage drivers that are currently in use.

        Queries platform_storage_driver and all tenant tenant_storage_driver configs.
        If any reference a driver code from this plugin, block the disable.
        """
        extensions = manifest_data.get("extensions", {})
        storage_drivers = extensions.get("storage_drivers", [])
        if not storage_drivers:
            return

        driver_codes = {sd.get("code") for sd in storage_drivers if sd.get("code")}
        if not driver_codes:
            return

        from app.configs.service import ConfigService

        config_service = ConfigService(self._db)

        # Check platform storage driver / 检查平台存储驱动
        platform_driver = await config_service.get_platform_config(
            "platform_storage_driver", default="local"
        )
        if str(platform_driver) in driver_codes:
            if not force:
                raise PluginError(
                    message=(
                        f"Cannot disable '{plugin_name}': storage driver "
                        f"'{platform_driver}' is used as platform storage driver. "
                        f"Switch to another driver first."
                    ),
                )
            logger.warning(
                "Force-disabling '{}': switching platform storage driver from '{}' to 'local'",
                plugin_name,
                platform_driver,
            )
            await config_service.set_platform_config("platform_storage_driver", "local")

        # Check tenant storage drivers — batch query to avoid N+1 / 检查企业存储驱动（批量查询避免 N+1）
        from sqlalchemy import and_, select

        from app.models.system.config import SystemConfig, SystemConfigValue

        # Batch fetch: query tenant_storage_driver and tenant_storage_mode configs in one go
        # Use IN (subquery) on config_id to avoid N+1 per-tenant queries
        # / 批量获取：一次查出 tenant_storage_driver 和 tenant_storage_mode 两张配置表
        # 用 IN (subquery) 关联 config_id，避免 N+1 per-tenant 查询
        config_ids_result = await self._db.execute(
            select(SystemConfig.id, SystemConfig.key).where(
                SystemConfig.key.in_(["tenant_storage_driver", "tenant_storage_mode"]),
                SystemConfig.is_deleted.is_(False),
            )
        )
        config_id_map: dict[str, int] = {
            row[1]: row[0] for row in config_ids_result.all()
        }

        driver_config_id = config_id_map.get("tenant_storage_driver")
        mode_config_id = config_id_map.get("tenant_storage_mode")

        if driver_config_id:
            # Get all tenants' driver configs / 获取所有企业的驱动配置
            driver_values_result = await self._db.execute(
                select(SystemConfigValue.tenant_id, SystemConfigValue.value).where(
                    and_(
                        SystemConfigValue.config_id == driver_config_id,
                        SystemConfigValue.is_deleted.is_(False),
                    )
                )
            )
            # Get all tenants' storage mode configs (one-shot batch) / 获取所有企业的存储模式配置（一次性批量）
            mode_by_tenant: dict[int, str] = {}
            if mode_config_id:
                mode_values_result = await self._db.execute(
                    select(SystemConfigValue.tenant_id, SystemConfigValue.value).where(
                        and_(
                            SystemConfigValue.config_id == mode_config_id,
                            SystemConfigValue.is_deleted.is_(False),
                        )
                    )
                )
                for t_id, mode_raw in mode_values_result.all():
                    try:
                        mode_by_tenant[t_id] = str(
                            json.loads(mode_raw) if mode_raw else "platform"
                        )
                    except (json.JSONDecodeError, TypeError):
                        mode_by_tenant[t_id] = str(mode_raw) if mode_raw else "platform"

            for row in driver_values_result.all():
                tenant_id, raw_value = row
                if raw_value:
                    try:
                        val = json.loads(raw_value)
                    except (json.JSONDecodeError, TypeError):
                        val = raw_value
                    if str(val) in driver_codes:
                        mode = mode_by_tenant.get(tenant_id, "platform")
                        if mode in ("custom", "admin_override"):
                            if not force:
                                raise PluginError(
                                    message=(
                                        f"Cannot disable '{plugin_name}': storage driver "
                                        f"'{val}' is used by tenant {tenant_id}. "
                                        f"Switch the tenant to another driver first."
                                    ),
                                )
                            logger.warning(
                                "Force-disabling '{}': resetting tenant {} storage mode to 'platform'",
                                plugin_name,
                                tenant_id,
                            )
                            await config_service.set_tenant_config(
                                tenant_id, "tenant_storage_mode", "platform"
                            )

    async def _install_python_deps(
        self, plugin_name: str, requirements: list[str]
    ) -> list[str]:
        """Install Python dependencies into the current venv.
        / 安装 Python 依赖到当前 venv。

        First checks via importlib.metadata whether packages already satisfy version constraints;
        skips pip if satisfied to avoid network requests on every startup causing false errors on flaky networks.
        Only calls pip install when package is missing or version doesn't match.
        / 先用 importlib.metadata 检查包是否已满足版本约束；
        已满足则跳过 pip，避免每次启动都触发网络请求导致网络抖动时误报异常。
        只有在包缺失或版本不满足时才调用 pip install。

        Calls importlib.invalidate_caches() after pip install to refresh import path cache,
        ensuring newly installed packages can be imported without server restart.
        / pip 安装成功后调用 importlib.invalidate_caches() 刷新导入路径缓存，
        确保新安装的包无需重启服务器即可 import。
        """
        import importlib
        import importlib.metadata as _imeta
        import importlib.util as _iutil
        import site

        from packaging.requirements import Requirement
        from packaging.version import Version

        def _module_candidates(req_name: str, dist=None) -> list[str]:
            """根据 wheel 元数据构建 import 模块名 / Build import module names from wheel metadata."""
            _ = req_name
            names: list[str] = []

            # Preferred source: top_level.txt from wheel metadata / 优先来源：wheel 元数据中的 top_level.txt
            if dist is not None:
                with suppress(Exception):
                    top_level = dist.read_text("top_level.txt")
                    if top_level:
                        for raw in top_level.splitlines():
                            mod = raw.strip()
                            if mod and mod.isidentifier() and mod not in names:
                                names.append(mod)

            return names

        def _has_importable_module(candidates: list[str]) -> bool | None:
            """有候选时返回 True/False，无候选时返回 None / Return True/False when candidates exist; None when no candidates."""
            if not candidates:
                return None
            for mod in candidates:
                with suppress(Exception):
                    if _iutil.find_spec(mod) is not None:
                        return True
            return False

        installed: list[str] = []
        needs_cache_refresh = False
        pip_python = self._resolve_pip_python_executable()
        pip_env = self._build_python_install_env(plugin_name)
        await self._ensure_python_dependency_preflight(plugin_name, requirements)

        for req in requirements:
            normalized_req = req.strip()
            try:
                req_obj = Requirement(normalized_req)
            except Exception as exc:
                raise PluginDependencyError(
                    message=resolve_public_error_message(
                        exc,
                        fallback_message=_("plugin.error.dependency_failed"),
                    ),
                ) from exc

            if req_obj.url:
                raise PluginDependencyError(
                    message=(
                        f"Direct URL requirement is not allowed for plugin '{plugin_name}': "
                        f"{normalized_req}"
                    ),
                )
            marker_text = str(req_obj.marker) if req_obj.marker else ""
            if marker_text and any(
                ch in marker_text for ch in [";", "&", "|", "`", "$", "\n", "\r"]
            ):
                # Reject markers containing shell metacharacters to prevent log/command parameter pollution
                # / 拒绝包含 shell 元字符的 marker，防止极端情况下拼接污染日志/命令参数
                raise PluginDependencyError(
                    message=(
                        f"Invalid environment marker in requirement '{normalized_req}'"
                    ),
                )
            if req_obj.marker and not req_obj.marker.evaluate():
                logger.debug(
                    "Skipping requirement for {} due environment marker mismatch: {}",
                    plugin_name,
                    normalized_req,
                )
                continue

            # ── Check if version constraint is already satisfied, skip pip if so ──
            # / ── 检查是否已满足版本约束，满足则跳过 pip ──
            force_reinstall = False
            import_candidates = _module_candidates(req_obj.name)
            try:
                dist = _imeta.distribution(req_obj.name)
                import_candidates = _module_candidates(req_obj.name, dist)
                metadata_text = None
                with suppress(Exception):
                    metadata_text = dist.read_text("METADATA")
                if not metadata_text:
                    # Defense: cancelled/interrupted install may leave corrupted dist-info with only INSTALLER/REQUESTED
                    # / 防御：取消/中断安装可能留下仅含 INSTALLER/REQUESTED 的残缺 dist-info
                    force_reinstall = True
                    logger.warning(
                        "Plugin {}: package {} metadata is corrupted, forcing reinstall",
                        plugin_name,
                        req_obj.name,
                    )

                installed_version = getattr(dist, "version", None)
                if installed_version:
                    try:
                        if (
                            not req_obj.specifier
                            or Version(installed_version) in req_obj.specifier
                        ):
                            importable = _has_importable_module(import_candidates)
                            if importable is False:
                                force_reinstall = True
                                logger.warning(
                                    "Plugin {}: package {} is installed ({}) but import path is missing, forcing reinstall",
                                    plugin_name,
                                    req_obj.name,
                                    installed_version,
                                )
                            elif not force_reinstall:
                                logger.debug(
                                    "Skipping pip install for {}: already satisfied ({}=={})",
                                    plugin_name,
                                    req_obj.name,
                                    installed_version,
                                )
                                continue
                    except Exception as exc:
                        # Some abnormal dist metadata may return invalid version; fallback to reinstall to avoid 500
                        # / 某些异常分发元数据可能返回非法 version；回退到重装，避免 500
                        force_reinstall = True
                        logger.warning(
                            "Plugin {}: invalid installed version for {} ({!r}), reinstalling: {}",
                            plugin_name,
                            req_obj.name,
                            installed_version,
                            exc,
                        )
                else:
                    force_reinstall = True
                    logger.debug(
                        "Plugin {}: installed package {} has no version metadata, reinstalling",
                        plugin_name,
                        req_obj.name,
                    )
            except _imeta.PackageNotFoundError:
                pass  # 包不存在，继续走 pip install

            install_args = [
                pip_python,
                "-m",
                "pip",
                "install",
                normalized_req,
                "--quiet",
            ]
            if force_reinstall:
                install_args.extend(["--upgrade", "--force-reinstall"])

            result = await run_subprocess_async(
                *install_args,
                timeout=180,
                shell=False,
                env=pip_env,
            )
            if result.returncode != 0:
                raise PluginDependencyError(
                    message=f"Failed to install {normalized_req}: {result.stderr.strip()}",
                )

            # Post-install conservative verification: only strongly verify importability when metadata provides top_level, to avoid false positives from distribution/import name mismatch (e.g. Pillow -> PIL) / 安装后保守校验：仅当元数据提供 top_level 时强校验可导入性，避免分发名与导入名不一致的误报
            # / 安装后做一次保守校验：仅当 metadata 能提供 top_level 时才强校验 importability，
            # 避免因发行名/导入名不一致导致误报（如 Pillow -> PIL）。
            post_top_level = ""
            try:
                post_dist = _imeta.distribution(req_obj.name)
                post_top_level = post_dist.read_text("top_level.txt") or ""
            except Exception:
                post_dist = None
            if post_dist is not None and post_top_level.strip():
                post_candidates = _module_candidates(req_obj.name, post_dist)
                post_importable = _has_importable_module(post_candidates)
                if post_importable is False:
                    raise PluginDependencyError(
                        message=(
                            f"Installed {normalized_req}, but runtime import check failed "
                            f"(candidates: {', '.join(post_candidates)})"
                        ),
                    )

            installed.append(normalized_req)
            needs_cache_refresh = True
            logger.info("Installed {} for plugin {}", normalized_req, plugin_name)

        if needs_cache_refresh:
            # Ensure newly installed packages are immediately importable (no restart needed), refresh sys.path and importlib cache / 确保新安装的包立即可导入（无需重启），刷新 sys.path 与 importlib 缓存
            for sp in site.getsitepackages():
                if sp not in sys.path:
                    sys.path.insert(0, sp)
            importlib.invalidate_caches()
            logger.debug(
                "Import caches refreshed after pip install for plugin {}", plugin_name
            )

        return installed

    def _resolve_pip_python_executable(self) -> str:
        """
        解析用于 pip 操作的 Python 解释器 / Resolve the Python executable used for pip operations.

        Why:
        - In some Windows starts, uvicorn may run as:
          `python.exe <project>/.venv/Scripts/uvicorn.exe ...`
          where `sys.executable` points to global Python, but runtime packages are
          imported from project `.venv/Lib/site-packages`.
        - If pip uses the wrong interpreter, dependencies appear "installed"
          while runtime `import` still fails.
        """
        import site

        py_rel = Path("Scripts/python.exe" if _IS_WINDOWS else "bin/python")
        candidates: list[Path] = []

        # 1) Active virtual env declared by environment. / 环境变量声明的活动虚拟环境
        venv = os.environ.get("VIRTUAL_ENV")
        if venv:
            candidates.append(Path(venv) / py_rel)

        # 2) Project-local .venv (backend/.venv). / 项目内 .venv
        candidates.append((PLUGINS_DIR.parent / ".venv") / py_rel)

        # 3) Derive venv root from runtime site-packages paths. / 由 site-packages 反推 venv 根
        path_sources: list[str] = []
        with suppress(Exception):
            path_sources.extend(site.getsitepackages())
        path_sources.extend(
            str(p) for p in sys.path if "site-packages" in str(p).lower()
        )

        for raw in path_sources:
            try:
                sp = Path(raw)
                if (
                    sp.name.lower() == "site-packages"
                    and sp.parent.name.lower() == "lib"
                ):
                    candidates.append(sp.parent.parent / py_rel)
            except Exception:
                continue

        # Keep order, drop duplicates/non-existing. / 保序去重并跳过不存在路径
        seen: set[str] = set()
        existing: list[Path] = []
        for cand in candidates:
            key = os.path.normcase(str(cand))
            if key in seen:
                continue
            seen.add(key)
            if cand.is_file():
                existing.append(cand)

        if existing:
            chosen = str(existing[0])
            if os.path.normcase(chosen) != os.path.normcase(sys.executable):
                logger.info(
                    "Plugin lifecycle pip interpreter switched: runtime={} pip={}",
                    sys.executable,
                    chosen,
                )
            return chosen

        return sys.executable

    def _build_python_install_env(self, plugin_name: str) -> dict[str, str]:
        """
        构建 pip 子进程环境（Windows 下补全 Cargo PATH）/ Build pip subprocess env with a resilient Cargo PATH on Windows.

        Some Rust-backed packages (e.g. y-py) run build backends that require `cargo`
        to be resolvable in the current process PATH. Rust may be installed, but PATH
        not refreshed in this uvicorn process. We prepend discovered cargo dirs.
        """
        env = os.environ.copy()
        current_path = env.get("PATH", "")

        # Fast path: already available. / 快速路径：已可用则直接返回
        if shutil.which("cargo", path=current_path):
            return env

        cargo_bin_name = "cargo.exe" if _IS_WINDOWS else "cargo"
        candidate_dirs: list[Path] = []

        # 1) Standard rustup/cargo home / 标准 rustup 安装目录
        home_cargo_bin = Path.home() / ".cargo" / "bin"
        candidate_dirs.append(home_cargo_bin)

        cargo_home = env.get("CARGO_HOME")
        if cargo_home:
            candidate_dirs.append(Path(cargo_home) / "bin")

        # 2) Some build tools (maturin/puccinialin) bootstrap rustup into cache dirs. / 部分构建工具把 rustup 装到缓存目录
        local_app_data = env.get("LOCALAPPDATA")
        if local_app_data:
            cache_root = Path(local_app_data) / "puccinialin" / "puccinialin" / "Cache"
            if cache_root.is_dir():
                with suppress(Exception):
                    for cargo_path in cache_root.rglob(cargo_bin_name):
                        candidate_dirs.append(cargo_path.parent)

        # Keep only existing dirs containing cargo binary, and de-duplicate / 仅保留含 cargo 二进制且存在的目录，并去重
        resolved_dirs: list[str] = []
        seen: set[str] = set()
        for p in candidate_dirs:
            cargo_path = p / cargo_bin_name
            if not cargo_path.exists():
                continue
            p_str = str(p)
            if p_str in seen:
                continue
            seen.add(p_str)
            resolved_dirs.append(p_str)

        if not resolved_dirs:
            logger.warning(
                "Plugin {}: cargo not found on PATH and no fallback cargo dir discovered",
                plugin_name,
            )
            return env

        env["PATH"] = os.pathsep.join(
            [*resolved_dirs, current_path] if current_path else resolved_dirs
        )
        logger.info(
            "Plugin {}: prepended {} Cargo PATH candidate(s) for pip install",
            plugin_name,
            len(resolved_dirs),
        )
        return env

    @staticmethod
    def _normalize_pkg_name(raw: str) -> str:
        """将 pip requirement 字符串规范化为小写包名 / Normalize a pip requirement string to a lowercase package name.

        Handles version specifiers (>=, ==, <, >, !=, ~=) and PEP 503 name normalization
        (hyphens, underscores, dots → unified lowercase).
        """
        import re

        pkg = re.split(r"[><=!~;@\[]", raw, maxsplit=1)[0].strip()
        return re.sub(r"[-_.]+", "-", pkg).lower()

    def _load_project_pyproject_dependencies(self) -> set[str]:
        """从主项目 pyproject.toml 加载包名（dependencies + optional-dependencies 各组）。"""
        protected: set[str] = set()
        pyproject_path = PLUGINS_DIR.parent / "pyproject.toml"
        if not pyproject_path.is_file():
            return protected
        try:
            raw = pyproject_path.read_bytes()
            if sys.version_info >= (3, 11):
                import tomllib

                cfg = tomllib.loads(raw.decode(encoding="utf-8"))
            else:
                import tomli

                cfg = tomli.loads(raw.decode(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to parse pyproject.toml: {}", exc)
            return protected

        project_cfg = cfg.get("project") or {}
        for item in project_cfg.get("dependencies") or []:
            if isinstance(item, str):
                protected.add(self._normalize_pkg_name(item))
        optional = project_cfg.get("optional-dependencies") or {}
        for deps in optional.values():
            if not isinstance(deps, list):
                continue
            for item in deps:
                if isinstance(item, str):
                    protected.add(self._normalize_pkg_name(item))
        return protected

    async def _uninstall_python_deps(
        self, plugin_name: str, packages: list[str]
    ) -> None:
        """Uninstall plugin-exclusive Python dependencies (3-layer safety check).
        / 卸载插件独占的 Python 依赖（三层安全检查）

        Safety policy (keep if any check hits):
        1. Other installed plugins' installed_packages declare the same package
        2. Main project pyproject.toml declares the same package
        3. pip show Required-by is non-empty (other packages reverse-depend on it)
        / 安全策略（任一命中则保留不删）：
        1. 其他已安装插件的 installed_packages 中声明了同名包
        2. 主项目 pyproject.toml（dependencies 与 optional-dependencies）中声明了同名包
        3. pip show 的 Required-by 非空（有其他包反向依赖它）
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel

        # Layer 1: Collect other plugins' dependencies / 收集其他插件的依赖
        result = await self._db.execute(
            select(PluginModel.installed_packages).where(
                PluginModel.name != plugin_name,
                PluginModel.is_deleted.is_(False),
            )
        )
        other_plugin_deps: set[str] = set()
        for row in result.scalars():
            if row:
                for req in row:
                    other_plugin_deps.add(self._normalize_pkg_name(req))

        # Layer 2: Main project pyproject.toml protection list / 主项目 pyproject.toml 保护名单
        project_deps = self._load_project_pyproject_dependencies()
        pip_python = self._resolve_pip_python_executable()

        for req in packages:
            pkg = self._normalize_pkg_name(req)
            if not pkg:
                continue

            # Check 1: other plugin needs it / 检查 1：其他插件需要
            if pkg in other_plugin_deps:
                logger.info("Kept {} (still needed by other plugins)", pkg)
                continue

            # Check 2: main project needs it / 检查 2：主项目需要
            if pkg in project_deps:
                logger.info("Kept {} (declared in project pyproject.toml)", pkg)
                continue

            # Check 3: pip reverse dependency check / 检查 3：pip 反向依赖检查
            try:
                pip_result = await run_subprocess_async(
                    pip_python,
                    "-m",
                    "pip",
                    "show",
                    pkg,
                    timeout=30,
                    shell=False,
                )
                if pip_result.returncode == 0:
                    for line in pip_result.stdout.splitlines():
                        if line.startswith("Required-by:"):
                            required_by = line.split(":", 1)[1].strip()
                            if required_by:
                                logger.info(
                                    "Kept {} (Required-by: {})",
                                    pkg,
                                    required_by,
                                )
                                break
                    else:
                        # No Required-by found or empty → safe to remove / 无 Required-by 或为空 → 可安全移除
                        await run_subprocess_async(
                            pip_python,
                            "-m",
                            "pip",
                            "uninstall",
                            pkg,
                            "-y",
                            "--quiet",
                            timeout=60,
                            shell=False,
                        )
                        logger.info("Uninstalled {} (no longer needed)", pkg)
                else:
                    logger.info("Package {} not installed, skipping", pkg)
            except Exception as exc:
                logger.warning("Failed to check/uninstall {}: {}", pkg, exc)
