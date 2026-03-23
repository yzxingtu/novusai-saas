from ..services.module_config_service import get_settings_overview
from ..services.release_service import get_release_overview_stats, get_runtime_status_metrics
from ..services.template_service import get_template_overview_stats


async def get_overview(request, db, ctx) -> dict:
    template_summary = await get_template_overview_stats(db)
    release_summary = await get_release_overview_stats(db)
    settings_summary = await get_settings_overview(db)
    runtime_summary = await get_runtime_status_metrics(db)
    return {
        "template_summary": template_summary,
        "release_summary": release_summary,
        "runtime_summary": runtime_summary,
        "settings_summary": settings_summary,
    }


async def get_metrics(request, db, ctx) -> dict:
    template_summary = await get_template_overview_stats(db)
    release_summary = await get_release_overview_stats(db)
    runtime_summary = await get_runtime_status_metrics(db)
    return {
        "templates": template_summary,
        "releases": release_summary,
        "runtime": runtime_summary,
    }
