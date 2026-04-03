"""
AI 表策略自动发现与同步服务 / AI Table Policy Auto-Discovery & Sync Service

负责扫描声明了 __ai_policy__ 的 SQLAlchemy 模型，创建 ai_table_policies 默认记录。
Scans models with __ai_policy__ declaration to create ai_table_policies default records.
采用白名单声明制：仅处理显式声明 __ai_policy__ 的 Model，未声明的表对 AI 完全不可见。
Uses declarative whitelist: only models with __ai_policy__ are synced; undeclared tables are invisible to AI.
"""

from enum import Enum
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapper

from app.core.base_model import Base, BaseModel, utc_now
from app.core.logging import get_logger
from app.models.ai.table_policy import AITablePolicy

logger = get_logger(__name__)

# ===== 全局敏感列名模式 / Global sensitive column patterns =====
_SENSITIVE_COLUMN_PATTERNS: set[str] = {
    "password",
    "password_hash",
    "hashed_password",
    "secret",
    "secret_key",
    "api_key",
    "access_token",
    "refresh_token",
    "encrypted_key",
    "salt",
}

# ===== 只读系统列 / Read-only system columns =====
_READONLY_COLUMNS: list[str] = [
    "id",
    "created_at",
    "updated_at",
    "is_deleted",
    "tenant_id",
]

# ===== 表名 → 中文关键词映射（常用表手动维护） / Table → keyword hints (curated) =====
_TABLE_KEYWORDS: dict[str, list[str]] = {
    "tenants": ["企业", "tenant", "组织", "商户", "客户"],
    "tenant_plans": ["套餐", "plan", "计划", "订阅"],
    "tenant_users": ["用户", "user", "终端用户"],
    "tenant_admins": ["管理员", "admin", "企业管理员"],
    "tenant_domains": ["域名", "domain"],
    "agents": ["智能体", "agent", "机器人", "bot", "助手"],
    "agent_conversations": ["对话", "conversation", "chat", "聊天"],
    "conversation_messages": ["消息", "message", "对话消息"],
    "knowledge_bases": ["知识库", "knowledge", "知识"],
    "knowledge_documents": ["文档", "document", "知识文档"],
    "document_chunks": ["分块", "chunk", "文档块"],
    "ai_providers": ["供应商", "provider", "AI供应商"],
    "ai_models": ["模型", "model", "AI模型"],
    "ai_call_logs": ["调用日志", "call_log", "AI调用"],
    "ai_query_logs": ["查询日志", "query_log", "审计"],
    "ai_action_logs": ["操作日志", "action_log"],
    "tenant_agent_publications": ["智能体用户发布", "publication", "租户智能体发布"],
    "tenant_agent_platform_kb_suppressions": [
        "平台知识库本企业停用",
        "platform_kb_opt_out",
        "租户停用平台KB",
    ],
    "operation_logs": ["操作日志", "operation", "日志"],
    "attachments": ["附件", "attachment", "文件"],
    "batch_runs": ["批处理", "batch", "批量运行"],
    "agent_versions": ["版本", "version", "智能体版本"],
    "agent_access": ["访问权限", "access", "智能体权限"],
    "tenant_quotas": ["配额", "quota", "企业配额"],
    "tenant_model_rate_limits": ["限流", "rate_limit", "速率限制"],
    "periodic_tasks": ["定时任务", "periodic", "计划任务"],
    "task_logs": ["任务日志", "task_log"],
}

