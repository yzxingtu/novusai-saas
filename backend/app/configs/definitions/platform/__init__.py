"""
平台配置定义

导入所有平台配置模块以触发配置注册
"""

# 导入配置模块（触发配置注册到分组）
from app.configs.definitions.platform import general
from app.configs.definitions.platform import security
from app.configs.definitions.platform import email


__all__ = [
    "general",
    "security",
    "email",
]
