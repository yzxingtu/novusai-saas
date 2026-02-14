"""
自然语言转 SQL 生成器（TextToSQLGenerator）

核心组件：使用 LLM 将用户自然语言问题转换为安全的 PostgreSQL SELECT 语句。

安全约束：
- System Prompt 严格限制 LLM 只生成 SELECT 语句
- 输出经过 SQLSafetyValidator 六重校验
- 生成失败时最多重试 2 次（含 violation 反馈）
- 3 次全部失败返回友好提示而非堆栈信息

多轮对话：
- 支持 conversation_history（最近 3 轮），用户可追问 "那上个月呢?"
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.ai.data_intelligence.schema_provider import SchemaProvider, TableSchema
from app.ai.data_intelligence.sql_safety import SQLSafetyValidator
from app.ai.types import ChatMessage
from app.core.i18n import _
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.gateway import AIGateway
    from app.models.ai.agent import Agent
    from sqlalchemy.ext.asyncio import AsyncSession

logger = LogManager.get_logger("ai.data_intelligence")

# 最大重试次数（含首次生成）
MAX_GENERATE_ATTEMPTS = 3

# 多轮对话保留的最近轮数
MAX_CONVERSATION_ROUNDS = 3


# ============================================
# 数据结构
# ============================================

@dataclass
class GeneratedSQL:
    """LLM 生成的 SQL 结果"""

    sql: str = ""
    explanation: str = ""
    visualization_suggestion: str = ""  # line/bar/pie/table/number
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
    """一轮对话记录（用于多轮上下文）"""

    question: str
    sql: str
    explanation: str = ""


# ============================================
# System Prompt 构建
# ============================================

_SYSTEM_PROMPT_TEMPLATE = """You are a PostgreSQL query generator for a multi-tenant SaaS platform.

## STRICT RULES
1. ONLY generate SELECT statements. Never INSERT/UPDATE/DELETE/DROP/ALTER/CREATE.
2. NEVER use comments (-- or /* */) in SQL.
3. NEVER use dangerous functions like pg_read_file, pg_sleep, dblink, lo_import, etc.
4. NEVER access system tables (pg_catalog, information_schema, pg_toast).
5. ONLY query the tables listed below — no other tables exist.
6. Do NOT add tenant_id conditions — they will be injected automatically.
7. Use table aliases for readability.
8. Add ORDER BY and reasonable LIMIT when appropriate.
9. For time ranges, use standard PostgreSQL date functions.

## AVAILABLE TABLES
{schema_ddl}

## OUTPUT FORMAT
Return ONLY a JSON object (no markdown, no extra text):
{{
  "sql": "SELECT ...",
  "explanation": "Brief explanation in the user's language",
  "visualization": "line|bar|pie|table|number",
  "confidence": 0.0-1.0
}}

- visualization: "number" for single-value, "line" for time series, "bar" for category comparison, "pie" for proportions, "table" for multi-column data.
- confidence: your certainty about the SQL correctness (1.0 = very sure, 0.5 = uncertain, 0.0 = cannot generate).
- If you CANNOT generate valid SQL, return: {{"sql": "", "explanation": "reason", "visualization": "text", "confidence": 0.0}}
"""

_RETRY_USER_TEMPLATE = """The SQL you generated has safety violations:
{violations}

