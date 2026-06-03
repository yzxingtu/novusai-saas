"""
Agent quota configuration / 智能体配额配置
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class AgentQuotaConfig:
    """
    Agent Quota Configuration / 智能体配额配置

    Attributes:
        daily_token_limit: Daily token cap (0 = unlimited) / 每日 Token 上限（0 = 不限制）
        monthly_token_limit: Monthly token cap (0 = unlimited) / 每月 Token 上限（0 = 不限制）
        conversations_per_day: Max daily conversations (0 = unlimited) / 每日最大对话数（0 = 不限制）
        max_turns_per_conversation: Max turns per conversation (0 = unlimited) / 单次对话最大轮次（0 = 不限制）
        max_tokens_per_conversation: Max tokens per conversation (0 = unlimited) / 单次对话最大 Token（0 = 不限制）
        user_conversations_per_day: Per-user daily conversation cap (0 = unlimited) / 每用户每日对话上限（0 = 不限制）
        user_tokens_per_day: Per-user daily token cap (0 = unlimited) / 每用户每日 Token 上限（0 = 不限制）
        max_concurrent: Max concurrent executions (0 = unlimited) / 最大并发执行数（0 = 不限制）
        tenant_max_concurrent: Tenant-wide max concurrency (0 = unlimited) / 全企业最大并发（0 = 不限制）
        warning_threshold: Warning threshold percentage (0-100) / 预警阈值百分比（0-100）
    """

    daily_token_limit: int = 0
    monthly_token_limit: int = 0
    conversations_per_day: int = 0
    max_turns_per_conversation: int = 50
    max_tokens_per_conversation: int = 0
    user_conversations_per_day: int = 0
    user_tokens_per_day: int = 0
    max_concurrent: int = 10
    tenant_max_concurrent: int = 50
    warning_threshold: int = 80

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AgentQuotaConfig":
        """Build config from Agent.quota_config JSON field / 从 Agent.quota_config JSON 字段构建配置"""
        if not data:
            return cls()
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {
            k: v for k, v in data.items() if k in known_fields and v is not None
        }
        return cls(**filtered)


__all__ = ["AgentQuotaConfig"]
