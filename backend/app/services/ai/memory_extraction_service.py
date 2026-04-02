"""
会话记忆提取服务 / Session memory extraction service.

封装记忆提取模型选择、内部 AI 调用和 JSON 解析，
避免在 AgentChatService 中直接触达 AIGateway。
Encapsulates model selection, internal AI calls, and JSON parsing so
AgentChatService does not call AIGateway directly.
"""

from __future__ import annotations

import json

from app.ai.internal_ai_service import InternalAIService
from app.ai.types import ChatMessage
from app.configs.service import PLATFORM_TENANT_ID, ConfigService
from app.core.database import async_session_factory
from app.core.logging import LogManager
from app.repositories.ai.agent_repository import AgentRepository

logger = LogManager.get_logger("ai.memory_extraction_service")


class MemoryExtractionService:
    """
    会话记忆提取服务 / Session memory extraction service.

    使用独立 DB Session 执行记忆提取，兼容流式回调场景，
    并通过 InternalAIService 维持允许的内部 AI 调用边界。
    Uses an independent DB session for streaming-safe execution and routes
    all internal model calls through InternalAIService.
    """

    EMPTY_DELTA: dict[str, list[str]] = {
        "preferences": [],
        "constraints": [],
        "task_states": [],
        "verified_facts": [],
    }

    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id

    async def extract_turn_memory(
        self,
        *,
        agent_id: int,
        message: str,
        response: str,
    ) -> dict[str, list[str]]:
        """
        从单轮对话中提取记忆增量 / Extract memory deltas from a single turn.

        失败时静默降级为空结果，不影响主对话流程。
        Failures degrade to an empty result without affecting the main chat flow.
        """
        text = (message or "").strip()
        if not text or len(text) < 4:
            return self.EMPTY_DELTA.copy()

        try:
            async with async_session_factory() as llm_db:
                provider_code, model_code = await self._resolve_model(
                    llm_db,
                    agent_id=agent_id,
                )
                if not provider_code or not model_code:
                    return self.EMPTY_DELTA.copy()

                llm_response = await InternalAIService(llm_db).chat(
                    provider_code=provider_code,
                    messages=[
                        ChatMessage(
                            role="user",
                            content=self._build_extraction_prompt(
                                message=text,
                                response=response,
                            ),
                        )
                    ],
                    model=model_code,
                    temperature=0.1,
                    max_tokens=500,
                    tenant_id=(
                        self.tenant_id
                        if self.tenant_id > PLATFORM_TENANT_ID
                        else None
                    ),
                )

                result = self._parse_response_content(
                    llm_response.message.content or "",
                )

                if any(result.values()):
                    logger.info(
                        "LLM memory extraction: tenant={} agent={} prefs={} constraints={} tasks={} facts={}",
                        self.tenant_id,
                        agent_id,
                        len(result["preferences"]),
                        len(result["constraints"]),
                        len(result["task_states"]),
                        len(result["verified_facts"]),
                    )

                return result
        except Exception as exc:
            logger.debug(
                "LLM memory extraction failed: tenant={} agent={} err={}",
                self.tenant_id,
                agent_id,
                str(exc),
            )
            return self.EMPTY_DELTA.copy()

    async def _resolve_model(
        self,
        db,
        *,
        agent_id: int,
    ) -> tuple[str | None, str | None]:
        """
        解析记忆提取所用模型 / Resolve the model used for memory extraction.

        优先使用平台显式配置，缺失时回退到 agent 绑定模型。
        Prefer explicit platform config, fall back to the agent-bound model.
        """
        cfg = ConfigService(db)
        cfg_provider = await cfg.get_platform_config(
            "memory_extraction_provider",
            default="",
        )
        cfg_model = await cfg.get_platform_config(
            "memory_extraction_model",
            default="",
        )
        if cfg_provider and cfg_model:
            return str(cfg_provider), str(cfg_model)

        if self.tenant_id == PLATFORM_TENANT_ID:
            from app.repositories.ai.agent_repository import AdminAgentRepository

            agent_repo = AdminAgentRepository(db)
        else:
            agent_repo = AgentRepository(db, self.tenant_id)

        agent = await agent_repo.get_by_id(agent_id)
        if not agent:
            return None, None

        model_obj = getattr(agent, "model", None)
        provider = getattr(model_obj, "provider", None)
        provider_code = getattr(provider, "code", None)
        model_code = getattr(model_obj, "code", None)
        if not provider_code or not model_code:
            return None, None
        return str(provider_code), str(model_code)

    @classmethod
    def _build_extraction_prompt(cls, *, message: str, response: str) -> str:
        return (
            "Analyze this conversation turn and extract information worth remembering.\n\n"
            f"User message:\n{message[:1500]}\n\n"
            f"Assistant response:\n{(response or '')[:1500]}\n\n"
            "Extract ONLY genuinely important items into these categories:\n"
            "- preferences: User's stated preferences, likes, dislikes, preferred formats/tools/styles\n"
            "- constraints: Explicit restrictions, rules, things to avoid, 'don't do X'\n"
            "- task_states: Current task progress, todos, next steps, ongoing work\n"
            "- verified_facts: User's personal facts (name, role, company, tech stack, etc.)\n\n"
            "Rules:\n"
            "1. Only extract items the user explicitly stated or strongly implied\n"
            "2. Summarize each item concisely (1 short sentence max)\n"
            "3. If nothing worth remembering, return all empty arrays\n"
            "4. Do NOT extract trivial greetings, acknowledgments, or filler\n"
            "5. Do NOT repeat what the assistant said unless the user confirmed it as a preference\n\n"
            'Respond ONLY with valid JSON (no markdown, no explanation):\n'
            '{"preferences": [], "constraints": [], "task_states": [], "verified_facts": []}'
        )

    @classmethod
    def _parse_response_content(cls, content: str) -> dict[str, list[str]]:
        text = (content or "").strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3].strip()

        data = json.loads(text)
        result: dict[str, list[str]] = {}
        for key in cls.EMPTY_DELTA:
            raw_list = data.get(key) or []
            result[key] = [
                str(item).strip()[:300]
                for item in raw_list
                if item and str(item).strip()
            ][:5]
        return result


__all__ = ["MemoryExtractionService"]
