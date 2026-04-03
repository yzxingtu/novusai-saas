"""
AI Module Constants / AI 模块常量定义

Centralized Redis key prefixes, TTLs, default limits, and other constants.
集中管理 Redis Key 前缀、TTL、默认限制等常量。
"""


# ============================================
# Action Executor Rate Limiting / Action Executor 频率限制
# ============================================

# Key pattern: ai:action_rate:{tenant_id}:{action_name}
# Limits per-tenant call frequency for a specific Action
# 用于限制单个企业对某个 Action 的调用频率
ACTION_RATE_KEY_PREFIX = "ai:action_rate:"
ACTION_RATE_LIMIT_TTL = 60  # Action rate limit window / Action 频率限制窗口


def action_rate_key(tenant_id: int, action_name: str) -> str:
    """构建 Action 频率限制 Redis key / Build Action rate limiting Redis key"""
    return f"{ACTION_RATE_KEY_PREFIX}{tenant_id}:{action_name}"


# ============================================
# Schema Provider Cache / Schema Provider 缓存
# ============================================

# Key pattern: ai:schema:{tenant_id}
# Caches tenant DB schema info for Text-to-SQL
# 缓存企业的数据库 Schema 信息，供 Text-to-SQL 使用
SCHEMA_CACHE_KEY_PREFIX = "ai:schema:"
SCHEMA_CACHE_TTL = 3600  # Schema cache 1 hour / Schema 缓存 1 小时缓存


def schema_cache_key(tenant_id: int) -> str:
    """构建 Schema 缓存 Redis key / Build Schema cache Redis key"""
    return f"{SCHEMA_CACHE_KEY_PREFIX}{tenant_id}"


# ============================================
# Text-to-SQL Query Result Cache / Text-to-SQL 查询结果缓存
# ============================================

# Key pattern: ai:sql_result:{tenant_id}:{query_hash}
# Caches identical query results to avoid re-execution
# 缓存相同查询的结果，避免重复执行
SQL_RESULT_CACHE_KEY_PREFIX = "ai:sql_result:"
SQL_RESULT_CACHE_TTL = 300  # SQL result cache 5 min / SQL 结果缓存 5 分钟缓存


def sql_result_cache_key(tenant_id: int, query_hash: str) -> str:
    """构建 SQL 查询结果缓存 Redis key / Build SQL result cache Redis key"""
    return f"{SQL_RESULT_CACHE_KEY_PREFIX}{tenant_id}:{query_hash}"


# ============================================
# Default Limits / 默认限制
# ============================================

# Default action rate limit (per hour) / Action 默认频率限制（每小时）
DEFAULT_ACTION_RATE_LIMIT = 100

# Text-to-SQL max rows returned / Text-to-SQL 最大返回行数
TEXT_TO_SQL_MAX_ROWS = 200

# Text-to-SQL query timeout (seconds) / Text-to-SQL 查询超时（秒）
TEXT_TO_SQL_TIMEOUT = 30


# ============================================
# Session Memory Scenes (Entry Boundary) / 会话记忆场景（入口边界）
# ============================================

# Legacy default memory scene marker.
# Runtime allowlist is resolved in AgentChatService._resolve_memory_context()
# and currently includes ai_chat_page + admin_chat.
# 历史默认记忆场景标记。运行时真正允许的场景由
# AgentChatService._resolve_memory_context() 决定，当前包含
# ai_chat_page + admin_chat。
MEMORY_ENABLED_SCENE = "ai_chat_page"

# Default scene (used when not explicitly provided) / 默认场景（未显式传入时使用）
DEFAULT_MEMORY_SCENE = "unknown"

# Channel enum values (for key namespacing/auditing) / 渠道枚举值（用于 key namespacing/审计）
MEMORY_CHANNEL_TENANT_CHAT = "tenant_chat"
MEMORY_CHANNEL_ADMIN_CHAT = "admin_chat"
MEMORY_CHANNEL_PLUGIN = "plugin"
MEMORY_CHANNEL_SYSTEM = "system"


# ============================================
# Session Memory Storage (Redis) / 会话记忆存储（Redis）
# ============================================

# Key pattern / Key 模式
# mem:sess:{tenant_id}:{channel}:{source}:{agent_id}:{user_id}:{conversation_id} / 占位：租户、渠道、来源、智能体、用户、会话 ID
SESSION_MEMORY_KEY_PREFIX = "mem:sess:"

# Session memory TTL (seconds), for fallback cleanup / 会话记忆 TTL（秒），用于兜底清理
SESSION_MEMORY_TTL_SECONDS = 86400  # Session memory 24 hours / 会话记忆 24 小时


def session_memory_key(
    tenant_id: int,
    channel: str,
    source: str,
    agent_id: int,
    user_id: int,
    conversation_id: int,
) -> str:
    """构建会话记忆 Redis key / Build session memory Redis key"""
    safe_source = (source or "unknown").replace(":", "_")
    return (
        f"{SESSION_MEMORY_KEY_PREFIX}"
        f"{tenant_id}:{channel}:{safe_source}:{agent_id}:{user_id}:{conversation_id}"
    )


def session_memory_conversation_pattern(tenant_id: int, conversation_id: int) -> str:
    """Match session memory keys by tenant + conversation (for cleanup) / 按 tenant + conversation 维度匹配会话记忆 key（用于清理）"""
    return f"{SESSION_MEMORY_KEY_PREFIX}{tenant_id}:*:*:*:*:{conversation_id}"


def session_memory_tenant_pattern(tenant_id: int) -> str:
    """Match all session memory keys by tenant / 按 tenant 维度匹配全部会话记忆 key。"""
    return f"{SESSION_MEMORY_KEY_PREFIX}{tenant_id}:*"


__all__ = [
    # Rate limiting / 频率限制
    "ACTION_RATE_KEY_PREFIX",
    "ACTION_RATE_LIMIT_TTL",
    "action_rate_key",
    # Schema cache / Schema 缓存
    "SCHEMA_CACHE_KEY_PREFIX",
    "SCHEMA_CACHE_TTL",
    "schema_cache_key",
    # SQL result cache / SQL 结果缓存
    "SQL_RESULT_CACHE_KEY_PREFIX",
    "SQL_RESULT_CACHE_TTL",
    "sql_result_cache_key",
    # Default limits / 默认限制
    "DEFAULT_ACTION_RATE_LIMIT",
    "TEXT_TO_SQL_MAX_ROWS",
    "TEXT_TO_SQL_TIMEOUT",
    # Session memory scenes / 会话记忆场景
    "MEMORY_ENABLED_SCENE",
    "DEFAULT_MEMORY_SCENE",
    "MEMORY_CHANNEL_TENANT_CHAT",
    "MEMORY_CHANNEL_ADMIN_CHAT",
    "MEMORY_CHANNEL_PLUGIN",
    "MEMORY_CHANNEL_SYSTEM",
    # Session memory storage / 会话记忆存储
    "SESSION_MEMORY_KEY_PREFIX",
    "SESSION_MEMORY_TTL_SECONDS",
    "session_memory_key",
    "session_memory_conversation_pattern",
    "session_memory_tenant_pattern",
]
