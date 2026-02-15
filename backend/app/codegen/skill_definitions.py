"""
CRUD Generator — Skill 配置 & Tool 定义

定义 CRUD Generator 的 Skill 常量和 13 个 ToolDefinition。
由 SkillResolver 在解析 builtin_type="crud_generator" 时使用。

Tool 列表:
  1.  crud_generate_config        — NL → CrudConfig JSON
  2.  crud_preview_code           — 预览生成代码
  3.  crud_generate_files         — 写入文件 (requires_confirmation)
  4.  crud_translate_i18n         — 翻译 i18n
  5.  crud_suggest_fields         — 推荐字段
  6.  crud_generate_slot          — 生成 Slot 代码
  7.  crud_recommend_style        — 推荐样式
  8.  crud_analyze_intent         — 业务意图分析
"""

from __future__ import annotations

from app.ai.tools.types import ToolDefinition, ToolParameter
from app.enums.agent import ToolTypeEnum

# ============================================================
# 常量
# ============================================================

_TOOL_TYPE = ToolTypeEnum.CRUD_GENERATOR.value
_TIMEOUT = 120

# ============================================================
# Tool 1: crud_generate_config
# ============================================================

TOOL_GENERATE_CONFIG = ToolDefinition(
    name="crud_generate_config",
    description="根据自然语言描述生成 CrudConfig JSON 配置。输入业务需求描述，输出完整的 CRUD 模块配置。",
    tool_type=_TOOL_TYPE,
    parameters=[
        ToolParameter(
            name="description",
            type="string",
            description="业务需求描述，如：'我需要一个订单管理模块，包含订单编号、金额、状态、客户关联'",
            required=True,
        ),
        ToolParameter(
            name="context",
            type="string",
            description="额外上下文信息，如已有模块名、数据库表、命名偏好等",
            required=False,
        ),
    ],
    timeout=_TIMEOUT,
)

# ============================================================
# Tool 2: crud_preview_code
# ============================================================

TOOL_PREVIEW_CODE = ToolDefinition(
    name="crud_preview_code",
    description="预览将要生成的代码文件列表和内容摘要。输入 CrudConfig JSON，输出文件树、冲突检测和代码预览。",
    tool_type=_TOOL_TYPE,
    parameters=[
        ToolParameter(
            name="config",
            type="object",
            description="CrudConfig JSON 对象（由 crud_generate_config 生成）",
            required=True,
        ),
        ToolParameter(
            name="include_content",
            type="boolean",
            description="是否包含文件内容（默认 false，仅返回文件列表）",
            required=False,
            default=False,
        ),
    ],
    timeout=_TIMEOUT,
)

# ============================================================
# Tool 3: crud_generate_files
# ============================================================

TOOL_GENERATE_FILES = ToolDefinition(
    name="crud_generate_files",
    description="将生成的代码写入磁盘。首次调用返回预览清单供用户确认，用户确认后以 confirmed=true 再次调用执行写入。",
    tool_type=_TOOL_TYPE,
    parameters=[
        ToolParameter(
            name="config",
            type="object",
            description="CrudConfig JSON 对象",
            required=True,
        ),
        ToolParameter(
            name="confirmed",
            type="boolean",
            description="用户确认标志。首次调用不传或传 false，系统返回预览。用户确认后传 true 执行写入。",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="conflict_action",
            type="string",
            description="冲突处理策略",
            required=False,
            default="skip",
            enum=["skip", "overwrite", "merge"],
        ),
    ],
    timeout=_TIMEOUT,
)

# ============================================================
# Tool 4: crud_translate_i18n
# ============================================================

TOOL_TRANSLATE_I18N = ToolDefinition(
    name="crud_translate_i18n",
    description="将中文 i18n JSON 翻译为目标语言（默认英文）。保持 JSON 结构不变，仅翻译值。",
    tool_type=_TOOL_TYPE,
    parameters=[
        ToolParameter(
            name="source_json",
            type="object",
            description="中文 i18n JSON 对象",
            required=True,
        ),
        ToolParameter(
            name="target_language",
            type="string",
            description="目标语言代码（默认 en）",
            required=False,
            default="en",
        ),
    ],
    timeout=_TIMEOUT,
)

# ============================================================
# Tool 5: crud_suggest_fields
# ============================================================

