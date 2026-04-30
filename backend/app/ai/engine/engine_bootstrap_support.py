"""Shared engine bootstrap helpers for dispatcher and stream paths."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.ai.gateway import AIGateway
from app.ai.tools.sandbox import SandboxConfig, ToolSandbox
from app.configs.service import ConfigService
from app.core.logging import LogManager
from app.enums.agent import AgentExecutionModeEnum

from .conversation import ConversationEngine
from .image_generation import ImageGenerationEngine
from .task import TaskEngine
from .types import ExecutionRequest

logger = LogManager.get_logger("ai.engine.bootstrap_support")


@dataclass(frozen=True)
class EngineBootstrapBundle:
    """Resolved gateway/engine wiring for one execution entrypoint."""

    gateway: AIGateway
    engine: Any
    skill_result: Any | None
    sandbox: ToolSandbox | None
    is_image_model: bool


async def resolve_skill_result(
    *,
    db: Any,
    agent: Any,
    request: ExecutionRequest,
    tolerate_failure: bool = False,
    log: Any | None = None,
) -> Any | None:
    """Resolve live skill activation for the current turn."""
    from app.ai.skills import resolver as skill_resolver_module

    try:
        return await skill_resolver_module.resolve_for_agent(
            db,
            agent,
            tenant_id=request.tenant_id,
            user_role=request.user_role,
            request=request,
        )
    except Exception as exc:  # noqa: BLE001
        if not tolerate_failure:
            raise
        (log or logger).error(
            "Skill resolution failed for agent {}: {}",
            getattr(agent, "id", None),
            str(exc),
        )
        return None


async def load_toolkit_runtime_settings(db: Any) -> tuple[str, int]:
    """Load shared toolkit security/runtime settings."""
    config_service = ConfigService(db)
    toolkit_security_level = await config_service.get_platform_config(
        "toolkit_security_level",
        default="normal",
    )
    toolkit_memory_limit_mb = await config_service.get_platform_config(
        "toolkit_memory_limit_mb",
        default=256,
    )
    return str(toolkit_security_level), int(toolkit_memory_limit_mb)


def build_tool_sandbox(
    *,
    gateway: AIGateway,
    agent: Any,
    request: ExecutionRequest,
    sandbox_config: SandboxConfig | None,
    toolkit_security_level: str,
    toolkit_memory_limit_mb: int,
    db: Any,
) -> ToolSandbox:
    """Create the canonical tool sandbox for a live turn."""
    sandbox = ToolSandbox(
        tenant_id=request.tenant_id,
        agent_id=agent.id,
        config=sandbox_config or SandboxConfig(),
        user_id=request.user_id,
        user_role=request.user_role,
        permissions=request.permissions,
        gateway=gateway,
        db=db,
        agent=agent,
        toolkit_security_level=toolkit_security_level,
        toolkit_memory_limit_mb=toolkit_memory_limit_mb,
        input_variables=request.input_variables,
        conversation_id=request.conversation_id,
        trust_policy_ref=request.trust_policy_ref,
        interaction_mode=request.interaction_mode,
    )
    if request.consented_actions:
        sandbox.consented_actions = set(request.consented_actions)
    return sandbox


def _build_conversation_engine(
    *,
    db: Any,
    gateway: AIGateway,
    sandbox: ToolSandbox | None,
    conversation_engine_factory: Callable[..., Any] | None,
) -> Any:
    if conversation_engine_factory is not None:
        return conversation_engine_factory(
            db=db,
            gateway=gateway,
            sandbox=sandbox,
        )
    return ConversationEngine(
        db=db,
        gateway=gateway,
        sandbox=sandbox,
    )


def _build_task_engine(
    *,
    db: Any,
    gateway: AIGateway,
    sandbox: ToolSandbox | None,
    task_engine_factory: Callable[..., Any] | None,
) -> Any:
    if task_engine_factory is not None:
        return task_engine_factory(
            db=db,
            gateway=gateway,
            sandbox=sandbox,
        )
    return TaskEngine(
        db=db,
        gateway=gateway,
        sandbox=sandbox,
    )


async def build_engine_bootstrap_bundle(
    *,
    db: Any,
    agent: Any,
    request: ExecutionRequest,
    sandbox_config: SandboxConfig | None = None,
    enable_tool_runtime: bool = True,
    allow_image_engine: bool = False,
    tolerate_skill_resolution_failure: bool = False,
    conversation_engine_factory: Callable[..., Any] | None = None,
    task_engine_factory: Callable[..., Any] | None = None,
    image_engine_factory: Callable[..., Any] | None = None,
    log: Any | None = None,
) -> EngineBootstrapBundle:
    """Build gateway/engine/skill wiring without duplicating turn owner logic."""
    gateway = AIGateway(db)
    model_obj = getattr(agent, "model", None)
    is_image_model = bool(
        allow_image_engine
        and model_obj is not None
        and getattr(model_obj, "type", "") == "image"
    )
    if is_image_model:
        engine = (
            image_engine_factory(gateway=gateway)
            if image_engine_factory is not None
            else ImageGenerationEngine(gateway=gateway)
        )
        return EngineBootstrapBundle(
            gateway=gateway,
            engine=engine,
            skill_result=None,
            sandbox=None,
            is_image_model=True,
        )

    if not enable_tool_runtime:
        return EngineBootstrapBundle(
            gateway=gateway,
            engine=_build_conversation_engine(
                db=db,
                gateway=gateway,
                sandbox=None,
                conversation_engine_factory=conversation_engine_factory,
            ),
            skill_result=None,
            sandbox=None,
            is_image_model=False,
        )

    skill_result = await resolve_skill_result(
        db=db,
        agent=agent,
        request=request,
        tolerate_failure=tolerate_skill_resolution_failure,
        log=log,
    )
    (
        toolkit_security_level,
        toolkit_memory_limit_mb,
    ) = await load_toolkit_runtime_settings(db)
    sandbox = build_tool_sandbox(
        gateway=gateway,
        agent=agent,
        request=request,
        sandbox_config=sandbox_config,
        toolkit_security_level=toolkit_security_level,
        toolkit_memory_limit_mb=toolkit_memory_limit_mb,
        db=db,
    )

    if request.execution_mode == AgentExecutionModeEnum.TASK.value:
        engine = _build_task_engine(
            db=db,
            gateway=gateway,
            sandbox=sandbox,
            task_engine_factory=task_engine_factory,
        )
    else:
        engine = _build_conversation_engine(
            db=db,
            gateway=gateway,
            sandbox=sandbox,
            conversation_engine_factory=conversation_engine_factory,
        )

    return EngineBootstrapBundle(
        gateway=gateway,
        engine=engine,
        skill_result=skill_result,
        sandbox=sandbox,
        is_image_model=False,
    )


__all__ = [
    "EngineBootstrapBundle",
    "build_engine_bootstrap_bundle",
    "build_tool_sandbox",
    "load_toolkit_runtime_settings",
    "resolve_skill_result",
]
