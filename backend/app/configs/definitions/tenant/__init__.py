"""
租户配置定义

导入所有租户配置模块以触发配置注册
"""

# 导入配置模块（触发配置注册到分组）
from app.configs.definitions.tenant import branding
from app.configs.definitions.tenant import security
from app.configs.definitions.tenant import features


__all__ = [
    "branding",
    "security",
    "features",
]