TOOL_SUGGEST_FIELDS = ToolDefinition(
    name="crud_suggest_fields",
    description="根据模块名和已有字段列表，推荐应该追加的字段、枚举和关联关系。",
    tool_type=_TOOL_TYPE,
    parameters=[
        ToolParameter(
            name="module_name",
            type="string",
            description="模块名称，如 'order', 'product', 'customer'",
            required=True,
        ),
        ToolParameter(
            name="existing_fields",
            type="array",
            description="已有字段名列表，如 ['name', 'status', 'amount']",
            required=False,
        ),
    ],
    timeout=_TIMEOUT,
)

# ============================================================
# Tool 6: crud_generate_slot
# ============================================================

TOOL_GENERATE_SLOT = ToolDefinition(
    name="crud_generate_slot",
    description="生成自定义列渲染的 Vue template 代码片段。适用于需要特殊展示效果的列表字段。",
    tool_type=_TOOL_TYPE,
    parameters=[
        ToolParameter(
            name="field_name",
            type="string",
            description="目标字段名，如 'avatar', 'progress', 'tags'",
            required=True,
        ),
        ToolParameter(
            name="description",
            type="string",
            description="渲染效果描述，如 '显示为圆形头像+姓名'、'显示为进度条+百分比'",
            required=True,
        ),
    ],
    timeout=_TIMEOUT,
)

# ============================================================
# Tool 7: crud_recommend_style
# ============================================================

TOOL_RECOMMEND_STYLE = ToolDefinition(
    name="crud_recommend_style",
    description="根据模块特征推荐最佳的页面布局变体和样式配置。",
    tool_type=_TOOL_TYPE,
    parameters=[
        ToolParameter(
            name="module_name",
            type="string",
            description="模块名称",
            required=True,
        ),
        ToolParameter(
            name="field_count",
            type="integer",
            description="字段数量",
            required=False,
        ),
        ToolParameter(
            name="has_status",
            type="boolean",
            description="是否有状态流转",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="has_hierarchy",
            type="boolean",
            description="是否有层级关系",
            required=False,
            default=False,
        ),
    ],
    timeout=_TIMEOUT,
)

# ============================================================
# Tool 8: crud_analyze_intent
# ============================================================

TOOL_ANALYZE_INTENT = ToolDefinition(
    name="crud_analyze_intent",
    description="分析业务需求描述，识别领域实体及其关联关系，拆解为多个可独立生成的 CRUD 模块。",
    tool_type=_TOOL_TYPE,
    parameters=[
        ToolParameter(
            name="description",
            type="string",
            description="业务需求描述，如 '我需要一个电商后台，管理商品、订单、客户和物流'",
            required=True,
        ),
        ToolParameter(
            name="detail_level",
            type="string",
            description="分析详细程度",
            required=False,
            default="basic",
            enum=["basic", "detailed"],
        ),
    ],
    timeout=_TIMEOUT,
)



# ============================================================
# 聚合列表
# ============================================================

CRUD_TOOL_DEFINITIONS: list[ToolDefinition] = [
    TOOL_GENERATE_CONFIG,
    TOOL_PREVIEW_CODE,
    TOOL_GENERATE_FILES,
    TOOL_TRANSLATE_I18N,
    TOOL_SUGGEST_FIELDS,
    TOOL_GENERATE_SLOT,
    TOOL_RECOMMEND_STYLE,
    TOOL_ANALYZE_INTENT,
]
"""全部 8 个 CRUD Generator Tool 定义"""


# ============================================================
# Skill input_schema（多 Tool 格式，存入 DB）
# ============================================================


def build_skill_input_schema() -> dict:
    """构建 Skill 的 input_schema（多 Tool 结构）

    用于 Seed Data 迁移写入 skills.input_schema 字段。
    SkillResolver 解析时读取此结构。

    Returns:
        {
            "multi_tool": true,
            "tools": {
                "crud_generate_config": {
                    "description": "...",
                    "parameters": { JSON Schema }
                },
                ...
            }
        }
    """
    tools: dict = {}
    for tool_def in CRUD_TOOL_DEFINITIONS:
        tools[tool_def.name] = {
            "description": tool_def.description,
            "parameters": tool_def.input_schema,
        }

    return {
        "multi_tool": True,
        "tools": tools,
    }


__all__ = [
    "CRUD_TOOL_DEFINITIONS",
    "TOOL_GENERATE_CONFIG",
    "TOOL_PREVIEW_CODE",
    "TOOL_GENERATE_FILES",
    "TOOL_TRANSLATE_I18N",
    "TOOL_SUGGEST_FIELDS",
    "TOOL_GENERATE_SLOT",
    "TOOL_RECOMMEND_STYLE",
    "TOOL_ANALYZE_INTENT",
    "build_skill_input_schema",
]
