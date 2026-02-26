"""
操作日志模型

记录系统中所有 API 调用的审计日志
"""


from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class OperationLog(BaseModel):
    """
    操作日志模型
    
    记录所有 API 调用的审计日志，支持：
    - 平台端操作（tenant_id 为空）
    - 租户端操作（tenant_id 不为空）
    """
    
    __tablename__ = "operation_logs"
    
    # 表级索引
    __table_args__ = (
        # 复合索引：租户 + 时间，用于租户日志查询
        Index("ix_operation_logs_tenant_created", "tenant_id", "created_at"),
        # 复合索引：用户类型 + 用户ID，用于用户操作追溯
        Index("ix_operation_logs_user", "user_type", "user_id"),
        # 复合索引：模块 + 操作，用于操作统计
        Index("ix_operation_logs_module_action", "module", "action"),
    )
    
    # 可过滤字段声明
    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "user_type": "user_type",
        "user_id": "user_id",
        "username": "username",
        "module": "module",
        "action": "action",
        "resource": "resource",
        "method": "method",
        "path": "path",
        "response_code": "response_code",
        "ip": "ip",
        "created_at": "created_at",
    }
    
    __sortable__ = ["id", "username", "module", "action", "method", "response_code", "created_at"]
    
    # ==================== 用户信息 ====================
    
    # 租户ID（平台操作时为空）
    tenant_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="租户ID（平台操作为空）"
    )
    
    # 用户类型: admin / tenant_admin / tenant_user
    user_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="用户类型"
    )
    
    # 用户ID
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="用户ID"
    )
    
    # 用户名（冗余存储，便于查询和展示）
    username: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="用户名"
    )
    
    # 用户昵称（冗余存储，便于展示）
    nickname: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="用户昵称"
    )
    
    # ==================== 操作信息 ====================
    
    # 业务模块: auth / permission / role / admin_user / tenant / config / plan / ...
    module: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="业务模块"
    )
    
    # 操作类型: create / update / delete / query / login / logout / export / import
    action: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="操作类型"
    )
    
    # 资源标识（权限代码）: admin_user:create / role:update 等
    resource: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="资源标识（权限代码）"
    )
    
    # ==================== 请求信息 ====================
    
    # HTTP 方法: GET / POST / PUT / DELETE / PATCH
    method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="HTTP 方法"
    )
    
    # 请求路径
    path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
        comment="请求路径"
    )
    
    # 查询参数（JSON 格式）
    query_params: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="查询参数"
    )
    
    # 请求体摘要（JSON 格式，已脱敏）
    request_body: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="请求体摘要（已脱敏）"
    )
    
    # ==================== 响应信息 ====================
    
    # HTTP 响应状态码
    status_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="HTTP 响应状态码"
    )
    
    # 业务响应码
    response_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="业务响应码"
    )
    
    # 响应消息
    response_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="响应消息"
    )
    
    # ==================== 客户端信息 ====================
    
    # 客户端 IP
    ip: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="客户端 IP"
    )
    
    # User-Agent
    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="User-Agent"
    )
    
    # ==================== 性能指标 ====================
    
    # 请求耗时（毫秒）
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="请求耗时（毫秒）"
    )
    
    def __repr__(self) -> str:
        return (
            f"<OperationLog(id={self.id}, user={self.username}, "
            f"action={self.action}, path={self.path})>"
        )


__all__ = ["OperationLog"]