# ===== 列名 → 描述映射（AI / i18n 回退） / Column → description map for AI & i18n fallback =====
_COLUMN_DESC_MAP: dict[str, str] = {
    # 通用 / 基类 / Common & base
    "id": "主键 ID",
    "created_at": "创建时间",
    "updated_at": "更新时间",
    "is_deleted": "是否已删除（软删除）",
    "deleted_at": "删除时间",
    "delete_level": "删除层级",
    "tenant_id": "所属企业 ID",
    "sort_order": "排序序号",
    "is_active": "是否启用",
    "name": "名称",
    "description": "描述",
    "code": "编码",
    "label": "显示名称",
    "status": "状态",
    "scope": "资源作用域 ResourceScopeEnum：global_shared/admin_only/all_tenants/admin_and_selected_tenants/selected_tenants",
    "type": "类型",
    "icon": "图标",
    "path": "路径",
    "parent_id": "父节点 ID",
    "level": "层级",
    "action": "操作",
    "resource": "资源",
    "component": "组件",
    "hidden": "是否隐藏",
    "is_enabled": "是否启用",
    "owner_tenant_id": "资源归属企业 ID（平台级资源为 NULL）",
    "visibility": "可见性",
    "avatar": "头像 URL",
    # 用户 / 企业 / User & tenant
    "user_id": "用户 ID",
    "user_type": "用户类型（admin/tenant_user）",
    "user_role": "用户角色",
    "username": "用户名",
    "nickname": "昵称",
    "email": "邮箱",
    "phone": "手机号",
    "is_owner": "是否企业主",
    "role_id": "角色 ID",
    "contact_name": "联系人姓名",
    "contact_phone": "联系电话",
    "contact_email": "联系邮箱",
    "remark": "备注",
    "plan": "套餐代码",
    "plan_id": "关联套餐 ID",
    "quota": "配额配置",
    "expires_at": "过期时间",
    "settings": "设置（JSON）",
    "last_login_at": "最后登录时间",
    "last_login_ip": "最后登录 IP",
    "login_fail_count": "登录失败次数",
    "last_fail_at": "最后失败时间",
    "locked_until": "锁定截至时间",
    "approval_status": "审批状态",
    "openid": "微信 OpenID",
    "unionid": "微信 UnionID",
    "gender": "性别",
    "extra": "扩展信息（JSON）",
    # AI 模型 / 供应商
    "model_id": "关联 AI 模型 ID",
    "provider_id": "关联 AI 供应商 ID",
    "routed_model_id": "实际路由到的模型 ID",
    "provider_name": "供应商名称",
    "model_name": "模型名称",
    "base_url": "基础 URL",
    "usage_limit": "使用次数上限",
    "usage_count": "已使用次数",
    "last_used_at": "最后使用时间",
    "encrypted_key": "加密后的 API Key",
    "config": "配置（JSON）",
    "system_prompt": "系统提示词",
    "temperature": "采样温度（0-2）",
    "max_tokens": "最大输出 Token 数",
    "top_p": "Top-P 采样参数",
    "execution_mode": "执行模式（conversation/batch）",
    "published_version": "已发布版本号",
    "version": "版本号",
    "change_log": "变更说明",
    "skill_grant_snapshot": "技能授权快照",
    "memory_enabled": "是否启用对话记忆",
    "input_variables": "输入变量（JSON）",
    "rag_config": "RAG 知识库配置",
    "context_config": "上下文配置",
    "output_schema": "输出 Schema",
    "quota_config": "配额配置",
    "routing_config": "多模型路由配置",
    "is_system": "是否系统内置",
    "welcome_message": "欢迎语",
    "suggested_questions": "推荐问题列表",
    # AI 调用 / 用量
    "input_tokens": "输入 Token 数",
    "output_tokens": "输出 Token 数",
    "total_tokens": "总 Token 数",
    "total_cost": "总费用（美元）",
    "cost": "单次费用（美元）",
    "latency_ms": "延迟（毫秒）",
    "avg_latency_ms": "平均延迟（毫秒）",
    "max_latency_ms": "最大延迟（毫秒）",
    "duration_ms": "耗时（毫秒）",
    "call_count": "调用次数",
    "success_count": "成功次数",
    "failed_count": "失败次数",
    "stat_date": "统计日期",
    "request_type": "请求类型（chat/completion/embedding）",
    "request_hash": "请求哈希（去重）",
    "request_metadata": "请求元数据（JSON）",
    "route_reason": "路由原因",
    "rpm_limit": "每分钟请求限制",
    "tpm_limit": "每分钟 Token 限制",
    # AI 模型扩展
    "context_window": "上下文窗口大小（tokens）",
    "max_output_tokens": "最大输出 Token 数",
    "input_price_per_1k": "输入价格（每 1k tokens，美元）",
    "output_price_per_1k": "输出价格（每 1k tokens，美元）",
    "supports_function_calling": "是否支持 Function Calling",
    "supports_vision": "是否支持视觉",
    "supports_streaming": "是否支持流式输出",
    "max_image_count": "最大图片数量",
    "max_image_size_mb": "单张图片最大尺寸（MB）",
    "tier": "模型级别",
    "fallback_model_id": "备用模型 ID（故障转移）",
    "supports_audio": "支持音频",
    "supports_video": "支持视频",
    # 智能体 / 对话 / Agent & conversation
    "agent_id": "关联智能体 ID",
    "conversation_id": "关联对话 ID",
    "title": "标题",
    "messages": "消息列表（JSON）",
    "message_count": "消息数量",
    "token_count": "Token 数量",
    "metadata_": "元数据（JSON）",
    "metadata": "元数据（JSON）",
    "content": "消息内容",
    "role": "角色（user/assistant/system）",
    # 技能 / 技能包 / Skills & packages
    "skill_id": "关联技能 ID",
    "skill_package_id": "关联技能包 ID",
    "package_id": "关联技能包 ID",
    "toolkit_content": "工具包内容",
    "toolkit_meta": "工具包元数据",
    "input_schema": "输入 Schema",
    "timeout": "超时时间（秒）",
    "disabled": "是否禁用",
    "weight": "权重",
    "enabled": "是否启用",
    "tool_name": "工具名称",
    "tool_type": "工具类型",
    "operator_id": "操作者 ID",
    "action_name": "操作名称",
    "action_type": "操作类型",
    "action_level": "操作级别",
    "request_data": "请求数据（JSON）",
    "response_data": "响应数据（JSON）",
    "error_message": "错误信息",
    "is_recommended": "是否推荐",
    "source_plugin": "来源插件",
    "valves_schema": "阀门配置 Schema",
    "valves_config": "阀门配置值",
    # 知识库 / Knowledge base
    "knowledge_base_id": "关联知识库 ID",
    "document_id": "关联文档 ID",
    "chunk_index": "分块索引",
    "chunk_content": "分块内容",
    "chunk_count": "分块数量",
    "chunk_size": "分块大小",
    "chunk_overlap": "分块重叠",
    "chunk_strategy": "分块策略",
    "embedding_model_id": "嵌入模型 ID",
    "embedding_dimensions": "嵌入维度",
    "vision_model_id": "视觉模型 ID",
    "audio_model_id": "音频模型 ID",
    "video_model_id": "视频模型 ID",
    "extract_images": "是否提取图片",
    "search_mode": "检索模式",
    "top_k": "Top-K 检索数",
    "score_threshold": "相似度阈值",
    "document_count": "文档数量",
    "total_chunks": "总分块数",
    "total_size_bytes": "总大小（字节）",
    "attachment_id": "关联附件 ID",
    "file_name": "文件名",
    "file_type": "文件类型",
    "file_size": "文件大小（字节）",
    "file_hash": "文件哈希",
    "source_url": "来源 URL",
    "metadata_extra": "扩展元数据",
    "error_stage": "错误阶段",
    "char_count": "字符数",
    "processing_started_at": "处理开始时间",
    "processing_completed_at": "处理完成时间",
    "content_hash": "内容哈希",
    "content_tsv": "全文搜索向量（TSV）",
    "embedding": "嵌入向量",
    # 批量任务 / Batch jobs
    "created_by": "创建者 ID",
    "total_items": "总条目数",
    "completed_items": "已完成条目数",
    "failed_items": "失败条目数",
    "completed_at": "完成时间",
    "result_summary": "结果摘要（JSON）",
    "error_summary": "错误摘要（JSON）",
    "max_workers": "最大并发数",
    "results": "执行结果列表",
    "errors": "错误列表",
    "input_items": "输入条目（JSON）",
    "celery_task_id": "Celery 任务 ID",
    "started_at": "开始时间",
    # 查询日志 / Query logs
    "question": "用户原始问题",
    "generated_sql": "LLM 生成的 SQL",
    "final_sql": "隔离注入后的最终 SQL",
    "row_count": "返回行数",
    "confidence": "置信度",
    # 操作日志 / Operation logs
    "module": "模块",
    "trace_id": "链路 ID",
    "method": "HTTP 方法",
    "query_params": "查询参数（JSON）",
    "request_body": "请求体（JSON）",
    "status_code": "HTTP 状态码",
    "response_code": "业务状态码",
    "response_message": "业务响应消息",
    "ip": "客户端 IP",
    "user_agent": "User-Agent",
    # 邮件 / Email
    "to_address": "收件人地址",
    "cc": "抄送（逗号分隔）",
    "bcc": "密送（逗号分隔）",
    "subject": "邮件主题",
    "triggered_by": "触发来源",
    "html_body": "HTML 正文",
    "text_body": "纯文本正文",
    "sent_at": "发送时间",
    # 任务日志 / Task logs
    "task_id": "任务 ID",
    "task_name": "任务名称",
    "queue": "队列名",
    "args": "任务参数（JSON）",
    "kwargs": "任务关键字参数（JSON）",
    "result": "执行结果（JSON）",
    "traceback": "异常堆栈",
    "finished_at": "结束时间",
    "retry_count": "重试次数",
    # 通知 / Notifications
    "recipient_type": "接收者类型",
    "recipient_id": "接收者 ID",
    "template_code": "模板代码",
    "category": "分类",
    "body": "通知正文",
    "link": "跳转链接",
    "priority": "优先级",
    "is_read": "是否已读",
    "read_at": "阅读时间",
    "data": "数据（JSON）",
    "expired_at": "过期时间",
    # 附件 / Attachments
    "original_name": "原始文件名",
    "size": "文件大小（字节）",
    "hash": "文件哈希",
    "mime_type": "MIME 类型",
    "extension": "文件扩展名",
    "driver": "存储驱动",
    "source": "来源",
    "uploader_id": "上传者 ID",
    "business_type": "业务类型",
    "business_id": "业务 ID",
    "meta": "元数据（JSON）",
    # 角色 / 权限 / Roles & permissions
    "allow_members": "是否允许成员",
    "leader_id": "负责人 ID",
    "data_scope": "数据范围",
    "permission_code": "权限码",
    # 表策略 / Table policy
    "table_name": "表名",
    "policy_id": "关联策略 ID",
    "keywords": "关键词（JSON 数组）",
    "column_descriptions": "列描述（JSON）",
    "allow_read": "允许读取",
    "allow_create": "允许创建",
    "allow_update": "允许更新",
    "allow_delete": "允许删除",
    "max_rows": "最大返回行数",
    "blocked_columns": "屏蔽列（JSON）",
    "readonly_columns": "只读列（JSON）",
}


