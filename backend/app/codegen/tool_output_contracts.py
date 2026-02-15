"""
CRUD Generator Tool 输出契约

定义 11 个 CRUD Generator Tool 的 JSON 输出结构。
供后端 Executor 和前端解析层参考，减少联调歧义。

前端解析入口：SSE tool_call 事件的 output 字段，JSON.parse 后按 tool name 分发。

使用方式：
  后端 —— 类型提示 + 测试断言
  前端 —— TypeScript interface 参照本文件同步定义
"""

from __future__ import annotations

from typing import Any, TypedDict


# ============================================================
# 1. crud_generate_config
# ============================================================
# AI 返回纯 JSON 文本，符合 CrudConfig schema。
# 前端：JSON.parse → 合并到 Wizard 配置表单（渐进填充 + 高亮动画）

class GenerateConfigOutput(TypedDict):
    """crud_generate_config 输出

    AI 直接返回 CrudConfig JSON 字符串（非嵌套包装）。
    字段结构参见 app.codegen.schemas.CrudConfig。

    前端解析伪代码::

        const raw = JSON.parse(toolOutput)
        // raw 即 CrudConfig 对象
        wizardStore.mergeConfig(raw)
        highlightChangedFields(raw)
    """
    module: str
    table_name: str
    display_name: str
    display_name_en: str
    scope: str  # "admin" | "tenant" | "both"
    parent_menu: str
    fields: list[dict[str, Any]]  # FieldConfig[]
    # 可选字段
    # enums: list[dict]
    # relations: list[dict]
    # layout: dict
    # list_config: dict
    # form_config: dict
    # search_config: dict
    # permissions: dict
    # api_config: dict


# ============================================================
# 2. crud_preview_code
# ============================================================

class PreviewFileItem(TypedDict, total=False):
    """单个文件预览（来自 CrudWriter.preview()）"""
    path: str            # 相对路径，如 "backend/app/models/tenant/notice.py"
    size: int            # 字节数
    exists: bool         # 文件是否已存在
    is_i18n: bool        # 是否为 i18n 文件（merge 模式）
    operation: str       # "create" | "merge" | "conflict"
    content: str         # 仅 include_content=True 时有值


class PreviewCodeOutput(TypedDict):
    """crud_preview_code 输出

    前端解析伪代码::

        const data = JSON.parse(toolOutput)
        fileList.value = data.files
        stats.value = { new: data.total_new, conflict: data.total_conflict }
    """
    files: list[PreviewFileItem]
    total_new: int
    total_conflict: int


# ============================================================
# 3. crud_generate_files (两种输出)
# ============================================================

class GenerateFilesPreview(TypedDict):
    """crud_generate_files 未确认时的输出（requires_confirmation 流程）

    前端解析伪代码::

        const data = JSON.parse(toolOutput)
        if (data.requires_confirmation) {
          // SSE confirmation_request 事件已自动推送
          // 前端展示确认卡片，含 files 列表和 message
          showConfirmationCard(data)
        }
    """
    requires_confirmation: bool  # 固定 True
    files: list[PreviewFileItem]
    total_new: int
    total_conflict: int
    message: str  # 人类可读的摘要


class GenerateFilesResult(TypedDict):
    """crud_generate_files 确认后的输出

    前端解析伪代码::

        const data = JSON.parse(toolOutput)
        if (data.success) {
          notification.success(`写入 ${data.total_written} 个文件`)
          // 可选：刷新文件树
        }
    """
    success: bool           # 固定 True
    written: list[str]      # 写入的文件路径列表
    skipped: list[str]      # 跳过的文件路径列表
    merged: list[str]       # 合并的文件路径列表
    errors: list[str]       # 错误信息列表
    total_written: int
    total_skipped: int
    total_merged: int
    total_errors: int


# ============================================================
# 4. crud_translate_i18n
# ============================================================
# AI 返回翻译后的 JSON 对象（纯 JSON 文本）。
# 前端：JSON.parse → 覆盖/合并对应语言文件内容

class TranslateI18nOutput(TypedDict):
    """crud_translate_i18n 输出

    AI 直接返回翻译后的 i18n JSON 对象。
    结构与输入的 source_json 相同，值为目标语言。

    前端解析伪代码::

        const translated = JSON.parse(toolOutput)
        // translated 是与 source_json 同结构的对象，值为目标语言
        i18nStore.mergeTranslation(targetLang, translated)
    """
    # 动态 key-value，与 source_json 结构相同
    # 例: { "title": "Title", "description": "Description" }


# ============================================================
# 5. crud_suggest_fields
# ============================================================
# AI 返回 JSON，包含推荐字段列表

class SuggestedField(TypedDict, total=False):
    """推荐的单个字段"""
    name: str
    type: str           # "string" | "integer" | "boolean" | "datetime" | "text" | "decimal" | "json"
    label_zh: str
    label_en: str
    required: bool
    max_length: int
    description: str
    reason: str         # AI 推荐理由


