"""
角色/组织架构枚举模块 / Role/Organization Enum Module

定义组织架构节点类型
Defines organization structure node types.
"""

from app.enums.base import StrEnum


class RoleType(StrEnum):
    """
    Organization Node Type Enum / 组织架构节点类型枚举

    - DEPARTMENT: Department / 部门 - can add sub-depts/positions, members, leaders / 可添加子部门/岗位，成员，负责人
    - POSITION: Position / 岗位 - no children, can add members / 不可添加子节点，可添加成员
    - ROLE: Functional Role / 职能角色 - can add sub-roles, members (default, backward compat) / 可添加子角色，成员（默认类型）
    """

    DEPARTMENT = ("department", "enum.role_type.department")
    POSITION = ("position", "enum.role_type.position")
    ROLE = ("role", "enum.role_type.role")


__all__ = [
    "RoleType",
]
