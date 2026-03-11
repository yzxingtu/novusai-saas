"""
权限相关 Schema / Permission Schema

定义权限树、菜单等响应结构
Defines permission tree, menu and other response structures.
"""

from pydantic import Field

from app.core.base_schema import BaseSchema


class PermissionResponse(BaseSchema):
    """权限响应"""

    id: int = Field(..., description="权限 ID")
    code: str = Field(..., description="权限代码")
    name: str = Field(..., description="权限名称")
    description: str | None = Field(None, description="权限描述")
    type: str = Field(..., description="权限类型: menu/operation")
    scope: str = Field(..., description="作用域: admin/tenant/both")
    resource: str = Field(..., description="资源标识")
    action: str = Field(..., description="操作标识")
    parent_id: int | None = Field(None, description="父级权限 ID")
    sort_order: int = Field(0, description="排序")
    icon: str | None = Field(None, description="图标")
    path: str | None = Field(None, description="前端路由")
    component: str | None = Field(None, description="前端组件")
    hidden: bool = Field(False, description="是否隐藏")


class PermissionTreeResponse(PermissionResponse):
    """权限树响应（含子权限）"""

    children: list["PermissionTreeResponse"] = Field(default_factory=list, description="子权限")


class MenuResponse(BaseSchema):
    """菜单响应"""

    id: int = Field(..., description="权限 ID")
    code: str = Field(..., description="权限代码")
    name: str = Field(..., description="菜单名称")
    icon: str | None = Field(None, description="图标")
    path: str | None = Field(None, description="前端路由")
    component: str | None = Field(None, description="前端组件")
    hidden: bool = Field(False, description="是否隐藏")
    sort_order: int = Field(0, description="排序")
    permissions: list[str] = Field(default_factory=list, description="该菜单下的操作权限码列表")
    children: list["MenuResponse"] = Field(default_factory=list, description="子菜单")


# 解决循环引用
PermissionTreeResponse.model_rebuild()
MenuResponse.model_rebuild()


__all__ = [
    "PermissionResponse",
    "PermissionTreeResponse",
    "MenuResponse",
]
