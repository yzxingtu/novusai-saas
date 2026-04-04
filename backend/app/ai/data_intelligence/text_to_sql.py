"""
Natural Language to SQL Generator (TextToSQLGenerator)
自然语言转 SQL 生成器（TextToSQLGenerator）

Core component: Uses LLM to convert user natural language questions into safe PostgreSQL SELECT statements.
核心组件：使用 LLM 将用户自然语言问题转换为安全的 PostgreSQL SELECT 语句。

Security constraints / 安全约束：
- System Prompt strictly limits LLM to generate SELECT only / 严格限制只生成 SELECT
- Output goes through SQLSafetyValidator six-layer validation / 六重校验
- Max 2 retries on failure (with violation feedback) / 最多重试 2 次
- Returns friendly message instead of stack trace after 3 failures / 友好提示

Multi-turn conversation / 多轮对话：
- Supports conversation_history (last 3 rounds) / 支持对话历史
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.ai.data_intelligence.schema_provider import SchemaProvider, TableSchema
from app.ai.data_intelligence.sql_safety import SQLSafetyValidator
from app.ai.prompt_contracts import render_prompt_contract
from app.ai.text_semantics import extract_fenced_json_block, extract_first_json_object
from app.ai.types import ChatMessage
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.common import UserRoleEnum

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ai.gateway import AIGateway
    from app.models.ai.agent import Agent

logger = LogManager.get_logger("ai.data_intelligence")

# Max retry attempts (including first generation) / 最大重试次数（含首次生成）
MAX_GENERATE_ATTEMPTS = 3

# Recent rounds retained in multi-turn conversation / 多轮对话保留的最近轮数
MAX_CONVERSATION_ROUNDS = 3


# ============================================
# Data Structures / 数据结构
# ============================================


@dataclass
class GeneratedSQL:
    """LLM-generated SQL result / LLM 生成的 SQL 结果"""

    sql: str = ""
    explanation: str = ""
    visualization_suggestion: str = ""  # line/bar/pie/table/number  # 补充说明 / note
    confidence: float = 0.0  # 0.0 ~ 1.0
    success: bool = True
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "sql": self.sql,
            "explanation": self.explanation,
            "visualization_suggestion": self.visualization_suggestion,
            "confidence": self.confidence,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class ConversationRound:
    """One conversation round (for multi-turn context) / 一轮对话记录"""

    question: str
    sql: str
    explanation: str = ""


# ============================================
# TextToSQLGenerator / 文本转 SQL 生成器
# ============================================


class TextToSQLGenerator:
    """
    Natural Language to SQL Generator / 自然语言转 SQL 生成器

    Uses LLM to convert user questions into PostgreSQL SELECT statements,
    with multi-layer safety validation, multi-turn conversation and failure retry support.
    使用 LLM 将用户问题转换为 PostgreSQL SELECT 语句，
    经过多重安全校验，支持多轮对话和失败重试。
    """

    def __init__(self, gateway: AIGateway, db: AsyncSession):
        """
        Args:
            gateway: AI gateway (for calling LLM) / AI 网关
            db: Database session (for getting schema) / 数据库会话
        """
        self.gateway = gateway
        self.db = db
        self._schema_provider = SchemaProvider()

    async def generate(
        self,
        question: str,
        tenant_id: int,
        agent: Agent,
        conversation_history: list[ConversationRound] | None = None,
        permissions: set[str] | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
    ) -> GeneratedSQL:
        """
        Convert natural language question to SQL.
        将自然语言问题转为 SQL。

        Args:
            question: User's natural language question / 用户的自然语言问题
            tenant_id: Tenant ID / 企业 ID
            agent: Agent (contains model config) / 智能体
            conversation_history: Multi-turn conversation history (last N rounds) / 多轮对话历史
            permissions: User RBAC permission code set (for table-level filtering) / RBAC 权限码集合
            user_role: User role / 用户角色

        Returns:
            GeneratedSQL generation result / 生成结果
        """
        # 1. Get schema (filter by RBAC permissions + question keywords) / 获取 schema
        schema = await self._schema_provider.get_schema(
            self.db,
            tenant_id,
            question,
            permissions=permissions,
            user_role=user_role,
        )

        if not schema:
            return GeneratedSQL(
                success=False,
                error=_("data_intelligence.generator.no_relevant_tables"),
            )

        # 2. Get allowed table name set (after RBAC filtering, for subsequent safety validation) / 获取允许的表名集合
        allowed_tables = await self._schema_provider.get_allowed_table_names(
            db=self.db,
            permissions=permissions,
            user_role=user_role,
            tenant_id=tenant_id,
        )

        # 3. Build message list / 构建消息列表
        messages = self._build_messages(
            question=question,
            schema=schema,
            conversation_history=conversation_history,
        )

        # 4. Generate + validate + retry loop / 生成 + 校验 + 重试循环
        for attempt in range(MAX_GENERATE_ATTEMPTS):
            try:
                response = await self._call_llm(agent, messages, tenant_id)
                content = response.message.content or ""
                generated = self._parse_llm_response(content)

                # LLM explicitly indicates cannot generate / LLM 明确表示无法生成
                if not generated.sql:
                    return generated

                # Safety validation / 安全校验
                validation = SQLSafetyValidator.validate(
                    generated.sql,
                    allowed_tables,
                )

                if validation.passed:
                    return generated

                # Validation failed: build retry feedback / 校验失败：构建重试反馈
                if attempt < MAX_GENERATE_ATTEMPTS - 1:
                    retry_msg = render_prompt_contract(
                        "text_to_sql_retry",
                        violations="\n".join(f"- {v}" for v in validation.violations),
                    )
                    messages.append(
                        ChatMessage(role="assistant", content=content),
                    )
                    messages.append(
                        ChatMessage(role="user", content=retry_msg),
                    )
                    logger.warning(
                        "SQL generation attempt {}/{} failed validation: {}",
                        attempt + 1,
                        MAX_GENERATE_ATTEMPTS,
                        validation.violations,
                    )
                else:
                    # Last attempt still failed / 最后一次尝试仍失败
                    logger.error(
                        "SQL generation failed after {} attempts: {}",
                        MAX_GENERATE_ATTEMPTS,
                        validation.violations,
                    )
                    return GeneratedSQL(
                        success=False,
                        error=_("data_intelligence.generator.validation_failed"),
                        explanation=validation.error_message,
                    )

            except Exception as exc:
                logger.error(
                    "SQL generation attempt {}/{} error: {}",
                    attempt + 1,
                    MAX_GENERATE_ATTEMPTS,
                    str(exc),
                    exc_info=True,
                )
                if attempt >= MAX_GENERATE_ATTEMPTS - 1:
                    return GeneratedSQL(
                        success=False,
                        error=_("data_intelligence.generator.generation_error"),
                    )

        # Should not reach here / 不应到达这里
        return GeneratedSQL(
            success=False,
            error=_("data_intelligence.generator.generation_error"),
        )

    def _build_messages(
        self,
        question: str,
        schema: list[TableSchema],
        conversation_history: list[ConversationRound] | None = None,
    ) -> list[ChatMessage]:
        """Build LLM message list / 构建 LLM 消息列表"""
        messages: list[ChatMessage] = []

        # System prompt (with schema DDL) / System prompt（含 schema DDL）
        schema_ddl = "\n\n".join(t.to_ddl() for t in schema)
        system_content = render_prompt_contract(
            "text_to_sql_system",
            schema_ddl=schema_ddl,
        )
        messages.append(ChatMessage(role="system", content=system_content))

        # Multi-turn conversation history (last N rounds) / 多轮对话历史
        if conversation_history:
            recent = conversation_history[-MAX_CONVERSATION_ROUNDS:]
            for round_item in recent:
                messages.append(
                    ChatMessage(role="user", content=round_item.question),
                )
                # Use previous generation result as assistant reply / 之前的生成结果作为 assistant 回复
                prev_response = json.dumps(
                    {
                        "sql": round_item.sql,
                        "explanation": round_item.explanation,
                    },
                    ensure_ascii=False,
                )
                messages.append(
                    ChatMessage(role="assistant", content=prev_response),
                )

        # Current user question / 当前用户问题
        messages.append(ChatMessage(role="user", content=question))

        return messages

    async def _call_llm(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        tenant_id: int,
    ) -> Any:
        """Call LLM / 调用 LLM"""
        model_obj = agent.model
        provider_code = (
            model_obj.provider.code if model_obj and model_obj.provider else ""
        )
        model_code = model_obj.code if model_obj else ""

        return await self.gateway.chat(
            provider_code=provider_code,
            messages=messages,
            model=model_code,
            temperature=0.1,  # Low temperature for SQL accuracy / 低温度保证 SQL 准确性
            max_tokens=agent.max_tokens or 2048,
            tenant_id=tenant_id,
        )

    @staticmethod
    def _parse_llm_response(content: str) -> GeneratedSQL:
        """
        Parse LLM-returned JSON.
        解析 LLM 返回的 JSON。

        Error tolerance / 容错处理：
        - Strip markdown code fence / 去除 markdown code fence
        - Lenient JSON parsing / 宽松 JSON 解析
        """
        fenced_json = extract_fenced_json_block(content)
        cleaned = str(fenced_json if fenced_json is not None else content or "").strip()

        if not cleaned:
            return GeneratedSQL(
                success=False,
                error=_("data_intelligence.generator.empty_response"),
            )

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON object from content / 尝试从内容中提取 JSON 对象
            data = extract_first_json_object(cleaned)
            if not isinstance(data, dict):
                return GeneratedSQL(
                    success=False,
                    error=_("data_intelligence.generator.parse_error"),
                )

        sql = data.get("sql", "").strip()
        explanation = data.get("explanation", "")
        visualization = data.get("visualization", "table")
        confidence = float(data.get("confidence", 0.5))

        # LLM indicates cannot generate / LLM 表示无法生成
        if not sql:
            return GeneratedSQL(
                sql="",
                explanation=explanation,
                visualization_suggestion="text",
                confidence=0.0,
                success=False,
                error=explanation or _("data_intelligence.generator.cannot_generate"),
            )

        return GeneratedSQL(
            sql=sql,
            explanation=explanation,
            visualization_suggestion=visualization,
            confidence=min(max(confidence, 0.0), 1.0),
            success=True,
        )


__all__ = [
    "GeneratedSQL",
    "ConversationRound",
    "TextToSQLGenerator",
]
