"""
角色/组织架构枚举模块 / Role/Organization Enum Module

定义组织架构节点类型、数据权限范围等
Defines organization node types, data scope for row-level filtering.
"""

from app.enums.base import LabeledStrEnum


class DataScope(LabeledStrEnum):
    """
    数据权限范围枚举 / Data permission scope enum

    - ALL: 全部数据（管理员） / All data (admin)
    - DEPT_AND_CHILDREN: 本部门及下级部门 / Department and children
    - DEPT_ONLY: 仅本部门 / Current department only
    - SELF_ONLY: 仅自己的数据 / Self only
    - CUSTOM: 自定义部门列表 / Custom department list
    """

    ALL = ("all", "enum.data_scope.all")
    DEPT_AND_CHILDREN = ("dept_children", "enum.data_scope.dept_children")
    DEPT_ONLY = ("dept_only", "enum.data_scope.dept_only")
    SELF_ONLY = ("self", "enum.data_scope.self")
    CUSTOM = ("custom", "enum.data_scope.custom")


class RoleType(LabeledStrEnum):
    """
    Organization Node Type Enum / 组织架构节点类型枚举

    - DEPARTMENT: Department / 部门 - can add sub-depts/positions, members, leaders / 可添加子部门/岗位，成员，负责人
    - POSITION: Position / 岗位 - no children, can add members / 不可添加子节点，可添加成员
    - ROLE: Functional Role / 职能角色 - can add sub-roles and members / 可添加子角色和成员
    """

    DEPARTMENT = ("department", "enum.role_type.department")
    POSITION = ("position", "enum.role_type.position")
    ROLE = ("role", "enum.role_type.role")


__all__ = [
    "DataScope",
    "RoleType",
]
