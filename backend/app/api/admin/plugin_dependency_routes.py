"""Dependency route section for admin plugin controller."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Body
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ValidationError

from app.core.deps import ActiveAdmin, DbSession
from app.core.response import success
from app.rbac.decorators import action_read, action_update

if TYPE_CHECKING:
    from app.core.base_controller import GlobalController


def _validate_dependency_action_payload(
    dependency_action_body: type[PydanticBaseModel],
    body: dict | None,
) -> PydanticBaseModel:
    """Translate ad-hoc body validation failures into FastAPI's 422 contract."""
    try:
        return dependency_action_body.model_validate(body or {})
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


def register_plugin_dependency_routes(
    controller: GlobalController,
    *,
    dependency_action_body: type[PydanticBaseModel],
) -> None:
    """Register dependency query/install/uninstall routes."""

    @controller.router.get("/{plugin_id}/dependents")
    @action_read("action.plugin.read")
    async def get_plugin_dependents(plugin_id: int, db: DbSession, admin: ActiveAdmin):
        _ = admin
        from app.plugins.lifecycle import PluginLifecycle

        lifecycle = PluginLifecycle(db)
        dependents = await lifecycle.get_dependents(plugin_id)
        return success(data=dependents)

    @controller.router.get("/{plugin_id}/dependencies")
    @action_read("action.plugin.read")
    async def get_plugin_dependencies(
        plugin_id: int, db: DbSession, admin: ActiveAdmin
    ):
        _ = admin
        from app.plugins.lifecycle import PluginLifecycle

        lifecycle = PluginLifecycle(db)
        dependencies = await lifecycle.get_dependencies(plugin_id)
        return success(data=dependencies)

    @controller.router.post("/{plugin_id}/dependencies/install")
    @action_update("action.plugin.update")
    async def install_plugin_dependencies(
        plugin_id: int,
        db: DbSession,
        admin: ActiveAdmin,
        body: dict | None = Body(default=None),
    ):
        _ = admin
        service = controller.get_service(db)
        payload = _validate_dependency_action_payload(dependency_action_body, body)
        result = await service.install_plugin_dependencies(
            plugin_id,
            install_python=bool(getattr(payload, "python", True)),
        )
        return success(data=result)

    @controller.router.post("/{plugin_id}/dependencies/uninstall")
    @action_update("action.plugin.update")
    async def uninstall_plugin_dependencies(
        plugin_id: int,
        db: DbSession,
        admin: ActiveAdmin,
        body: dict | None = Body(default=None),
    ):
        _ = admin
        service = controller.get_service(db)
        payload = _validate_dependency_action_payload(dependency_action_body, body)
        result = await service.uninstall_plugin_dependencies(
            plugin_id,
            uninstall_python=bool(getattr(payload, "python", True)),
        )
        return success(data=result)
