"""Tenant config definitions / 企业配置定义

Imports all tenant config modules to trigger config registration.
导入所有企业配置模块以触发配置注册
"""

# Import config modules (triggers config registration to groups) / 导入配置模块（触发注册）
from app.configs.definitions.tenant import branding, features, registration, security, storage

__all__ = [
    "branding",
    "security",
    "features",
    "registration",
    "storage",
]
