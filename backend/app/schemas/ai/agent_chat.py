"""
智能体对话相关 Schema / Agent Chat Schema

定义对话请求和响应数据结构
Defines chat request and response data structures.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.ai.runtime.contracts import PAGE_CONTEXT_KEY
from app.core.i18n import _

InteractionMode = Literal["confirm", "trusted_auto"]


class ChatAttachment(BaseModel):
    """对话附件（图片/文件/音频/视频） / Chat attachment (image/file/audio/video)."""

    attachment_id: int | None = Field(
        None,
        description="Attachment ID for refreshing signed URLs / 用于刷新签名 URL 的附件 ID",
    )
    type: Literal["image", "file", "audio", "video"] = Field(
        ...,
        description=_("agent_chat.field.attachment_type"),
    )
    url: str = Field(
        ...,
        description=_("agent_chat.field.attachment_url"),
    )
    name: str | None = Field(
        None,
        description=_("agent_chat.field.attachment_name"),
    )
    mime_type: str | None = Field(
        None,
        description=_("agent_chat.field.attachment_mime_type"),
    )


class ImageParams(BaseModel):
    """图像生成参数 / Image generation params."""

    size: str = Field("1024x1024", description=_("agent_chat.field.image_size"))
    quality: str = Field("standard", description=_("agent_chat.field.image_quality"))
    style: str = Field("vivid", description=_("agent_chat.field.image_style"))
    n: int = Field(1, ge=1, le=4, description=_("agent_chat.field.image_n"))


class TrustPolicyRef(BaseModel):
    """运行时信任策略引用 / Runtime trust policy reference."""

    policy_ids: list[int] | None = Field(
        None,
        description="Resolved policy ids / 已解析的策略 ID",
    )
    allowed_tool_names: list[str] | None = Field(
        None,
        description="Allowed tool names / 允许的工具名",
    )
    tool_families: list[str] | None = Field(
        None,
        description="Allowed tool families / 允许的工具族",
    )
    risk_level_cap: str | None = Field(
        None,
        description="Highest auto-approved action level / 自动批准的最高风险级别",
    )


class AgentChatRequest(BaseModel):
    """对话请求 / Agent chat request."""

    message: str = Field(
        "",
        min_length=0,
        max_length=32000,
        description=_("agent_chat.field.message"),
    )
    messages: list[str] | None = Field(
        None,
        max_length=10,
        description=_("agent_chat.field.messages_batch"),
    )

    @model_validator(mode="after")
    def require_message_or_messages(self) -> AgentChatRequest:
        msgs = self.messages or []
        single = (self.message or "").strip()
        has_interaction = bool(self.interaction_updates)
        if not msgs and not single and not has_interaction:
            raise ValueError("message, messages, or interaction_updates required")
        if msgs and any(not (m or "").strip() for m in msgs):
            raise ValueError("messages must not contain empty strings")
        return self

    conversation_id: int | None = Field(
        None,
        description=_("agent_chat.field.conversation_id"),
    )
    variables: dict[str, Any] | None = Field(
        None,
        description=_("agent_chat.field.variables"),
    )
    page_context: PageContext | None = Field(
        None,
        description=_("agent_chat.field.page_context"),
    )
    knowledge_base_ids: list[int] | None = Field(
        None,
        description=_("agent_chat.field.knowledge_base_ids"),
    )
    consented_actions: list[str] | None = Field(
        None,
        description=_("agent_chat.field.consented_actions"),
    )
    attachments: list[ChatAttachment] | None = Field(
        None,
        description=_("agent_chat.field.attachments"),
    )
    trust_policy_ref: TrustPolicyRef | None = Field(
        None,
        description="Runtime trust policy reference / 运行时信任策略引用",
    )
    image_params: ImageParams | None = Field(
        None,
        description=_("agent_chat.field.image_params"),
    )
    page_session_id: str | None = Field(
        None,
        max_length=64,
        description=_("agent_chat.field.page_session_id"),
    )
    route_source: str | None = Field(
        None,
        max_length=32,
        description="Frontend route source hint (e.g. mention)",
    )
    interaction_updates: list[InteractionUpdate] | None = Field(
        None,
        description="Client-side interaction state updates to persist before processing the next turn",
    )


class UpdateConversationTitleRequest(BaseModel):
    """更新对话标题请求 / Update conversation title request."""

    title: str = Field(
        "",
        min_length=0,
        max_length=200,
        description=_("agent_chat.field.conversation_title"),
    )


class AgentChatResponse(BaseModel):
    """对话响应（非流式） / Agent chat response (non-streaming)."""

    conversation_id: int = Field(
        ...,
        description=_("agent_chat.field.conversation_id"),
    )
    message: str = Field(
        ...,
        description=_("agent_chat.field.reply_message"),
    )
    tool_calls: list[dict[str, Any]] | None = Field(
        None,
        description=_("agent_chat.field.tool_calls"),
    )
    total_tokens: int = Field(
        0,
        description=_("agent_chat.field.total_tokens"),
    )
    duration_ms: int = Field(
        0,
        description=_("agent_chat.field.duration_ms"),
    )
    effective_knowledge_base_ids: list[int] | None = Field(
        None,
        description="Effective knowledge base IDs applied to this turn after sanitization",
    )
    dropped_knowledge_base_ids: list[int] | None = Field(
        None,
        description="Client-selected knowledge base IDs dropped during sanitization",
    )
    context_compacted: bool = Field(
        False,
        description="Whether compacted context was used during this turn",
    )
    memory_recalled: bool = Field(
        False,
        description="Whether long-term memory recall was injected during this turn",
    )
    prune_stats: dict[str, Any] | None = Field(
        None,
        description="Prompt-only pruning diagnostics for this turn",
    )
    rag_source_kinds: list[str] = Field(
        default_factory=list,
        description="Kinds of RAG sources used in this turn",
    )
    context_diagnostics: dict[str, Any] | None = Field(
        None,
        description="Context diagnostics for this turn / 本轮上下文诊断",
    )
    last_run_summary: dict[str, Any] | None = Field(
        None,
        description="Execution summary for this turn / 本轮执行摘要",
    )


class InteractionUpdate(BaseModel):
    kind: Literal["action_buttons", "pending_confirmation", "pending_consent"]
    action: str | None = None
    auto_approved: bool | None = None
    rejected: bool | None = None
    table: str | None = None
    tool_name: str | None = None
    value: str | None = None


class UpdateConversationInteractionStateRequest(BaseModel):
    updates: list[InteractionUpdate] = Field(default_factory=list)


class ThinSurfaceSummary(BaseModel):
    """Surface summary for thin page context / 薄页面上下文中的 surface 摘要。"""

    model_config = ConfigDict(extra="ignore")

    surface_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="UI surface id / UI surface 标识",
    )
    kind: Literal["page", "drawer", "modal", "dropdown", "popover"] = Field(
        ...,
        description="Surface kind / surface 类型",
    )
    title: str | None = Field(
        None,
        max_length=200,
        description="Surface title / surface 标题",
    )

    @field_validator("surface_id", mode="before")
    @classmethod
    def validate_surface_id(cls, value: Any) -> str:
        return _normalize_required_compact_text(
            value,
            field_name="surface_id",
            max_length=128,
        )


class ActiveFormSummary(BaseModel):
    """Active form summary for thin page context / 活跃表单薄摘要。"""

    model_config = ConfigDict(extra="ignore")

    form_session_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Form session id / 表单会话 ID",
    )
    entity_name: str | None = Field(
        None,
        max_length=128,
        description="Entity name / 实体名",
    )
    mode: Literal["create", "edit", "view", "unknown"] = Field(
        "unknown",
        description="Form mode / 表单模式",
    )
    stage: Literal[
        "opening",
        "ready",
        "filled_partial",
        "validating",
        "ready_to_submit",
        "submitting",
        "submitted",
        "failed",
    ] = Field(
        "ready",
        description="Form stage / 表单阶段",
    )
    record_id: int | str | None = Field(
        None,
        description="Editing record id / 编辑目标记录 ID",
    )
    remaining_required_fields: list[str] = Field(
        default_factory=list,
        description="Remaining required fields / 剩余必填字段",
    )
    can_submit: bool = Field(
        False,
        description="Whether the form can submit / 是否可提交",
    )
    submit_policy: Literal["auto", "confirm", "off"] = Field(
        "confirm",
        description="Submit policy / 提交策略",
    )

    @field_validator("form_session_id", mode="before")
    @classmethod
    def validate_form_session_id(cls, value: Any) -> str:
        return _normalize_required_compact_text(
            value,
            field_name="form_session_id",
            max_length=128,
        )

    @model_validator(mode="after")
    def normalize_remaining_required_fields(self) -> ActiveFormSummary:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in self.remaining_required_fields:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text[:128])
            if len(normalized) >= 32:
                break
        self.remaining_required_fields = normalized
        return self


class NavigationCatalogEntry(BaseModel):
    """Compact navigation entry for thin page_data / 薄 page_data 的紧凑导航条目。"""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Navigation title / 导航标题",
    )
    path: str = Field(
        ...,
        min_length=1,
        max_length=240,
        description="Navigation path / 导航路径",
    )
    page_key: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Navigation page key / 导航页面键",
    )
    description: str | None = Field(
        None,
        max_length=240,
        description="Navigation description / 导航描述",
    )
    category: str | None = Field(
        None,
        max_length=120,
        description="Navigation category / 导航分类",
    )
    endpoint: str | None = Field(
        None,
        max_length=240,
        description="Navigation endpoint / 导航端点",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Navigation keywords / 导航关键词",
    )
    capabilities: list[str] = Field(
        default_factory=list,
        description="Navigation capabilities / 导航能力标签",
    )
    breadcrumb: list[str] = Field(
        default_factory=list,
        description="Navigation breadcrumb / 导航面包屑",
    )

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: Any) -> str:
        return _normalize_required_compact_text(
            value,
            field_name="title",
            max_length=200,
        )

    @field_validator("path", mode="before")
    @classmethod
    def validate_path(cls, value: Any) -> str:
        return _normalize_required_compact_text(
            value,
            field_name="path",
            max_length=240,
        )

    @field_validator("page_key", mode="before")
    @classmethod
    def validate_page_key(cls, value: Any) -> str:
        return _normalize_required_compact_text(
            value,
            field_name="page_key",
            max_length=200,
        )

    @model_validator(mode="after")
    def normalize_entry(self) -> NavigationCatalogEntry:
        self.title = self.title.strip()[:200]
        self.path = self.path.strip()[:240]
        self.page_key = self.page_key.strip()[:200]
        if self.description is not None:
            description = self.description.strip()
            self.description = description[:240] if description else None
        if self.category is not None:
            category = self.category.strip()
            self.category = category[:120] if category else None
        if self.endpoint is not None:
            endpoint = self.endpoint.strip()
            self.endpoint = endpoint[:240] if endpoint else None
        self.keywords = _normalize_compact_string_list(self.keywords, max_items=12)
        self.capabilities = _normalize_compact_string_list(
            self.capabilities,
            max_items=12,
        )
        self.breadcrumb = _normalize_compact_string_list(self.breadcrumb, max_items=8)
        return self


class NavigationContext(BaseModel):
    """Compact navigation context for thin page_data / 薄 page_data 的导航上下文。"""

    model_config = ConfigDict(extra="ignore")

    breadcrumb: list[str] = Field(
        default_factory=list,
        description="Navigation breadcrumb / 导航面包屑",
    )
    endpoint: str | None = Field(
        None,
        max_length=240,
        description="Current endpoint / 当前端点",
    )
    page_key: str | None = Field(
        None,
        max_length=200,
        description="Current page key / 当前页面键",
    )
    path: str | None = Field(
        None,
        max_length=240,
        description="Current path / 当前路径",
    )

    @model_validator(mode="after")
    def normalize_context(self) -> NavigationContext:
        self.breadcrumb = _normalize_compact_string_list(self.breadcrumb, max_items=8)
        if self.endpoint is not None:
            endpoint = self.endpoint.strip()
            self.endpoint = endpoint[:240] if endpoint else None
        if self.page_key is not None:
            page_key = self.page_key.strip()
            self.page_key = page_key[:200] if page_key else None
        if self.path is not None:
            path = self.path.strip()
            self.path = path[:240] if path else None
        return self


class SearchInputAffordance(BaseModel):
    """Visible search/filter input affordance / 可见搜索或筛选输入框摘要。"""

    model_config = ConfigDict(extra="ignore")

    locator: str = Field(
        ...,
        min_length=1,
        max_length=240,
        description="Runtime locator / 运行时 locator",
    )
    label: str | None = Field(
        None,
        max_length=200,
        description="Visible label / 可见标签",
    )
    placeholder: str | None = Field(
        None,
        max_length=200,
        description="Input placeholder / 输入框占位提示",
    )
    field_name: str | None = Field(
        None,
        max_length=120,
        description="Resolved field name / 解析到的字段名",
    )

    @field_validator("locator", mode="before")
    @classmethod
    def validate_locator(cls, value: Any) -> str:
        return _normalize_required_compact_text(
            value,
            field_name="locator",
            max_length=240,
        )

    @model_validator(mode="after")
    def normalize_affordance(self) -> SearchInputAffordance:
        self.locator = self.locator.strip()[:240]
        if self.label is not None:
            label = self.label.strip()
            self.label = label[:200] if label else None
        if self.placeholder is not None:
            placeholder = self.placeholder.strip()
            self.placeholder = placeholder[:200] if placeholder else None
        if self.field_name is not None:
            field_name = self.field_name.strip()
            self.field_name = field_name[:120] if field_name else None
        return self


class VisibleTableAffordance(BaseModel):
    """Visible table affordance / 可见表格摘要。"""

    model_config = ConfigDict(extra="ignore")

    locator: str = Field(
        ...,
        min_length=1,
        max_length=240,
        description="Runtime locator / 运行时 locator",
    )
    label: str | None = Field(
        None,
        max_length=200,
        description="Visible table label / 可见表格标签",
    )
    row_count: int | None = Field(
        None,
        ge=0,
        description="Visible row count / 可见行数",
    )
    column_count: int | None = Field(
        None,
        ge=0,
        description="Visible column count / 可见列数",
    )

    @field_validator("locator", mode="before")
    @classmethod
    def validate_locator(cls, value: Any) -> str:
        return _normalize_required_compact_text(
            value,
            field_name="locator",
            max_length=240,
        )

    @model_validator(mode="after")
    def normalize_affordance(self) -> VisibleTableAffordance:
        self.locator = self.locator.strip()[:240]
        if self.label is not None:
            label = self.label.strip()
            self.label = label[:200] if label else None
        if self.row_count is not None:
            self.row_count = max(int(self.row_count), 0)
        if self.column_count is not None:
            self.column_count = max(int(self.column_count), 0)
        return self


class PageContextPageData(BaseModel):
    """Summary-first page data extension / summary-first 页面扩展数据。"""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_available_menus(cls, value: Any) -> Any:
        if isinstance(value, dict) and "available_menus" in value:
            raise ValueError(
                "available_menus is not allowed in page_data; use navigation_catalog"
            )
        return value

    locale: str | None = Field(
        None,
        max_length=32,
        description="Page-data locale / page_data 语言",
    )
    entity_description: str | None = Field(
        None,
        max_length=240,
        description="Entity description summary / 实体描述摘要",
    )
    navigation_catalog: list[NavigationCatalogEntry] = Field(
        default_factory=list,
        description="Compact navigation catalog / 紧凑导航目录",
    )
    navigation_context: NavigationContext | None = Field(
        None,
        description="Compact navigation context / 紧凑导航上下文",
    )
    search_inputs: list[SearchInputAffordance] | None = Field(
        None,
        description="Visible search/filter inputs / 可见搜索或筛选输入框摘要",
    )
    visible_tables: list[VisibleTableAffordance] | None = Field(
        None,
        description="Visible tables / 可见表格摘要",
    )

    @field_validator("navigation_catalog", mode="before")
    @classmethod
    def sanitize_navigation_catalog(
        cls,
        value: Any,
    ) -> list[NavigationCatalogEntry | dict[str, Any]]:
        if not isinstance(value, list):
            return []

        normalized: list[NavigationCatalogEntry | dict[str, Any]] = []
        for item in value:
            try:
                entry = NavigationCatalogEntry.model_validate(item)
            except ValidationError:
                continue
            normalized.append(entry)
        return normalized

    @field_validator("search_inputs", mode="before")
    @classmethod
    def sanitize_search_inputs(
        cls,
        value: Any,
    ) -> list[SearchInputAffordance | dict[str, Any]] | None:
        if not isinstance(value, list):
            return None

        normalized: list[SearchInputAffordance | dict[str, Any]] = []
        for item in value:
            try:
                affordance = SearchInputAffordance.model_validate(item)
            except ValidationError:
                continue
            normalized.append(affordance)
        return normalized

    @field_validator("visible_tables", mode="before")
    @classmethod
    def sanitize_visible_tables(
        cls,
        value: Any,
    ) -> list[VisibleTableAffordance | dict[str, Any]] | None:
        if not isinstance(value, list):
            return None

        normalized: list[VisibleTableAffordance | dict[str, Any]] = []
        for item in value:
            try:
                affordance = VisibleTableAffordance.model_validate(item)
            except ValidationError:
                continue
            normalized.append(affordance)
        return normalized

    @model_validator(mode="after")
    def normalize_page_data(self) -> PageContextPageData:
        if self.locale is not None:
            locale = self.locale.strip()
            self.locale = locale[:32] if locale else None
        if self.entity_description is not None:
            entity_description = self.entity_description.strip()
            self.entity_description = (
                entity_description[:240] if entity_description else None
            )

        normalized_catalog: list[NavigationCatalogEntry] = []
        seen_catalog_keys: set[tuple[str, str]] = set()
        for entry in self.navigation_catalog:
            dedupe_key = (entry.page_key, entry.path)
            if dedupe_key in seen_catalog_keys:
                continue
            seen_catalog_keys.add(dedupe_key)
            normalized_catalog.append(entry)
            if len(normalized_catalog) >= 32:
                break
        self.navigation_catalog = normalized_catalog
        normalized_search_inputs: list[SearchInputAffordance] = []
        seen_search_locators: set[str] = set()
        for affordance in self.search_inputs or []:
            dedupe_key = affordance.locator
            if dedupe_key in seen_search_locators:
                continue
            seen_search_locators.add(dedupe_key)
            normalized_search_inputs.append(affordance)
            if len(normalized_search_inputs) >= 8:
                break
        self.search_inputs = normalized_search_inputs or None

        normalized_visible_tables: list[VisibleTableAffordance] = []
        seen_table_locators: set[str] = set()
        for affordance in self.visible_tables or []:
            dedupe_key = affordance.locator
            if dedupe_key in seen_table_locators:
                continue
            seen_table_locators.add(dedupe_key)
            normalized_visible_tables.append(affordance)
            if len(normalized_visible_tables) >= 8:
                break
        self.visible_tables = normalized_visible_tables or None

        if self.navigation_context and not (
            self.navigation_context.breadcrumb
            or self.navigation_context.endpoint
            or self.navigation_context.page_key
            or self.navigation_context.path
        ):
            self.navigation_context = None

        return self


def _normalize_compact_string_list(
    values: list[str],
    *,
    max_items: int,
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        dedupe_key = text.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(text[:200])
        if len(normalized) >= max_items:
            break
    return normalized


def _normalize_required_compact_text(
    value: Any,
    *,
    field_name: str,
    max_length: int,
) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text[:max_length]


class PageContext(BaseModel):
    """统一页面上下文（贯穿 Router 路由决策与标准 Agent 聊天执行链） / Unified page context (Router + Agent chat chain)."""

    model_config = ConfigDict(extra="ignore")

    page_key: str = Field(
        ...,
        description=_("agent_chat.field.page_key"),
        min_length=1,
        max_length=200,
    )
    page_title: str | None = Field(
        None,
        description=_("agent_chat.field.page_title"),
        max_length=200,
    )
    locale: str | None = Field(
        None,
        max_length=32,
        description="Frontend runtime locale / 前端运行时语言",
    )
    page_session_id: str | None = Field(
        None,
        max_length=64,
        description="Page session id / 页面会话 ID",
    )
    ui_epoch: int | None = Field(
        None,
        ge=0,
        description="UI epoch / UI 版本序号",
    )
    active_surface_id: str | None = Field(
        None,
        max_length=128,
        description="Active surface id / 当前活跃 surface",
    )
    active_form_session_id: str | None = Field(
        None,
        max_length=128,
        description="Active form session id / 当前活跃表单会话",
    )
    surface_stack: list[ThinSurfaceSummary] = Field(
        default_factory=list,
        description="Current UI surface stack / 当前 UI surface 栈",
    )
    active_form_summary: ActiveFormSummary | None = Field(
        None,
        description="Active form summary / 活跃表单摘要",
    )
    page_data: PageContextPageData | None = Field(
        None,
        description="Compact page data / 紧凑页面数据",
    )

    @field_validator("page_key", mode="before")
    @classmethod
    def validate_page_key(cls, value: Any) -> str:
        return _normalize_required_compact_text(
            value,
            field_name="page_key",
            max_length=200,
        )

    @model_validator(mode="after")
    def normalize_context(self) -> PageContext:
        self.page_key = self.page_key.strip()[:200]
        if self.page_title is not None:
            title = self.page_title.strip()
            self.page_title = title[:200] if title else None
        if self.locale is not None:
            locale = self.locale.strip()
            self.locale = locale[:32] if locale else None
        if self.page_session_id is not None:
            session_id = self.page_session_id.strip()
            self.page_session_id = session_id[:64] if session_id else None
        if self.active_surface_id is not None:
            active_surface_id = self.active_surface_id.strip()
            self.active_surface_id = (
                active_surface_id[:128] if active_surface_id else None
            )
        if self.active_form_session_id is not None:
            active_form_session_id = self.active_form_session_id.strip()
            self.active_form_session_id = (
                active_form_session_id[:128] if active_form_session_id else None
            )

        normalized_stack: list[ThinSurfaceSummary] = []
        seen_surface_ids: set[str] = set()
        for surface in self.surface_stack:
            surface_id = str(surface.surface_id or "").strip()[:128]
            if not surface_id or surface_id in seen_surface_ids:
                continue
            seen_surface_ids.add(surface_id)
            normalized_stack.append(
                surface.model_copy(
                    update={
                        "surface_id": surface_id,
                        "title": (
                            str(surface.title).strip()[:200]
                            if isinstance(surface.title, str) and surface.title.strip()
                            else None
                        ),
                    }
                )
            )
            if len(normalized_stack) >= 12:
                break
        self.surface_stack = normalized_stack

        if self.ui_epoch is not None:
            self.ui_epoch = max(int(self.ui_epoch), 0)

        if self.active_form_summary:
            if self.active_form_summary.entity_name:
                self.active_form_summary = self.active_form_summary.model_copy(
                    update={
                        "entity_name": self.active_form_summary.entity_name.strip()[
                            :128
                        ]
                    }
                )
            if self.active_form_session_id:
                self.active_form_summary = self.active_form_summary.model_copy(
                    update={"form_session_id": self.active_form_session_id}
                )
            elif not self.active_form_session_id:
                self.active_form_session_id = self.active_form_summary.form_session_id

        if self.page_data and not (
            self.page_data.locale
            or self.page_data.entity_description
            or self.page_data.navigation_catalog
            or self.page_data.navigation_context
            or self.page_data.search_inputs
            or self.page_data.visible_tables
        ):
            self.page_data = None

        if self.active_surface_id and self.surface_stack:
            if self.active_surface_id not in {
                surface.surface_id for surface in self.surface_stack
            }:
                self.active_surface_id = self.surface_stack[-1].surface_id
        elif not self.active_surface_id and self.surface_stack:
            self.active_surface_id = self.surface_stack[-1].surface_id

        return self

    @classmethod
    def normalize(cls, value: Any) -> dict[str, Any] | None:
        if not value:
            return None

        if isinstance(value, cls):
            page_context = value
        elif isinstance(value, dict):
            try:
                page_context = cls.model_validate(value)
            except ValidationError:
                return None
        else:
            return None

        return page_context.model_dump(exclude_none=True)

    @classmethod
    def normalize_variables(
        cls,
        variables: dict[str, Any] | None,
        page_context: Any = None,
    ) -> dict[str, Any] | None:
        """Normalize request variables after retiring page-awareness.

        ``page_context`` remains in schemas for backwards-compatible request
        parsing, but AI dialogue must not smuggle page runtime state into the
        execution variables anymore.
        """
        normalized_variables = dict(variables or {})
        del page_context
        normalized_variables.pop(PAGE_CONTEXT_KEY, None)

        return normalized_variables or None


class AgentRouteRequest(BaseModel):
    """智能路由请求 / Agent route request."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=32000,
        description=_("agent_chat.field.message"),
    )
    conversation_id: int | None = Field(
        None,
        description=_("agent_chat.field.conversation_id"),
    )
    page_context: PageContext | None = Field(
        None,
        description=_("agent_chat.field.page_context"),
    )
    pinned_agent_id: int | None = Field(
        None,
        description=_("agent_chat.field.pinned_agent_id"),
    )
    force_reroute: bool = Field(
        False,
        description="Force rerouting even when the conversation is already bound to an agent / 即使当前对话已绑定智能体也强制重新路由",
    )
    has_image_attachments: bool = Field(
        False,
        description="Whether the user message includes image attachments / 是否包含图片附件",
    )
    has_audio_attachments: bool = Field(
        False,
        description="Whether the user message includes audio attachments / 是否包含音频附件",
    )
    has_video_attachments: bool = Field(
        False,
        description="Whether the user message includes video attachments / 是否包含视频附件",
    )
    has_file_attachments: bool = Field(
        False,
        description="Whether the user message includes generic file attachments / 是否包含通用文件附件",
    )


class AgentRouteResponse(BaseModel):
    """智能路由响应 / Agent route response."""

    agent_id: int = Field(
        ...,
        description=_("agent_chat.field.routed_agent_id"),
    )
    agent_name: str = Field(
        ...,
        description=_("agent_chat.field.routed_agent_name"),
    )
    confidence: float = Field(
        1.0,
        description=_("agent_chat.field.route_confidence"),
    )
    routed_by: str = Field(
        ...,
        description=_("agent_chat.field.routed_by"),
    )


__all__ = [
    "ChatAttachment",
    "ImageParams",
    "TrustPolicyRef",
    "PAGE_CONTEXT_KEY",
    "InteractionMode",
    "AgentChatRequest",
    "AgentChatResponse",
    "InteractionUpdate",
    "PageContext",
    "AgentRouteRequest",
    "AgentRouteResponse",
    "UpdateConversationInteractionStateRequest",
]