Please fix the SQL to comply with all rules. Return the corrected JSON output."""


# ============================================
# TextToSQLGenerator
# ============================================

class TextToSQLGenerator:
    """
    自然语言转 SQL 生成器

    使用 LLM 将用户问题转换为 PostgreSQL SELECT 语句，
    经过多重安全校验，支持多轮对话和失败重试。
    """

    def __init__(self, gateway: AIGateway, db: AsyncSession):
        """
        Args:
            gateway: AI 网关（用于调用 LLM）
            db: 数据库会话（用于获取 schema）
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
        user_role: str = "tenant_admin",
    ) -> GeneratedSQL:
        """
        将自然语言问题转为 SQL

        Args:
            question: 用户的自然语言问题
            tenant_id: 租户 ID
            agent: 智能体（包含模型配置）
            conversation_history: 多轮对话历史（最近 N 轮）
            permissions: 用户 RBAC 权限码集合（用于表级过滤）
            user_role: 用户角色

        Returns:
            GeneratedSQL 生成结果
        """
        # 1. 获取 schema（按 RBAC 权限 + 问题关键词过滤相关表）
        schema = await self._schema_provider.get_schema(
            self.db, tenant_id, question,
            permissions=permissions,
            user_role=user_role,
        )

        if not schema:
            return GeneratedSQL(
                success=False,
                error=_(
                    "data_intelligence.generator.no_relevant_tables"
                ),
            )

        # 2. 获取允许的表名集合（RBAC 过滤后，用于后续安全校验）
        allowed_tables = await self._schema_provider.get_allowed_table_names(
            db=self.db,
            permissions=permissions,
            user_role=user_role,
            tenant_id=tenant_id,
        )

        # 3. 构建消息列表
        messages = self._build_messages(
            question=question,
            schema=schema,
            conversation_history=conversation_history,
        )

        # 4. 生成 + 校验 + 重试循环
        for attempt in range(MAX_GENERATE_ATTEMPTS):
            try:
                response = await self._call_llm(agent, messages, tenant_id)
                content = response.message.content or ""
                generated = self._parse_llm_response(content)

                # LLM 明确表示无法生成
                if not generated.sql:
                    return generated

                # 安全校验
                validation = SQLSafetyValidator.validate(
                    generated.sql, allowed_tables,
                )

                if validation.passed:
                    return generated

                # 校验失败：构建重试反馈
                if attempt < MAX_GENERATE_ATTEMPTS - 1:
                    retry_msg = _RETRY_USER_TEMPLATE.format(
                        violations="\n".join(
                            f"- {v}" for v in validation.violations
                        ),
                    )
                    messages.append(
                        ChatMessage(role="assistant", content=content),
                    )
                    messages.append(
                        ChatMessage(role="user", content=retry_msg),
                    )
                    logger.warning(
                        "SQL generation attempt %d/%d failed validation: %s",
                        attempt + 1,
                        MAX_GENERATE_ATTEMPTS,
                        validation.violations,
                    )
                else:
                    # 最后一次尝试仍失败
                    logger.error(
                        "SQL generation failed after %d attempts: %s",
                        MAX_GENERATE_ATTEMPTS,
                        validation.violations,
                    )
                    return GeneratedSQL(
                        success=False,
                        error=_(
                            "data_intelligence.generator.validation_failed"
                        ),
                        explanation=validation.error_message,
                    )

            except Exception as exc:
                logger.error(
                    "SQL generation attempt %d/%d error: %s",
                    attempt + 1,
                    MAX_GENERATE_ATTEMPTS,
                    str(exc),
                    exc_info=True,
                )
                if attempt >= MAX_GENERATE_ATTEMPTS - 1:
                    return GeneratedSQL(
                        success=False,
                        error=_(
                            "data_intelligence.generator.generation_error"
                        ),
                    )

        # 不应到达这里
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
        """构建 LLM 消息列表"""
        messages: list[ChatMessage] = []

        # System prompt（含 schema DDL）
        schema_ddl = "\n\n".join(t.to_ddl() for t in schema)
        system_content = _SYSTEM_PROMPT_TEMPLATE.format(
            schema_ddl=schema_ddl,
        )
        messages.append(ChatMessage(role="system", content=system_content))

        # 多轮对话历史（最近 N 轮）
        if conversation_history:
            recent = conversation_history[-MAX_CONVERSATION_ROUNDS:]
            for round_item in recent:
                messages.append(
                    ChatMessage(role="user", content=round_item.question),
                )
                # 将之前的生成结果作为 assistant 回复
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

        # 当前用户问题
        messages.append(ChatMessage(role="user", content=question))

        return messages

    async def _call_llm(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        tenant_id: int,
    ) -> Any:
        """调用 LLM"""
        model_obj = agent.model
        provider_code = (
            model_obj.provider.code
            if model_obj and model_obj.provider
            else ""
        )
        model_code = model_obj.code if model_obj else ""

        return await self.gateway.chat(
            provider_code=provider_code,
            messages=messages,
            model=model_code,
            temperature=0.1,  # 低温度保证 SQL 准确性
            max_tokens=agent.max_tokens or 2048,
            tenant_id=tenant_id,
        )

    @staticmethod
    def _parse_llm_response(content: str) -> GeneratedSQL:
        """
        解析 LLM 返回的 JSON

        容错处理：
        - 去除 markdown code fence
        - 宽松 JSON 解析
        """
        # 去除 markdown code fence
        cleaned = content.strip()
        cleaned = re.sub(
            r"^```(?:json)?\s*\n?", "", cleaned, flags=re.MULTILINE,
        )
        cleaned = re.sub(
            r"\n?```\s*$", "", cleaned, flags=re.MULTILINE,
        )
        cleaned = cleaned.strip()

        if not cleaned:
            return GeneratedSQL(
                success=False,
                error=_("data_intelligence.generator.empty_response"),
            )

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # 尝试从内容中提取 JSON 对象
            json_match = re.search(r"\{[\s\S]*\}", cleaned)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    return GeneratedSQL(
                        success=False,
                        error=_(
                            "data_intelligence.generator.parse_error"
                        ),
                    )
            else:
                return GeneratedSQL(
                    success=False,
                    error=_(
                        "data_intelligence.generator.parse_error"
                    ),
                )

        sql = data.get("sql", "").strip()
        explanation = data.get("explanation", "")
        visualization = data.get("visualization", "table")
        confidence = float(data.get("confidence", 0.5))

        # LLM 表示无法生成
        if not sql:
            return GeneratedSQL(
                sql="",
                explanation=explanation,
                visualization_suggestion="text",
                confidence=0.0,
                success=False,
                error=explanation or _(
                    "data_intelligence.generator.cannot_generate"
                ),
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