def _is_i18n_key(text: str) -> bool:
    """
    检测文本是否为未翻译的 i18n 键（如 enum.agent_model.name）。

    特征：点号分隔、多段、每段为字母数字下划线，且无中文。
    """
    if not text or len(text) > 100:
        return False
    parts = text.split(".")
    if len(parts) < 2:
        return False
    # 每段应为字母数字下划线，且不含中文 / Each segment: alnum + underscore, no CJK
    for part in parts:
        clean = part.replace("_", "")
        if not clean.isalnum():
            return False
    # 简单排除：若包含常见中文，则不是 i18n 键 / Any CJK → not i18n key
    return all(not "\u4e00" <= c <= "\u9fff" for c in text)


def _humanize_table_name(table_name: str) -> str:
    """将 snake_case 表名转为可读标签 / Convert snake_case table name to readable label."""
    return table_name.replace("_", " ").title()


def _derive_permission_code(table_name: str, has_tenant: bool) -> str:
    """从表名推导权限码 / Derive permission code from table name."""
    if not has_tenant:
        return "platform_only"
    # 去除复数 s，转为资源名 / Strip plural 's' → resource slug
    resource = table_name.rstrip("s")
    # 特殊处理一些表名 / Exceptions for irregular table names
    resource_map = {
        "tenant_user": "tenant_user",
        "tenant_admin": "tenant_admin",
        "tenant_domain": "tenant_domain",
        "tenant_plan": "tenant_plan",
        "tool_definition": "tool_definition",
        "knowledge_base": "knowledge_base",
        "knowledge_document": "knowledge_base",
        "document_chunk": "knowledge_base",
        "agent_conversation": "agent_conversation",
        "conversation_message": "agent_conversation",
        "operation_log": "operation_log",
        "ai_call_log": "ai_call_log",
        "ai_query_log": "ai_query_log",
        "ai_action_log": "ai_action_log",
        "ai_usage_stat": "ai_usage_stat",
        "agent_version": "agent",
        "agent_access": "agent",
        "batch_run": "batch_run",
        "attachment": "attachment",
    }
    resource = resource_map.get(resource, resource)
    return f"{resource}:read"


