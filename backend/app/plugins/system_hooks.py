"""
系统事件钩子点常量

定义插件可订阅的标准系统钩子点。
在 plugin.yaml 的 extensions.hooks 中使用 point 字段引用这些常量。

用法（plugin.yaml）:
  extensions:
    hooks:
      - point: system.tenant.created
        handler: backend.hooks:on_tenant_created
        priority: 50

框架在对应系统事件触发时自动调用所有订阅该点的插件 handler。

handler 签名:
  async def on_tenant_created(**context) -> dict:
      # context 包含事件相关数据（见各点的 context 说明）
      return context  # 必须返回 context（可修改）
"""

from __future__ import annotations


class SystemHookPoint:
    """标准系统钩子点常量（插件 manifest hooks.point 使用）"""

    # ── 租户生命周期 ──
    TENANT_CREATED = "system.tenant.created"
    """租户创建后触发。context: {tenant_id, tenant_name, admin_id}"""
    TENANT_UPDATED = "system.tenant.updated"
    """租户信息更新后触发。context: {tenant_id, changed_fields}"""
    TENANT_DELETED = "system.tenant.deleted"
    """租户软删除后触发。context: {tenant_id, tenant_name}"""
    TENANT_ENABLED = "system.tenant.enabled"
    """租户启用后触发。context: {tenant_id}"""
    TENANT_DISABLED = "system.tenant.disabled"
    """租户禁用后触发。context: {tenant_id, reason}"""

    # ── 用户生命周期 ──
    USER_CREATED = "system.user.created"
    """平台用户/租户管理员创建后触发。context: {user_id, role, tenant_id}"""
    USER_LOGIN = "system.user.login"
    """用户登录成功后触发。context: {user_id, role, tenant_id, ip}"""
    USER_LOGOUT = "system.user.logout"
    """用户登出后触发。context: {user_id, role, tenant_id}"""

    # ── Agent 生命周期 ──
    AGENT_PUBLISHED = "system.agent.published"
    """Agent 发布后触发。context: {agent_id, tenant_id, publish_type}"""
    AGENT_UNPUBLISHED = "system.agent.unpublished"
    """Agent 取消发布后触发。context: {agent_id, tenant_id}"""

    # ── AI 调用 ──
    BEFORE_AGENT_CHAT = "system.agent.before_chat"
    """Agent 对话前触发（可修改消息）。context: {agent_id, tenant_id, messages}"""
    AFTER_AGENT_CHAT = "system.agent.after_chat"
    """Agent 对话后触发。context: {agent_id, tenant_id, response}"""

    # ── 插件生命周期 ──
    PLUGIN_ENABLED = "system.plugin.enabled"
    """插件启用后触发（非本插件，避免自触发死循环）。context: {plugin_name, plugin_id}"""
    PLUGIN_DISABLED = "system.plugin.disabled"
    """插件禁用后触发。context: {plugin_name, plugin_id}"""

    # ── 文件/存储 ──
    FILE_UPLOADED = "system.file.uploaded"
    """文件上传完成后触发。context: {file_url, filename, tenant_id, uploader_id}"""

    # ── 知识库 ──
    KB_INDEX_COMPLETE = "system.kb.index_complete"
    """知识库索引完成后触发。context: {kb_id, tenant_id, doc_count}"""

    @classmethod
    def all_points(cls) -> list[str]:
        """返回所有已定义的钩子点名称列表"""
        return [
            v for k, v in vars(cls).items()
            if not k.startswith("_") and isinstance(v, str)
        ]


async def trigger_hook(point: str, **context) -> dict:
    """
    触发指定系统钩子点，调用所有已注册插件 handler。

    非阻塞：handler 异常不影响调用方。
    返回：最终 context（可被 handler 链式修改）。
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
