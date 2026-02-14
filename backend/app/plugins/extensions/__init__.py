"""
插件扩展点接口

定义 5 种扩展点类型：
- AdapterPlugin: AI 适配器扩展
- ToolPlugin: 工具执行器扩展
- HookPlugin: 事件钩子扩展
- ApiPlugin: API 端点扩展
- SkillPlugin: Skill 类型扩展
"""

from app.plugins.extensions.adapter_plugin import AdapterPlugin
from app.plugins.extensions.api_plugin import ApiPlugin
from app.plugins.extensions.hook_plugin import HookPlugin
from app.plugins.extensions.skill_plugin import SkillPlugin
from app.plugins.extensions.tool_plugin import ToolPlugin

__all__ = [
    "AdapterPlugin",
    "ApiPlugin",
    "HookPlugin",
    "SkillPlugin",
    "ToolPlugin",
]