def _get_model_class_for_table(table_name: str) -> type[BaseModel] | None:
    """根据表名查找对应的 Model 类 / Find Model class by table name."""
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        if hasattr(cls, "__tablename__") and cls.__tablename__ == table_name:
            return cls
    return None


def _extract_column_descriptions(model_cls: type[BaseModel]) -> dict[str, str]:
    """
    从 Model 的 column comment 提取列描述 / Extract column descriptions from Model comments.

    若 comment 为未翻译的 i18n 键（如 enum.agent_model.name），则从 _COLUMN_DESC_MAP 回退。
    若无 comment，也尝试从 _COLUMN_DESC_MAP 获取描述。
    """
    descriptions: dict[str, str] = {}
    mapper: Mapper = sa_inspect(model_cls)

    for attr in mapper.column_attrs:
        col = attr.columns[0]
        col_name = col.name
        comment = col.comment

        # 跳过敏感列 / Skip secret columns
        if col_name in _SENSITIVE_COLUMN_PATTERNS:
            continue

        desc_parts: list[str] = []

        # 1. 列 comment - 检测是否为未翻译的 i18n 键 / Column comment vs raw i18n key
        if comment:
            comment_str = str(comment)
            if _is_i18n_key(comment_str):
                # i18n 键未翻译，尝试静态映射回退 / Fallback to _COLUMN_DESC_MAP when i18n key raw
                fallback = _COLUMN_DESC_MAP.get(col_name)
                if fallback:
                    desc_parts.append(fallback)
            else:
                desc_parts.append(comment_str)
        else:
            # 无 comment，尝试静态映射 / No DB comment → static map
            fallback = _COLUMN_DESC_MAP.get(col_name)
            if fallback:
                desc_parts.append(fallback)

        # 2. 枚举值自动提取 / Auto-append enum value lists
        col_type = col.type
        if hasattr(col_type, "enum_class") and col_type.enum_class is not None:
            enum_cls = col_type.enum_class
            if issubclass(enum_cls, Enum):
                values = [f"{m.value}" for m in enum_cls]
                desc_parts.append(f"values: {', '.join(values)}")
        else:
            # 检查 Model 类上是否有同名的 default 引用枚举 / Infer enum from column default
            default = col.default
            if default is not None and hasattr(default, "arg"):
                arg = default.arg
                if isinstance(arg, str):
                    # 尝试查找 import 的枚举类 / Resolve enum class from module
                    _try_extract_enum_from_default(model_cls, col_name, arg, desc_parts)

        if desc_parts:
            descriptions[col_name] = "; ".join(desc_parts)

    return descriptions