class SuggestedEnum(TypedDict, total=False):
    """推荐的枚举定义"""
    name: str
    values: list[dict[str, Any]]  # [{"value": "draft", "label_zh": "草稿", "label_en": "Draft"}]
    reason: str


class SuggestFieldsOutput(TypedDict):
    """crud_suggest_fields 输出

    前端解析伪代码::

        const data = JSON.parse(toolOutput)
        suggestedFields.value = data.fields
        suggestedEnums.value = data.enums || []
        // 用户勾选后合并到配置
    """
    fields: list[SuggestedField]
    enums: list[SuggestedEnum]
    relations: list[dict[str, Any]]  # 推荐的关联关系


# ============================================================
# 6. crud_generate_slot
# ============================================================
# AI 返回 Vue template 代码片段

class GenerateSlotOutput(TypedDict):
    """crud_generate_slot 输出

    AI 返回 JSON 包含 Vue template 代码。

    前端解析伪代码::

        const data = JSON.parse(toolOutput)
        slotEditor.value = data.template
        // 用户可在 Monaco 编辑器中预览和修改
    """
    template: str       # Vue <template> 代码片段
    description: str    # 代码说明
    imports: list[str]  # 需要额外导入的组件/工具


# ============================================================
# 7. crud_recommend_style
# ============================================================
# AI 返回布局和样式推荐

class RecommendStyleOutput(TypedDict):
    """crud_recommend_style 输出

    前端解析伪代码::

        const data = JSON.parse(toolOutput)
        configForm.layout.variant = data.layout_variant
        configForm.list_config = { ...configForm.list_config, ...data.list_config }
        configForm.form_config = { ...configForm.form_config, ...data.form_config }
    """
    layout_variant: str     # "standard" | "card_list" | "master_detail" | "tree_table" | "kanban" | "timeline"
    reason: str             # 推荐理由
    list_config: dict[str, Any]   # 列表页配置建议 (row_height, stripe, show_index 等)
    form_config: dict[str, Any]   # 表单配置建议 (columns, label_width 等)
    style_tokens: dict[str, Any]  # 样式 Token 建议 (primary_color, density 等)


# ============================================================
# 8. crud_analyze_intent
# ============================================================
# AI 返回多实体分析结果

class AnalyzedEntity(TypedDict, total=False):
    """分析出的单个领域实体"""
    name: str               # 实体名 (snake_case)
    display_name: str       # 中文名
    display_name_en: str    # 英文名
    description: str        # 实体描述
    fields: list[dict[str, Any]]      # 核心字段列表 (简化版)
    relations: list[dict[str, Any]]   # 与其他实体的关系


class AnalyzeIntentOutput(TypedDict):
    """crud_analyze_intent 输出

    前端解析伪代码::

        const data = JSON.parse(toolOutput)
        entityList.value = data.entities
        // 用户选择一个实体 → 调用 crud_generate_config 生成完整配置
        if (data.suggested_order) {
          buildOrder.value = data.suggested_order
        }
    """
    entities: list[AnalyzedEntity]
    suggested_order: list[str]  # 建议的开发顺序 (按依赖排序)
    summary: str                # 业务分析摘要


# ============================================================
# AI 错误输出（所有 AI 工具共用）
# ============================================================

class AIErrorOutput(TypedDict):
    """AI 工具无法执行时的输出

    前端解析伪代码::

        const data = JSON.parse(toolOutput)
        if (data.error) {
          notification.warning(data.error)
          if (data.hint) showHint(data.hint)
        }
    """
    error: str
    hint: str


# ============================================================
# 工具名 → 输出类型映射（文档用）
# ============================================================

TOOL_OUTPUT_MAP: dict[str, str] = {
    "crud_generate_config": "GenerateConfigOutput (CrudConfig JSON)",
    "crud_preview_code": "PreviewCodeOutput",
    "crud_generate_files": "GenerateFilesPreview (未确认) | GenerateFilesResult (已确认)",
    "crud_translate_i18n": "TranslateI18nOutput (翻译后的 i18n JSON)",
    "crud_suggest_fields": "SuggestFieldsOutput",
    "crud_generate_slot": "GenerateSlotOutput",
    "crud_recommend_style": "RecommendStyleOutput",
    "crud_analyze_intent": "AnalyzeIntentOutput",
}


__all__ = [
    "GenerateConfigOutput",
    "PreviewCodeOutput",
    "PreviewFileItem",
    "GenerateFilesPreview",
    "GenerateFilesResult",
    "TranslateI18nOutput",
    "SuggestedField",
    "SuggestedEnum",
    "SuggestFieldsOutput",
    "GenerateSlotOutput",
    "RecommendStyleOutput",
    "AnalyzedEntity",
    "AnalyzeIntentOutput",
    "AIErrorOutput",
    "TOOL_OUTPUT_MAP",
]
