"""
System event hook point constants.
/ 系统事件钩子点常量

Defines standard system hook points that plugins can subscribe to.
Reference these constants in plugin.yaml extensions.hooks point field.
/ 定义插件可订阅的标准系统钩子点。

Usage (plugin.yaml) / 用法:
  extensions:
    hooks:
      - point: system.tenant.created
        handler: backend.hooks:on_tenant_created
        priority: 50

The framework automatically calls all plugin handlers subscribed to a point
when the corresponding system event fires.
/ 框架在对应系统事件触发时自动调用所有订阅该点的插件 handler。

Handler signature / handler 签名:
  async def on_tenant_created(**context) -> dict:
      # context contains event-related data (see each point's context description)
      return context  # must return context (can be modified)
"""

from __future__ import annotations


class SystemHookPoint:
    """Standard system hook point constants (used in plugin manifest hooks.point)
    / 标准系统钩子点常量"""

    # ── Tenant lifecycle / 企业生命周期 ──
    TENANT_CREATED = "system.tenant.created"
    """Fired after tenant creation. context: {tenant_id, tenant_name, admin_id}
    / 企业创建后触发"""
    TENANT_UPDATED = "system.tenant.updated"
    """Fired after tenant info update. context: {tenant_id, changed_fields}
    / 企业信息更新后触发"""
    TENANT_DELETED = "system.tenant.deleted"
    """Fired after tenant soft-delete. context: {tenant_id, tenant_name}
    / 企业软删除后触发"""
    TENANT_ENABLED = "system.tenant.enabled"
    """Fired after tenant enabled. context: {tenant_id}
    / 企业启用后触发"""
    TENANT_DISABLED = "system.tenant.disabled"
    """Fired after tenant disabled. context: {tenant_id, reason}
    / 企业禁用后触发"""

    # ── User lifecycle / 用户生命周期 ──
    USER_CREATED = "system.user.created"
    """Fired after platform user/tenant admin creation. context: {user_id, role, tenant_id}
    / 用户创建后触发"""
    USER_LOGIN = "system.user.login"
    """Fired after successful user login. context: {user_id, role, tenant_id, ip}
    / 用户登录成功后触发"""
    USER_LOGOUT = "system.user.logout"
    """Fired after user logout. context: {user_id, role, tenant_id}
    / 用户登出后触发"""

    # ── Agent lifecycle / Agent 生命周期 ──
    AGENT_PUBLISHED = "system.agent.published"
    """Fired after Agent published. context: {agent_id, tenant_id, publish_type}
    / Agent 发布后触发"""
    AGENT_UNPUBLISHED = "system.agent.unpublished"
    """Fired after Agent unpublished. context: {agent_id, tenant_id}
    / Agent 取消发布后触发"""

    # ── AI invocation / AI 调用 ──
    BEFORE_AGENT_CHAT = "system.agent.before_chat"
    """Fired before Agent chat (messages can be modified). context: {agent_id, tenant_id, messages}
    / Agent 对话前触发"""
    AFTER_AGENT_CHAT = "system.agent.after_chat"
    """Fired after Agent chat. context: {agent_id, tenant_id, response}
    / Agent 对话后触发"""

    # ── Plugin lifecycle / 插件生命周期 ──
    PLUGIN_ENABLED = "system.plugin.enabled"
    """Fired after plugin enabled (not self, to avoid self-trigger loop). context: {plugin_name, plugin_id}
    / 插件启用后触发"""
    PLUGIN_DISABLED = "system.plugin.disabled"
    """Fired after plugin disabled. context: {plugin_name, plugin_id}
    / 插件禁用后触发"""

    # ── File/Storage / 文件/存储 ──
    FILE_UPLOADED = "system.file.uploaded"
    """Fired after file upload complete. context: {file_url, filename, tenant_id, uploader_id}
    / 文件上传完成后触发"""

    # ── Knowledge base / 知识库 ──
    KB_INDEX_COMPLETE = "system.kb.index_complete"
    """Fired after knowledge base indexing complete. context: {kb_id, tenant_id, doc_count}
    / 知识库索引完成后触发"""

    @classmethod
    def all_points(cls) -> list[str]:
        """Return list of all defined hook point names / 返回所有已定义的钩子点名称列表"""
        return [
            v for k, v in vars(cls).items()
            if not k.startswith("_") and isinstance(v, str)
        ]


async def trigger_hook(point: str, **context) -> dict:
    """
    Trigger specified system hook point, calling all registered plugin handlers.
    / 触发指定系统钩子点，调用所有已注册插件 handler。

    Non-blocking: handler exceptions don't affect the caller.
    Returns: final context (can be chain-modified by handlers).
    / 非阻塞，返回最终 context。
    """
    try:
        from app.ai.events.hooks import HookRegistry
        registry = HookRegistry.get_instance()
        if registry.has_hooks(point):
            return await registry.trigger(point, **context)
    except Exception as exc:
        from app.core.logging import get_logger
        get_logger(__name__).warning(
            "system_hook trigger failed for '%s': %s", point, exc
        )
    return context
