"""
会话记忆提取服务 / Session memory extraction service.

封装记忆提取模型选择、内部 AI 调用和 JSON 解析，
避免在 AgentChatService 中直接触达 AIGateway。
Encapsulates model selection, internal AI calls, and JSON parsing so
AgentChatService does not call AIGateway directly.
"""

from __future__ import annotations

import json
import re

from app.ai.internal_ai_service import InternalAIService
from app.ai.prompt_contracts import render_prompt_contract
from app.ai.types import ChatMessage
from app.configs.service import PLATFORM_TENANT_ID, ConfigService
from app.core.database import async_session_factory
from app.core.logging import LogManager
from app.enums.ai import CallTypeEnum
from app.repositories.ai.agent_repository import AgentRepository

logger = LogManager.get_logger("ai.memory_extraction_service")

_CHINESE_NAME_PATTERN = re.compile(
    r"(?:我叫|叫我|我的名字是|你可以叫我|请叫我|称呼我)\s*[\"'“”‘’]?(?P<name>[\u4e00-\u9fffA-Za-z0-9_.\-·]{1,24})",
)
_ENGLISH_NAME_PATTERNS = (
    re.compile(
        r"\bmy name is\s+(?P<name>[A-Za-z][A-Za-z0-9_.\-]*(?:\s+[A-Za-z0-9_.\-]+){0,2})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bcall me\s+(?P<name>[A-Za-z][A-Za-z0-9_.\-]*(?:\s+[A-Za-z0-9_.\-]+){0,2})",
        re.IGNORECASE,
    ),
)
_MEMORY_SAVE_REQUEST_TERMS = (
    "存入记忆",
    "存入长期记忆",
    "存到记忆",
    "存到长期记忆",
    "保存到记忆",
    "保存到长期记忆",
    "记到记忆",
    "记到长期记忆",
    "请记住",
    "帮我记住",
    "记下来",
    "remember this",
    "save to memory",
)
_QUOTED_MEMORY_FACT_PATTERN = re.compile(
    r"[\"“”'‘’](?P<fact>[^\"“”'‘’]{2,160})[\"“”'‘’]"
)
_EXPLICIT_MEMORY_FACT_PATTERNS = (
    re.compile(
        r"(?:请|请你|帮我|麻烦你)?把\s*[\"“”'‘’]?(?P<fact>.+?)[\"“”'‘’]?\s*"
        r"(?:存入|存到|保存到|记到)(?:长期)?记忆",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:请记住|帮我记住|记下来)\s*(?P<fact>.+)",
        re.IGNORECASE,
    ),
)
_MEMORY_FACT_STOP_PATTERNS = (
    re.compile(r"(?:只有在|如果没有|否则|只回答|only answer|otherwise).*$", re.IGNORECASE),
)
_PLACEHOLDER_MEMORY_FACTS = {
    "这个",
    "这个信息",
    "这条信息",
    "这件事",
    "这条",
    "这句",
    "这句话",
    "这个偏好",
    "这条偏好",
    "我的偏好",
    "偏好",
}


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

    @classmethod
    def _empty_delta(cls) -> dict[str, list[str]]:
        return {key: [] for key in cls.EMPTY_DELTA}

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
            return self._empty_delta()

        try:
            async with async_session_factory() as llm_db:
                provider_code, model_code = await self._resolve_model(
                    llm_db,
                    agent_id=agent_id,
                )
                if not provider_code or not model_code:
                    return self._empty_delta()

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
                    call_type=CallTypeEnum.INTERNAL_MEMORY.value,
                    tenant_id=(
                        self.tenant_id if self.tenant_id > PLATFORM_TENANT_ID else None
                    ),
                )

                result = self._extract_with_fallback(
                    content=llm_response.message.content or "",
                    message=text,
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
            logger.warning(
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
        return render_prompt_contract(
            "memory_extraction",
            message=message[:1500],
            response=(response or "")[:1500],
        )

    @classmethod
    def _extract_with_fallback(
        cls,
        *,
        content: str,
        message: str,
    ) -> dict[str, list[str]]:
        text = (content or "").strip()
        if text:
            try:
                result = cls._parse_response_content(text)
                if any(result.values()):
                    return result
            except Exception:
                logger.debug("Memory extraction parse fallback engaged")

        return cls._fallback_extract_turn_memory(message)

    @classmethod
    def _fallback_extract_turn_memory(cls, message: str) -> dict[str, list[str]]:
        result = cls._empty_delta()
        display_name = cls._extract_display_name(message)
        if display_name:
            result["verified_facts"].append(f"用户名字是{display_name}")
        for fact in cls._extract_explicit_memory_facts(message):
            if fact not in result["verified_facts"]:
                result["verified_facts"].append(fact)
        return result

    @classmethod
    def _extract_explicit_memory_facts(cls, message: str) -> list[str]:
        text = (message or "").strip()
        if not text:
            return []
        lowered = text.lower()
        if not any(term in lowered for term in _MEMORY_SAVE_REQUEST_TERMS):
            return []

        facts: list[str] = []

        def _push(raw_fact: str | None) -> None:
            fact = cls._sanitize_memory_fact(raw_fact)
            if fact and fact not in facts:
                facts.append(fact)

        for match in _QUOTED_MEMORY_FACT_PATTERN.finditer(text):
            _push(match.group("fact"))
        for pattern in _EXPLICIT_MEMORY_FACT_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            _push(match.group("fact"))

        return facts[:3]

    @classmethod
    def _sanitize_memory_fact(cls, raw_fact: str | None) -> str | None:
        candidate = str(raw_fact or "").strip().strip("\"'“”‘’()（）[]【】")
        if not candidate:
            return None
        for pattern in _MEMORY_FACT_STOP_PATTERNS:
            candidate = pattern.sub("", candidate).strip()
        candidate = re.split(r"[\n\r\t。！？!?]", candidate, maxsplit=1)[0]
        candidate = re.sub(r"^(?:是|为|内容是|信息是|暗号是)\s*", "", candidate).strip()
        candidate = re.sub(r"\s+", " ", candidate).strip(" ，,：:；;。")
        if not candidate:
            return None
        if candidate in _PLACEHOLDER_MEMORY_FACTS:
            return None
        if len(candidate) > 160:
            candidate = candidate[:160].rstrip()
        return candidate or None

    @classmethod
    def _extract_display_name(cls, message: str) -> str | None:
        text = (message or "").strip()
        if not text:
            return None

        for pattern in (_CHINESE_NAME_PATTERN, *_ENGLISH_NAME_PATTERNS):
            match = pattern.search(text)
            if not match:
                continue
            candidate = cls._sanitize_name(match.group("name"))
            if candidate:
                return candidate
        return None

    @staticmethod
    def _sanitize_name(raw_name: str | None) -> str | None:
        candidate = str(raw_name or "").strip().strip("\"'“”‘’()（）[]【】")
        if not candidate:
            return None
        candidate = re.split(r"[\n\r\t，,。！？；;:：]", candidate, maxsplit=1)[0]
        candidate = re.sub(r"\s+", " ", candidate).strip()
        if not candidate or len(candidate) > 32:
            return None
        return candidate

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