def _try_extract_enum_from_default(
    model_cls: type[BaseModel],
    col_name: str,
    default_value: str,
    desc_parts: list[str],
) -> None:
    """尝试从列默认值反查枚举类并提取合法值 / Try to infer enum from column default."""
    import sys

    module = sys.modules.get(model_cls.__module__)
    if not module:
        return

    # 扫描模块级别的枚举导入 / Scan module-level Enum imports
    for _name, obj in vars(module).items():
        if not isinstance(obj, type) or not issubclass(obj, Enum):
            continue
        # 检查默认值是否属于该枚举 / Match default to enum member
        try:
            if any(m.value == default_value for m in obj):
                labels = []
                for m in obj:
                    if hasattr(m, "label_key") and m.label_key:
                        labels.append(f"{m.value}({m.name.lower()})")
                    else:
                        labels.append(m.value)
                desc_parts.append(f"values: {', '.join(labels)}")
                return
        except Exception:
            continue


def _detect_blocked_columns(table) -> list[str]:
    """检测表中的敏感列 / Detect sensitive columns in table."""
    blocked = []
    for col in table.columns:
        if col.name in _SENSITIVE_COLUMN_PATTERNS:
            blocked.append(col.name)
    return blocked


def _detect_readonly_columns(table) -> list[str]:
    """检测表中的只读列 / Detect readonly columns in table."""
    readonly = []
    for col in table.columns:
        if col.name in _READONLY_COLUMNS:
            readonly.append(col.name)
    return readonly


