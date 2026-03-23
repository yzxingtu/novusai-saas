from ..schemas.module_config import UpdateModuleSettingsRequestSchema
from ..services.module_config_service import (
    get_settings_bundle,
    update_settings as update_settings_service,
)


async def get_settings(request, db, ctx) -> dict:
    return await get_settings_bundle(db)


async def update_settings(request, db, ctx) -> dict:
    body = await request.json()
    payload = UpdateModuleSettingsRequestSchema.model_validate(body)
    return await update_settings_service(
        db,
        payload,
        user_id=ctx.get_current_user_id(),
    )
