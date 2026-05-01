"""System prompt rendering helpers extracted from BaseEngine."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from jinja2 import (
    BaseLoader,
    ChainableUndefined,
    Environment,
    TemplateSyntaxError,
    UndefinedError,
)

from app.ai.types import ChatMessage
from app.core.config import settings
from app.core.i18n import _
from app.core.logging import LogManager
from app.models.ai.agent import Agent
from app.schemas.ai.retired_page_awareness import (
    assert_no_retired_page_awareness_input,
)

logger = LogManager.get_logger("ai.engine")

_jinja_env = Environment(
    loader=BaseLoader(),
    keep_trailing_newline=True,
    undefined=ChainableUndefined,
)


def build_system_message(
    *,
    agent: Agent,
    input_variables: dict[str, Any] | None = None,
) -> ChatMessage:
    """Render system prompt with built-in variables and identity declaration."""
    prompt = agent.system_prompt or ""
    agent_name = agent.name or ""

    if not prompt:
        return ChatMessage(role="system", content=prompt)

    if agent_name:
        identity = _("agent.identity_declaration").format(agent_name=agent_name)
        prompt = f"{identity}\n\n{prompt}"

    now = datetime.now(settings.tz)
    variables: dict[str, Any] = {
        "current_date": now.strftime("%Y-%m-%d"),
        "current_time": now.strftime("%H:%M:%S"),
        "current_timezone": settings.TIMEZONE,
        "agent_name": agent_name,
    }
    if input_variables:
        variables.update(assert_no_retired_page_awareness_input(input_variables))

    try:
        template = _jinja_env.from_string(prompt)
        prompt = template.render(**variables)
    except TemplateSyntaxError as exc:
        logger.warning(
            "Template syntax error: agent_id={} error={}",
            agent.id,
            str(exc),
        )
    except UndefinedError as exc:
        logger.warning(
            "Template undefined variable: agent_id={} error={}",
            agent.id,
            str(exc),
        )
    except Exception as exc:
        logger.warning(
            "Template render error: agent_id={} error={}",
            agent.id,
            str(exc),
        )

    return ChatMessage(role="system", content=prompt)