def _has_tenant_id(table) -> bool:
    """判断表是否有 tenant_id 列 / Whether table has tenant_id column."""
    return "tenant_id" in {c.name for c in table.columns}


def _build_default_policy_from_declaration(
    model_cls: type[BaseModel],
    ai_policy: dict[str, Any] | bool,
) -> dict[str, Any]:
    """从 Model 的 __ai_policy__ 声明构建默认策略 / Build default policy from Model __ai_policy__ declaration."""
    table_name = model_cls.__tablename__
    table = Base.metadata.tables.get(table_name)

    # 简写 True 转为空 dict / Shorthand True -> empty dict
    if ai_policy is True:
        ai_policy = {}

    # label: 优先 __ai_policy__.label > docstring 第一行 > 表名
    label = ai_policy.get("label")
    if not label and model_cls.__doc__:
        first_line = model_cls.__doc__.strip().split("\n")[0].strip()
        if first_line:
            label = first_line
    if not label:
        label = _humanize_table_name(table_name)

    # description: 优先 __ai_policy__.description > docstring
    description = ai_policy.get("description", "")
    if not description and model_cls.__doc__:
        description = model_cls.__doc__.strip()

    # keywords: 优先 __ai_policy__ > _TABLE_KEYWORDS > [表名]
    keywords = ai_policy.get("keywords")
    if keywords is None:
        keywords = _TABLE_KEYWORDS.get(table_name, [table_name])

    # CRUD 权限 / CRUD permissions
    allow_read = ai_policy.get("allow_read", True)
    allow_create = ai_policy.get("allow_create", False)
    allow_update = ai_policy.get("allow_update", False)
    allow_delete = ai_policy.get("allow_delete", False)
    max_rows = ai_policy.get("max_rows", 200)

    # 列控制: 优先 __ai_policy__ > 自动检测 / Column control: __ai_policy__ > auto-detect
    blocked_columns = ai_policy.get("blocked_columns")
    if blocked_columns is None and table is not None:
        blocked_columns = _detect_blocked_columns(table)
    readonly_columns = ai_policy.get("readonly_columns")
    if readonly_columns is None and table is not None:
        readonly_columns = _detect_readonly_columns(table)

    # 列描述 / Column descriptions
    column_descriptions = _extract_column_descriptions(model_cls)

    # 权限码 / Permission code
    has_tenant = table is not None and _has_tenant_id(table)
    permission_code = _derive_permission_code(table_name, has_tenant)

    now = utc_now()

    return {
        "table_name": table_name,
        "label": label,
        "description": description,
        "keywords": keywords,
        "column_descriptions": column_descriptions,
        "allow_read": allow_read,
        "allow_create": allow_create,
        "allow_update": allow_update,
        "allow_delete": allow_delete,
        "max_rows": max_rows,
        "blocked_columns": blocked_columns or [],
        "readonly_columns": readonly_columns or [],
        "permission_code": permission_code,
        "sort_order": 0,
        "is_active": True,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
    }


