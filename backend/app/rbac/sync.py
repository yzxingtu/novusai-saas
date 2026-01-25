"""
权限同步服务

应用启动时调用，将装饰器定义的权限同步到数据库

同步策略:
- 新权限（代码有，DB 无）: 创建
- 已存在（代码有，DB 有）: 更新所有字段（name, icon, path, parent_id 等）
- 代码删除（代码无，DB 有）: 禁用（is_enabled=False），不物理删除

父子关系处理:
- 使用拓扑排序确保父级先于子级处理
- 支持菜单层级变更（移动到不同父级）
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import LoggerMixin
from app.models.auth.permission import Permission
from app.rbac.decorators import PermissionMeta
from app.rbac.registry import permission_registry


class PermissionSyncService(LoggerMixin):
    """
    权限同步服务
    
    应用启动时调用，将装饰器/菜单定义文件中的权限同步到数据库
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def _topological_sort(self, permissions: list[PermissionMeta]) -> list[PermissionMeta]:
        """
        拓扑排序，确保父级权限先于子级处理
        
        Args:
            permissions: 权限列表
        
        Returns:
            排序后的权限列表
        """
        code_to_perm = {p.code: p for p in permissions}
        depth_cache: dict[str, int] = {}
        
        # 计算每个权限的深度（到根的距离），带缓存
        def get_depth(perm: PermissionMeta, visited: set[str] | None = None) -> int:
            if perm.code in depth_cache:
                return depth_cache[perm.code]
            
            if visited is None:
                visited = set()
            if perm.code in visited:
                # 循环引用，返回 0 避免无限递归
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
        
        # 按深度排序，深度小的（父级）先处理
        return sorted(permissions, key=lambda p: get_depth(p))
    
    def _make_key(self, code: str, scope: str) -> str:
        """生成权限唯一标识（code + scope）"""
        return f"{code}:{scope}"
    
    async def sync_permissions(self) -> dict[str, int]:
        """
        同步权限到数据库
        
        使用 (code, scope) 组合作为唯一标识，因为同一个 code 在不同 scope 下是不同权限。
        
        Returns:
            {"created": n, "updated": n, "disabled": n}
        """
        registered_permissions = permission_registry.get_all()
        # 使用 code:scope 作为唯一标识
        registered_keys = {
            self._make_key(p.code, p.scope.value) for p in registered_permissions
        }
        # 获取数据库中现有权限
        result = await self.db.execute(select(Permission))
        existing_permissions = result.scalars().all()
        # 使用 code:scope 作为唯一标识
        existing_keys = {
            self._make_key(p.code, p.scope): p for p in existing_permissions
        }
        existing_map = existing_keys  # key -> Permission
        
        created_count = 0
        updated_count = 0
        disabled_count = 0
        
        # (code, scope) -> db_id 映射（用于父子关联）
        # 注意：parent_code 不含 scope，需要根据同 scope 查找
        code_scope_to_id: dict[str, int] = {
            self._make_key(p.code, p.scope): p.id for p in existing_permissions
        }
        
        # 拓扑排序，确保父级先于子级处理
        sorted_permissions = self._topological_sort(registered_permissions)
        
        for perm_meta in sorted_permissions:
            perm_key = self._make_key(perm_meta.code, perm_meta.scope.value)
            
            # 解析父级 ID（父级 code 与当前权限同 scope）
            parent_id = None
            if perm_meta.parent_code:
                parent_key = self._make_key(perm_meta.parent_code, perm_meta.scope.value)
                parent_id = code_scope_to_id.get(parent_key)
                if parent_id is None:
                    self.logger.warning(
                        f"权限 {perm_meta.code} ({perm_meta.scope.value}) 的父级 {perm_meta.parent_code} 不存在"
                    )
            
            if perm_key in existing_map:
                # 更新已存在的权限
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
                # 始终更新 parent_id（支持菜单移动）
                db_perm.parent_id = parent_id
                
                updated_count += 1
            else:
                # 创建新权限
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
                await self.db.flush()  # 获取 ID
                code_scope_to_id[perm_key] = db_perm.id
                created_count += 1
        
        # 禁用代码中已删除的权限
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
        
        return {
            "created": created_count,
            "updated": updated_count,
            "disabled": disabled_count,
        }


async def sync_permissions_on_startup(db: AsyncSession) -> dict[str, int]:
    """
    启动时同步权限
    
    Args:
        db: 数据库会话
    
    Returns:
        同步结果统计
    """
    sync_service = PermissionSyncService(db)
    return await sync_service.sync_permissions()


__all__ = [
    "PermissionSyncService",
    "sync_permissions_on_startup",
]
