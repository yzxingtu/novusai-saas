"""
平台配置定义

导入所有平台配置模块以触发配置注册
"""

# 导入配置模块（触发配置注册到分组）
from app.configs.definitions.platform import (
    ai_memory,
    ai_toolkit,
    email,
    general,
    security,
    ssl,
    storage,
    websocket,
)

__all__ = [
    "general",
    "security",
    "email",
    "storage",
    "ssl",
    "websocket",
    "ai_toolkit",
    "ai_memory",
]