def get_declared_table_names() -> set[str]:
    """获取所有声明了 __ai_policy__ 的表名 / Get table names of models with __ai_policy__."""
    declared: set[str] = set()
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        # 仅当类自身定义 __abstract__=True 时跳过（不因继承 BaseModel 的 __abstract__ 而误跳）
        if cls.__dict__.get("__abstract__", False):
            continue
        if getattr(cls, "__ai_policy__", None) is None:
            continue
        if hasattr(cls, "__tablename__"):
            declared.add(cls.__tablename__)
    return declared


# 管理员自定义字段（sync 时保留旧值，不从声明覆盖） / Fields preserved on sync (not overwritten by codegen)
_ADMIN_CUSTOM_FIELDS: tuple[str, ...] = (
    "max_rows",
    "allow_create",
    "allow_update",
    "allow_delete",
    "column_descriptions",
    "is_active",
    "sort_order",
)


def _extract_admin_custom(policy: AITablePolicy) -> dict[str, Any]:
    """提取管理员自定义字段用于回填 / Extract admin custom fields for restore."""
    return {k: getattr(policy, k) for k in _ADMIN_CUSTOM_FIELDS}


async def sync_table_policies(db: AsyncSession) -> dict[str, Any]:
    """
    同步表策略：先删后建 + 保留自定义 / Sync table policies: delete all then rebuild, preserving admin customizations.

    1. 缓存现有策略的管理员自定义字段（max_rows, column_descriptions 等）
    2. 硬删除全部旧记录（ai_table_policy_overrides 级联删除）
    3. 从 __ai_policy__ 声明重建
    4. 对同名表回填管理员自定义字段

    Returns:
        {"synced": N, "declared_tables": [...]}
    """
    # 1. 缓存旧配置（仅 is_deleted=False 的活跃记录） / Snapshot active rows before delete
    old_result = await db.execute(
        select(AITablePolicy).where(AITablePolicy.is_deleted == False)  # noqa: E712
    )
    old_policies: dict[str, dict[str, Any]] = {}
    for p in old_result.scalars().all():
        old_policies[p.table_name] = _extract_admin_custom(p)

    # 2. 硬删除全部旧记录（CASCADE 会清理 ai_table_policy_overrides） / Hard-delete policies (CASCADE overrides)
    await db.execute(delete(AITablePolicy))
    await db.flush()

    # 3. 从声明重建并回填自定义 / Rebuild from __ai_policy__, merge admin overrides
    declared_names: list[str] = []
    for mapper in Base.registry.mappers:
        cls = mapper.class_

        if cls.__dict__.get("__abstract__", False):
            continue

        ai_policy = getattr(cls, "__ai_policy__", None)
        if ai_policy is None:
            continue

        table_name = getattr(cls, "__tablename__", None)
        if not table_name:
            continue

        declared_names.append(table_name)
        policy_data = _build_default_policy_from_declaration(cls, ai_policy)

        # 4. 回填管理员自定义字段 / Restore admin-tuned fields
        if table_name in old_policies:
            old_custom = old_policies[table_name]
            for k, v in old_custom.items():
                if v is None:
                    continue
                if k == "column_descriptions" and isinstance(v, dict):
                    # 合并：仅保留非 i18n 键的旧值（管理员自定义），其余用新提取的描述 / Merge manual descs + fresh extract
                    new_descs = policy_data.get("column_descriptions") or {}
                    merged: dict[str, str] = {}
                    for col, old_val in v.items():
                        s = str(old_val).strip()
                        # 丢弃以 enum. 开头的（含 "enum.xxx; values: ..." 这种混合格式） / Skip enum.* legacy strings
                        if s and not s.startswith("enum.") and not _is_i18n_key(s):
                            merged[col] = s
                    for col, new_val in new_descs.items():
                        if col not in merged:
                            merged[col] = new_val
                    policy_data["column_descriptions"] = merged
                else:
                    policy_data[k] = v

        policy = AITablePolicy(**policy_data)
        db.add(policy)

    await db.commit()

    synced = len(declared_names)
    logger.info(
        "Table policy sync: synced={} from __ai_policy__ declarations",
        synced,
    )

    return {
        "synced": synced,
        "declared_tables": declared_names,
    }


__all__ = ["sync_table_policies", "get_declared_table_names"]
