from app.core.query_parser import parse_query_spec

from ..schemas.template import CreateTemplateRequestSchema, UpdateTemplateRequestSchema
from ..services.template_service import (
    create_template as create_template_service,
    get_template_detail as get_template_detail_service,
    list_template_versions as list_template_versions_service,
    list_templates as list_templates_service,
    update_template as update_template_service,
)


async def list_templates(request, db, ctx) -> dict:
    query = parse_query_spec(request)
    return await list_templates_service(db, query)


async def create_template(request, db, ctx) -> dict:
    body = await request.json()
    payload = CreateTemplateRequestSchema.model_validate(body)
    return await create_template_service(
        db,
        payload,
        user_id=ctx.get_current_user_id(),
    )


async def get_template_detail(request, db, ctx) -> dict:
    template_id = int(request.path_params["template_id"])
    return await get_template_detail_service(db, template_id)


async def update_template(request, db, ctx) -> dict:
    template_id = int(request.path_params["template_id"])
    body = await request.json()
    payload = UpdateTemplateRequestSchema.model_validate(body)
    return await update_template_service(
        db,
        template_id,
        payload,
        user_id=ctx.get_current_user_id(),
    )


async def list_template_versions(request, db, ctx) -> dict:
    template_id = int(request.path_params["template_id"])
    query = parse_query_spec(request)
    return await list_template_versions_service(db, template_id, query)
