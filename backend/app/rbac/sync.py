"""
Permission Sync Service
权限同步服务

Syncs permissions defined by decorators + menu definitions to database, executed on app startup.
将装饰器定义的权限 + 菜单定义同步到数据库，应用启动时执行。

Sync strategy / 同步策略:
- New permission (in code, not in DB): create / 新权限（代码有，DB 无）: 创建
- Existing (in code and DB): update all fields (name, icon, path, parent_id etc.) / 已存在（代码有，DB 有）: 更新所有字段
- Removed from code (not in code, in DB): disable (is_enabled=False), no physical delete / 代码删除（代码无，DB 有）: 禁用，不物理删除

Parent-child relationship handling / 父子关系处理:
- Uses topological sort to ensure parents processed before children / 使用拓扑排序确保父级先于子级处理
- Supports menu hierarchy changes (moving to different parent) / 支持菜单层级变更（移动到不同父级）
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LoggerMixin
from app.enums.rbac import PermissionType
from app.models.auth.permission import Permission
from app.rbac.decorators import PermissionMeta
from app.rbac.registry import permission_registry


class PermissionSyncService(LoggerMixin):
    """
    Permission Sync Service.
    权限同步服务。

    Syncs permissions defined by decorators + menu definitions to database.
    将装饰器定义的权限 + 菜单定义同步到数据库。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def _topological_sort(self, permissions: list[PermissionMeta]) -> list[PermissionMeta]:
        """
        Topological sort, ensures parent permissions processed before children.
        拓扑排序，确保父级权限先于子级处理。

        Args:
            permissions: Permission list / 权限列表

        Returns:
            Sorted permission list / 排序后的权限列表
        """
        code_to_perm = {p.code: p for p in permissions}
        depth_cache: dict[str, int] = {}

        # Calculate depth of each permission (distance to root), with cache / 计算每个权限的深度（到根的距离），带缓存
        def get_depth(perm: PermissionMeta, visited: set[str] | None = None) -> int:
            if perm.code in depth_cache:
                return depth_cache[perm.code]

            if visited is None:
                visited = set()
            if perm.code in visited:
                # Circular reference, return 0 to avoid infinite recursion / 循环引用，返回 0 避免无限递归
                return 0
            visited.add(perm.code)

            if not perm.parent_code:
                depth_cache[perm.code] = 0
                return 0
            parent = code_to_perm.get(perm.parent_code)
            if not parent:
                depth_cache[perm.code] = 0
                return 0
            depth = 1 + get_depth(parent, visited)
            depth_cache[perm.code] = depth
            return depth

        # Sort by depth, lower depth (parents) processed first / 按深度排序，深度小的（父级）先处理
        return sorted(permissions, key=lambda p: get_depth(p))

    def _make_key(self, code: str, scope: str) -> str:
        """Generate permission unique key (code + scope) / 生成权限唯一标识（code + scope）"""
        return f"{code}:{scope}"

    async def sync_permissions(self) -> dict[str, int]:
        """
        Sync permissions to database.
        同步权限到数据库。

        Uses (code, scope) combination as unique identifier, since same code under different scopes are different permissions.
        使用 (code, scope) 组合作为唯一标识，因为同一个 code 在不同 scope 下是不同权限。

        Returns:
            Sync statistics / 同步结果统计: {created: N, updated: N, disabled: N}
        """
        registered_permissions = permission_registry.get_all()
        # Use code:scope as unique identifier / 使用 code:scope 作为唯一标识
        registered_keys = {
            self._make_key(p.code, p.scope.value) for p in registered_permissions
        }
        # Get existing permissions from DB / 获取数据库中现有权限
        result = await self.db.execute(select(Permission))
        existing_permissions = result.scalars().all()
        # Use code:scope as unique identifier / 使用 code:scope 作为唯一标识
        existing_keys = {
            self._make_key(p.code, p.scope): p for p in existing_permissions
        }
        existing_map = existing_keys  # key -> Permission

        created_count = 0
        updated_count = 0
        disabled_count = 0

        # (code, scope) -> db_id mapping (for parent-child association, exact match) / 映射（用于父子关联，精确匹配）
        # Note: parent_code has no scope, needs same-scope lookup / 注意：parent_code 不含 scope，需要根据同 scope 查找
        code_scope_to_id: dict[str, int] = {
            self._make_key(p.code, p.scope): p.id for p in existing_permissions
        }
        # code-only fallback mapping: when parent scope differs from child (e.g. plugin tenant menu mounted to system menu) / 回退映射：当父级 scope 与子级不同时避免误报
        code_to_id: dict[str, int] = {
            p.code: p.id for p in existing_permissions
        }

        # Topological sort, ensure parents processed before children / 拓扑排序，确保父级先于子级处理
        sorted_permissions = self._topological_sort(registered_permissions)

        for perm_meta in sorted_permissions:
            perm_key = self._make_key(perm_meta.code, perm_meta.scope.value)

            # Resolve parent ID / 解析父级 ID
            # 1) First try code+scope exact match (same-scope parent-child) / 先按 code+scope 精确匹配
            # 2) Fallback to code-only match (plugin menu mounted to system menu, scope may differ) / 回退到 code-only 匹配
            parent_id = None
            if perm_meta.parent_code:
                parent_key = self._make_key(perm_meta.parent_code, perm_meta.scope.value)
                parent_id = code_scope_to_id.get(parent_key) or code_to_id.get(perm_meta.parent_code)
                if parent_id is None:
                    self.logger.warning(
                        f"权限 {perm_meta.code} ({perm_meta.scope.value}) 的父级 {perm_meta.parent_code} 不存在"
                    )

            if perm_key in existing_map:
                # Update existing permission / 更新已存在的权限
                db_perm = existing_map[perm_key]
                db_perm.name = perm_meta.name
                db_perm.description = perm_meta.description
                db_perm.type = perm_meta.type.value
                db_perm.scope = perm_meta.scope.value
                db_perm.resource = perm_meta.resource
                db_perm.action = perm_meta.action
                db_perm.icon = perm_meta.icon
                db_perm.path = perm_meta.path
                db_perm.component = perm_meta.component
                db_perm.sort_order = perm_meta.sort_order
                db_perm.hidden = perm_meta.hidden
                db_perm.is_enabled = True
                # Always update parent_id (supports menu moving) / 始终更新 parent_id（支持菜单移动）
                db_perm.parent_id = parent_id

                updated_count += 1
            else:
                # Create new permission / 创建新权限
                db_perm = Permission(
                    code=perm_meta.code,
                    name=perm_meta.name,
                    description=perm_meta.description,
                    type=perm_meta.type.value,
                    scope=perm_meta.scope.value,
                    resource=perm_meta.resource,
                    action=perm_meta.action,
                    parent_id=parent_id,
                    sort_order=perm_meta.sort_order,
                    icon=perm_meta.icon,
                    path=perm_meta.path,
                    component=perm_meta.component,
                    hidden=perm_meta.hidden,
                    is_enabled=True,
                )
                self.db.add(db_perm)
                await self.db.flush()  # Get ID / 获取 ID
                code_scope_to_id[perm_key] = db_perm.id
                code_to_id[perm_meta.code] = db_perm.id
                created_count += 1

        # Disable permissions removed from code / 禁用代码中已删除的权限
        orphan_keys = set(existing_map.keys()) - registered_keys
        for key in orphan_keys:
            db_perm = existing_map[key]
            if db_perm.is_enabled:
                db_perm.is_enabled = False
                disabled_count += 1
                self.logger.debug(f"禁用权限: {key}")

        await self.db.commit()

        self.logger.info(
            f"权限同步完成: 新增 {created_count}, 更新 {updated_count}, 禁用 {disabled_count}"
        )

        self._validate_menu_components(registered_permissions)

        return {
            "created": created_count,
            "updated": updated_count,
            "disabled": disabled_count,
        }


    def _validate_menu_components(self, permissions: list[PermissionMeta]) -> None:
        """
        Validate menu component paths for common issues.
        校验菜单组件路径是否存在常见错误。

        Runs after sync_permissions, logs warnings only (never blocks startup).
        在 sync_permissions 后运行，只记录警告，不会阻断启动。
        """
        menus = [p for p in permissions if p.type == PermissionType.MENU and p.component]
        issues: list[str] = []

        for menu in menus:
            if menu.component.endswith(".vue"):
                issues.append(
                    f"  {menu.code}: component 不应包含 .vue 后缀 -> '{menu.component}'"
                )
            if menu.parent_code and menu.parent_code not in permission_registry:
                issues.append(
                    f"  {menu.code}: parent_code '{menu.parent_code}' 未在 registry 中注册"
                )

        if issues:
            self.logger.warning(
                "菜单组件路径校验发现 %d 个问题:\n%s",
                len(issues),
                "\n".join(issues),
            )

    async def sync_plugin_permissions(self, plugin_name: str) -> int:
        """
        Sync only specified plugin's menu permissions (flush, no commit, no orphan handling).
        仅同步指定插件的菜单权限（flush，不 commit，不处理孤儿权限）。

        Used during plugin enable flow, avoids sync_permissions()'s commit breaking outer transaction atomicity.
        Only processes registered plugin permissions (create/update), won't disable any existing permissions.
        用于插件 enable 流程中途调用，避免 sync_permissions() 的 commit 破坏外层事务原子性。
        只处理代码中已注册的该插件权限，不会禁用任何现有权限。

        Args:
            plugin_name: Plugin name (for prefix filtering, e.g. "my-plugin") / 插件名称（用于前缀过滤）

        Returns:
            Number of permissions created or updated / 创建或更新的权限数量
        """
        safe_name = plugin_name.replace("-", "_")
        prefix_admin = f"menu:admin.plugin_{safe_name}_"
        prefix_tenant = f"menu:tenant.plugin_{safe_name}_"

        # Only process permissions belonging to this plugin / 只处理属于此插件的权限
        plugin_perms = [
            p for p in permission_registry.get_all()
            if p.code.startswith(prefix_admin) or p.code.startswith(prefix_tenant)
        ]
        if not plugin_perms:
            return 0

        # Query existing plugin permissions (including is_deleted) / 查询已有的插件权限（含 is_deleted）
        result = await self.db.execute(
            select(Permission).where(
                (Permission.code.startswith(prefix_admin, autoescape=True))
                | (Permission.code.startswith(prefix_tenant, autoescape=True))
            )
        )
        existing_db: dict[str, Permission] = {
            self._make_key(p.code, p.scope): p
            for p in result.scalars().all()
        }

        # Build parent ID mapping (query all existing IDs for parent association) / 构建父级 ID 映射（先查出所有已有 ID 以便关联父级）
        all_result = await self.db.execute(select(Permission.code, Permission.id))
        code_to_id: dict[str, int] = {row[0]: row[1] for row in all_result.all()}

        count = 0
        sorted_perms = self._topological_sort(plugin_perms)
        for perm_meta in sorted_perms:
            perm_key = self._make_key(perm_meta.code, perm_meta.scope.value)
            parent_id = None
            if perm_meta.parent_code:
                parent_id = code_to_id.get(perm_meta.parent_code)

            if perm_key in existing_db:
                db_perm = existing_db[perm_key]
                db_perm.name = perm_meta.name
                db_perm.type = perm_meta.type.value
                db_perm.scope = perm_meta.scope.value
                db_perm.resource = perm_meta.resource
                db_perm.action = perm_meta.action
                db_perm.icon = perm_meta.icon
                db_perm.path = perm_meta.path
                db_perm.component = perm_meta.component
                db_perm.sort_order = perm_meta.sort_order
                db_perm.hidden = perm_meta.hidden
                db_perm.is_enabled = True
                db_perm.is_deleted = False
                db_perm.parent_id = parent_id
            else:
                db_perm = Permission(
                    code=perm_meta.code,
                    name=perm_meta.name,
                    type=perm_meta.type.value,
                    scope=perm_meta.scope.value,
                    resource=perm_meta.resource,
                    action=perm_meta.action,
                    parent_id=parent_id,
                    sort_order=perm_meta.sort_order,
                    icon=perm_meta.icon,
                    path=perm_meta.path,
                    component=perm_meta.component,
                    hidden=perm_meta.hidden,
                    is_enabled=True,
                )
                self.db.add(db_perm)
                await self.db.flush()
                code_to_id[perm_meta.code] = db_perm.id
            count += 1

        if count:
            await self.db.flush()
        return count


async def sync_permissions_on_startup(db: AsyncSession) -> dict[str, int]:
    """
    Sync permissions on startup.
    启动时同步权限。

    Args:
        db: Database session / 数据库会话

    Returns:
        Sync statistics / 同步结果统计
    """
    sync_service = PermissionSyncService(db)
    return await sync_service.sync_permissions()


__all__ = [
    "PermissionSyncService",
    "sync_permissions_on_startup",
]
