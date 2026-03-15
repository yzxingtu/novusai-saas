"""公共序列化辅助函数 — 避免各 handler 重复定义 / Shared serialization helpers to avoid duplicate definitions in handlers."""

from __future__ import annotations


def node_schema(node) -> dict:
    """将 NetDiskNode ORM 对象序列化为 API 响应 dict（完整版，含软删除字段） / Serialize node to API dict (with soft-delete)."""
    return {
        "id":         node.id,
        "parentId":   node.parent_id,
        "name":       node.name,
        "nodeType":   node.node_type,
        "sizeBytes":  node.size_bytes,
        "mimeType":   node.mime_type,
        "isDeleted":  node.is_deleted,
        "deletedAt":  node.deleted_at.isoformat() if node.deleted_at else None,
        "createdAt":  node.created_at.isoformat() if node.created_at else None,
        "updatedAt":  node.updated_at.isoformat() if node.updated_at else None,
    }


def share_schema(share, node_name: str | None = None, node_type: str | None = None) -> dict:
    """将 Share ORM 对象序列化为 API 响应 dict / Serialize Share to API dict."""
    result = {
        "id":          share.id,
        "nodeId":      share.node_id,
        "nodeName":    node_name,
        "nodeType":    node_type,
        "shareToken":  share.share_token,
        "permission":  share.permission,
        "hasPassword": share.password_hash is not None,
        "expiresAt":   share.expires_at.isoformat() if share.expires_at else None,
        "accessCount": share.access_count,
        "isActive":    share.is_active,
        "createdAt":   share.created_at.isoformat() if share.created_at else None,
    }
    return result
