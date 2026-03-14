"""
用户偏好服务 / User Preference Service

分层偏好读写：系统默认 → 全局偏好 → 个人覆盖，逐层合并。
全局变更时精确清除个人覆盖中已变更的 key。
Layered preference read/write: system defaults -> global -> individual, merged layer by layer.
On global change, precisely removes changed keys from individual overrides.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LogManager
from app.models.common.user_preference import UserPreference

logger = LogManager.get_logger("app")

SCOPE_PLATFORM_GLOBAL = "platform_global"
SCOPE_TENANT_GLOBAL = "tenant_global"
SCOPE_ADMIN = "admin"
SCOPE_TENANT_ADMIN = "tenant_admin"

PLATFORM_TENANT_ID = 0

GLOBAL_SCOPES = {SCOPE_PLATFORM_GLOBAL, SCOPE_TENANT_GLOBAL}
INDIVIDUAL_SCOPES = {SCOPE_ADMIN, SCOPE_TENANT_ADMIN}

SCOPE_TO_GLOBAL = {
    SCOPE_ADMIN: SCOPE_PLATFORM_GLOBAL,
    SCOPE_TENANT_ADMIN: SCOPE_TENANT_GLOBAL,
}

SYSTEM_DEFAULTS: dict[str, Any] = {
    # ── 水印（全局专属） / Watermark (global only) ──
    "watermark_enable": False,
    "watermark_content": "{tenant_name} - {real_name}",
    # ── 外观 / Appearance ──
    "theme_mode": "dark",
    "builtin_type": "default",
    "color_primary": "hsl(212 100% 45%)",
    "radius": "0.5",
    "font_size": 16,
    "semi_dark_sidebar": False,
    "semi_dark_header": False,
    "color_weak_mode": False,
    "color_gray_mode": False,
    # ── 布局 / Layout ──
    "layout_mode": "sidebar-nav",
    "content_compact": "wide",
    # 侧栏 / Sidebar
    "sidebar_enable": True,
    "sidebar_collapsed": False,
    "sidebar_expand_on_hover": True,
    "sidebar_collapsed_show_title": False,
    "sidebar_auto_activate_child": False,
    "sidebar_width": 224,
    # 顶栏 / Header
    "header_enable": True,
    "header_mode": "fixed",
    "header_menu_align": "start",
    # 导航 / Navigation
    "navigation_style_type": "rounded",
    "navigation_split": True,
    "navigation_accordion": True,
    # 面包屑 / Breadcrumb
    "breadcrumb_enable": True,
    "breadcrumb_hide_only_one": False,
    "breadcrumb_show_icon": True,
    "breadcrumb_show_home": False,
    "breadcrumb_style_type": "normal",
    # 标签栏 / Tabbar
    "tabbar_enable": True,
    "tabbar_persist": True,
    "tabbar_max_count": 0,
    "tabbar_draggable": True,
    "tabbar_wheelable": True,
    "tabbar_middle_click_to_close": False,
    "tabbar_show_icon": True,
    "tabbar_show_more": True,
    "tabbar_show_maximize": True,
    "tabbar_style_type": "chrome",
    # 小部件 / Widget
    "widget_global_search": False,
    "widget_theme_toggle": True,
    "widget_language_toggle": True,
    "widget_fullscreen": True,
    "widget_notification": True,
    "widget_lock_screen": True,
    "widget_sidebar_toggle": True,
    "widget_refresh": True,
    # 页脚 / Footer
    "footer_enable": False,
    "footer_fixed": False,
    # ── 语言 / Language ──
    "locale": "zh-CN",
    # ── 表格 / Table ──
    "page_size": 20,
    "table_size": "default",
    # ── 日期时间 / DateTime ──
    "timezone": "Asia/Shanghai",
    "date_format": "YYYY-MM-DD",
    # ── 动画 / Animation ──
    "transition_enable": True,
    "transition_loading": True,
    "transition_progress": True,
    "transition_name": "fade-slide",
}

VALID_KEYS = set(SYSTEM_DEFAULTS.keys())

GLOBAL_ONLY_KEYS: set[str] = {"watermark_enable", "watermark_content"}


class UserPreferenceService:
    """用户偏好 CRUD 服务 / User preference CRUD service"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def get_system_defaults(self) -> dict[str, Any]:
        """返回系统默认偏好 / Return system default preferences"""
        return dict(SYSTEM_DEFAULTS)

    async def get_effective(
        self,
        scope: str,
        tenant_id: int,
        user_id: int,
    ) -> dict[str, Any]:
        """
        获取生效偏好（系统默认 + 全局 + 个人合并）
        Get effective preferences (system defaults + global + individual merged)
        """
        result = dict(SYSTEM_DEFAULTS)

        global_scope = SCOPE_TO_GLOBAL.get(scope, scope)
        global_record = await self._get_record(global_scope, tenant_id, user_id=None)
        if global_record:
            global_prefs = self._parse_json(global_record.preferences)
            result.update(global_prefs)

        if scope in INDIVIDUAL_SCOPES:
            ind_record = await self._get_record(scope, tenant_id, user_id=user_id)
            if ind_record:
                ind_prefs = self._parse_json(ind_record.preferences)
                result.update(ind_prefs)

        return result

    async def get_global(
        self,
        scope: str,
        tenant_id: int,
    ) -> dict[str, Any]:
        """
        获取全局偏好（仅全局记录，不含系统默认）
        Get global preferences (global record only, without system defaults)
        """
        record = await self._get_record(scope, tenant_id, user_id=None)
        if record:
            return self._parse_json(record.preferences)
        return {}

    async def get_global_with_defaults(
        self,
        scope: str,
        tenant_id: int,
    ) -> dict[str, Any]:
        """
        获取全局偏好（含系统默认补全）
        Get global preferences with system defaults filled in
        """
        result = dict(SYSTEM_DEFAULTS)
        record = await self._get_record(scope, tenant_id, user_id=None)
        if record:
            result.update(self._parse_json(record.preferences))
        return result

    async def get_individual(
        self,
        scope: str,
        tenant_id: int,
        user_id: int,
    ) -> dict[str, Any]:
        """
        获取个人覆盖部分（仅个人记录）
        Get individual override part only
        """
        record = await self._get_record(scope, tenant_id, user_id=user_id)
        if record:
            return self._parse_json(record.preferences)
        return {}

    async def update_global(
        self,
        scope: str,
        tenant_id: int,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        更新全局偏好 + 精确清除个人覆盖中已变更的 key
        Update global preferences + precisely clear changed keys from individual overrides

        Returns: 更新后的全局偏好 / Updated global preferences
        """
        filtered = self._filter_valid_keys(data)
        if not filtered:
            return await self.get_global_with_defaults(scope, tenant_id)

        record = await self._get_record(scope, tenant_id, user_id=None)
        old_prefs: dict[str, Any] = {}

        if record:
            old_prefs = self._parse_json(record.preferences)
        else:
            record = UserPreference(
                scope=scope,
                tenant_id=tenant_id,
                user_id=None,
                preferences="{}",
                version=0,
            )
            self.db.add(record)

        changed_keys = {k for k in filtered if filtered[k] != old_prefs.get(k)}

        new_prefs = {**old_prefs, **filtered}
        record.preferences = json.dumps(new_prefs, ensure_ascii=False)
        record.version = (record.version or 0) + 1

        if changed_keys:
            ind_scope = self._get_individual_scope(scope)
            if ind_scope:
                await self._clear_individual_keys(ind_scope, tenant_id, changed_keys)

        await self.db.flush()

        result = dict(SYSTEM_DEFAULTS)
        result.update(new_prefs)
        return result

    async def update_individual(
        self,
        scope: str,
        tenant_id: int,
        user_id: int,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        更新个人覆盖（自动排除全局专属 key）
        Update individual overrides (auto-excludes global-only keys)

        Returns: 更新后的生效偏好 / Updated effective preferences
        """
        filtered = self._filter_valid_keys(data, exclude_global_only=True)

        record = await self._get_record(scope, tenant_id, user_id=user_id)
        if record:
            current = self._parse_json(record.preferences)
            current.update(filtered)
            record.preferences = json.dumps(current, ensure_ascii=False)
        else:
            record = UserPreference(
                scope=scope,
                tenant_id=tenant_id,
                user_id=user_id,
                preferences=json.dumps(filtered, ensure_ascii=False),
                version=0,
            )
            self.db.add(record)

        await self.db.flush()
        return await self.get_effective(scope, tenant_id, user_id)

    async def reset_individual(
        self,
        scope: str,
        tenant_id: int,
        user_id: int,
    ) -> dict[str, Any]:
        """
        重置个人覆盖（恢复为全局默认）
        Reset individual overrides (restore to global defaults)

        Returns: 重置后的生效偏好 / Effective preferences after reset
        """
        record = await self._get_record(scope, tenant_id, user_id=user_id)
        if record:
            record.preferences = "{}"
            await self.db.flush()

        global_scope = SCOPE_TO_GLOBAL.get(scope, scope)
        result = dict(SYSTEM_DEFAULTS)
        global_record = await self._get_record(global_scope, tenant_id, user_id=None)
        if global_record:
            result.update(self._parse_json(global_record.preferences))
        return result

    # ── internal helpers / 内部方法 ──

    async def _get_record(
        self,
        scope: str,
        tenant_id: int,
        user_id: int | None,
    ) -> UserPreference | None:
        """查询单条偏好记录 / Query single preference record"""
        conditions = [
            UserPreference.scope == scope,
            UserPreference.tenant_id == tenant_id,
            UserPreference.is_deleted.is_(False),
        ]
        if user_id is None:
            conditions.append(UserPreference.user_id.is_(None))
        else:
            conditions.append(UserPreference.user_id == user_id)

        result = await self.db.execute(
            select(UserPreference).where(and_(*conditions))
        )
        return result.scalar_one_or_none()

    async def _clear_individual_keys(
        self,
        ind_scope: str,
        tenant_id: int,
        changed_keys: set[str],
    ) -> None:
        """
        从该层级下所有个人记录中移除已变更的 key
        Remove changed keys from all individual records under this scope
        """
        result = await self.db.execute(
            select(UserPreference).where(
                and_(
                    UserPreference.scope == ind_scope,
                    UserPreference.tenant_id == tenant_id,
                    UserPreference.user_id.isnot(None),
                    UserPreference.is_deleted.is_(False),
                )
            )
        )
        individuals = result.scalars().all()

        for ind in individuals:
            prefs = self._parse_json(ind.preferences)
            cleaned = {k: v for k, v in prefs.items() if k not in changed_keys}
            ind.preferences = json.dumps(cleaned, ensure_ascii=False)

        if individuals:
            logger.info(
                f"Cleared {len(changed_keys)} key(s) from {len(individuals)} "
                f"individual preference record(s) under scope={ind_scope}"
            )

    @staticmethod
    def _get_individual_scope(global_scope: str) -> str | None:
        """全局 scope → 对应的个人 scope / Map global scope to individual scope"""
        mapping = {
            SCOPE_PLATFORM_GLOBAL: SCOPE_ADMIN,
            SCOPE_TENANT_GLOBAL: SCOPE_TENANT_ADMIN,
        }
        return mapping.get(global_scope)

    @staticmethod
    def _filter_valid_keys(
        data: dict[str, Any],
        *,
        exclude_global_only: bool = False,
    ) -> dict[str, Any]:
        """
        过滤只保留合法的偏好 key / Filter to keep only valid preference keys
        exclude_global_only=True 时额外排除全局专属 key（水印等）
        When exclude_global_only=True, also excludes global-only keys (watermark, etc.)
        """
        result = {k: v for k, v in data.items() if k in VALID_KEYS}
        if exclude_global_only:
            result = {k: v for k, v in result.items() if k not in GLOBAL_ONLY_KEYS}
        return result

    @staticmethod
    def _parse_json(raw: str | None) -> dict[str, Any]:
        """安全解析 JSON 字符串 / Safely parse JSON string"""
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}


__all__ = [
    "UserPreferenceService",
    "SYSTEM_DEFAULTS",
    "VALID_KEYS",
    "GLOBAL_ONLY_KEYS",
    "SCOPE_PLATFORM_GLOBAL",
    "SCOPE_TENANT_GLOBAL",
    "SCOPE_ADMIN",
    "SCOPE_TENANT_ADMIN",
    "PLATFORM_TENANT_ID",
]
