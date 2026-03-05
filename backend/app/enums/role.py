"""
角色/组织架构枚举模块

定义组织架构节点类型
"""

from app.enums.base import StrEnum


class RoleType(StrEnum):
    """
    组织架构节点类型枚举

    - DEPARTMENT: 部门 - 可添加子部门/岗位，可添加成员，可设置负责人
    - POSITION: 岗位 - 不可添加子节点，可添加成员
    - ROLE: 职能角色 - 可添加子角色，可添加成员（默认类型，兼容现有数据）
    """

    DEPARTMENT = ("department", "enum.role_type.department")
    POSITION = ("position", "enum.role_type.position")
    ROLE = ("role", "enum.role_type.role")


__all__ = [
    "RoleType",
]
