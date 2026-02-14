"""
AI 模块常量定义

统一管理 Redis Key Pattern 和 TTL，避免各模块硬编码
"""


# ============================================
# Action Executor 频率限制
# ============================================

# Key pattern: ai:action_rate:{tenant_id}:{action_name}
# 用于限制单个租户对某个 Action 的调用频率
ACTION_RATE_KEY_PREFIX = "ai:action_rate:"
ACTION_RATE_TTL = 3600  # 1 小时窗口


def action_rate_key(tenant_id: int, action_name: str) -> str:
    """构建 Action 频率限制 Redis key"""
    return f"{ACTION_RATE_KEY_PREFIX}{tenant_id}:{action_name}"


# ============================================
# Action 确认（AsyncConfirm）
# ============================================

# Key pattern: ai:action_confirm:{confirm_id}
# 存储待确认操作的上下文数据，等待用户确认后执行
CONFIRM_KEY_PREFIX = "ai:action_confirm:"
CONFIRM_TTL = 300  # 5 分钟过期


def action_confirm_key(confirm_id: str) -> str:
    """构建 Action 确认 Redis key"""
    return f"{CONFIRM_KEY_PREFIX}{confirm_id}"


# ============================================
# Schema Provider 缓存
# ============================================

# Key pattern: ai:schema:{tenant_id}
# 缓存租户的数据库 Schema 信息，供 Text-to-SQL 使用
SCHEMA_CACHE_KEY_PREFIX = "ai:schema:"
SCHEMA_CACHE_TTL = 3600  # 1 小时缓存


def schema_cache_key(tenant_id: int) -> str:
    """构建 Schema 缓存 Redis key"""
    return f"{SCHEMA_CACHE_KEY_PREFIX}{tenant_id}"


# ============================================
# Text-to-SQL 查询结果缓存
# ============================================

# Key pattern: ai:sql_result:{tenant_id}:{query_hash}
# 缓存相同查询的结果，避免重复执行
SQL_RESULT_CACHE_KEY_PREFIX = "ai:sql_result:"
SQL_RESULT_CACHE_TTL = 600  # 10 分钟缓存


def sql_result_cache_key(tenant_id: int, query_hash: str) -> str:
    """构建 SQL 查询结果缓存 Redis key"""
    return f"{SQL_RESULT_CACHE_KEY_PREFIX}{tenant_id}:{query_hash}"


# ============================================
# 默认限制
# ============================================

# Action 默认频率限制（每小时）
DEFAULT_ACTION_RATE_LIMIT = 100

# Text-to-SQL 最大返回行数
TEXT_TO_SQL_MAX_ROWS = 200

# Text-to-SQL 查询超时（秒）
TEXT_TO_SQL_TIMEOUT = 30


__all__ = [
    # 频率限制
    "ACTION_RATE_KEY_PREFIX",
    "ACTION_RATE_TTL",
    "action_rate_key",
    # 确认
    "CONFIRM_KEY_PREFIX",
    "CONFIRM_TTL",
    "action_confirm_key",
    # Schema 缓存
    "SCHEMA_CACHE_KEY_PREFIX",
    "SCHEMA_CACHE_TTL",
    "schema_cache_key",
    # SQL 结果缓存
    "SQL_RESULT_CACHE_KEY_PREFIX",
    "SQL_RESULT_CACHE_TTL",
    "sql_result_cache_key",
    # 默认限制
    "DEFAULT_ACTION_RATE_LIMIT",
    "TEXT_TO_SQL_MAX_ROWS",
    "TEXT_TO_SQL_TIMEOUT",
]
