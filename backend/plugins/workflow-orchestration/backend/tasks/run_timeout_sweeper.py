from __future__ import annotations

from app.core.logging import get_logger
from app.plugins.module_loader import load_plugin_module

PLUGIN_NAME = "workflow-orchestration"
logger = get_logger(__name__)


def _service(name: str):
    module = load_plugin_module(PLUGIN_NAME, f"services.{name}")
    if module is None:
        raise RuntimeError(f"Missing service module: {name}")
    return module


async def handle() -> dict[str, object]:
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        service = _service("recovery_service").RecoveryService(
            db,
            tenant_id=None,
            actor_type="system",
            actor_id=None,
        )
        result = await service.sweep_timeout_runs()
        await db.commit()
        logger.info("Workflow timeout sweep finished: {}", result)
        return result
