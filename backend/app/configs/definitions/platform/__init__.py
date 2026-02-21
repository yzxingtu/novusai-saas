"""
平台配置定义

导入所有平台配置模块以触发配置注册
"""

# 导入配置模块（触发配置注册到分组）
from app.configs.definitions.platform import general
from app.configs.definitions.platform import security
from app.configs.definitions.platform import email
from app.configs.definitions.platform import storage
from app.configs.definitions.platform import ssl
from app.configs.definitions.platform import websocket
from app.configs.definitions.platform import ai_toolkit


__all__ = [
    "general",
    "security",
    "email",
    "storage",
    "ssl",
    "websocket",
    "ai_toolkit",
]
