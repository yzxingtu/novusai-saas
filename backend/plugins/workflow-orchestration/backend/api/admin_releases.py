from app.core.query_parser import parse_query_spec

from ..schemas.release import PublishTemplateRequestSchema, RollbackReleaseRequestSchema
from ..services.release_service import (
    list_releases as list_releases_service,
    publish_template as publish_template_service,
    rollback_release as rollback_release_service,
)


async def list_releases(request, db, ctx) -> dict:
    query = parse_query_spec(request)
    return await list_releases_service(db, query)


async def publish_template(request, db, ctx) -> dict:
    template_id = int(request.path_params["template_id"])
    body = await request.json()
    payload = PublishTemplateRequestSchema.model_validate(body)
    return await publish_template_service(
        db,
        template_id,
        payload,
        user_id=ctx.get_current_user_id(),
    )


async def rollback_release(request, db, ctx) -> dict:
    release_id = int(request.path_params["release_id"])
    try:
        body = await request.json()
    except Exception:
        body = {}
    payload = RollbackReleaseRequestSchema.model_validate(body)
    return await rollback_release_service(
        db,
        release_id,
        payload,
        user_id=ctx.get_current_user_id(),
    )
