"""
回收站自动清理定时任务

清理超过保留天数的已删除记录（物理删除）
通过 periodic-tasks 页面注册到调度系统
"""

import time

from app.core.database import sync_session_factory
from app.core.i18n import _
from app.core.logging import LogManager
from app.tasks.base import register_task, BaseTask
from app.core.base_model import utc_now

logger = LogManager.get_logger("task")

# 需要清理的模型列表（延迟导入避免循环依赖）
RECYCLABLE_MODELS = [
    # ── 叶子节点（无子表依赖），优先清理 ──
    "app.models.ai.agent_conversation.AgentConversation",  # child of Agent
    "app.models.ai.knowledge_document.KnowledgeDocument",  # child of KnowledgeBase
    "app.models.ai.skill.Skill",                           # child of SkillPackage
    # ── 父节点（有子表 CASCADE） ──
    "app.models.ai.agent.Agent",
    "app.models.ai.knowledge_base.KnowledgeBase",
    "app.models.ai.skill_package.SkillPackage",
    # ── 独立模型（无父子关系） ──
    "app.models.ai.api_key.ProviderApiKey",
    "app.models.ai.model.AIModel",
    "app.models.ai.provider.AIProvider",
    "app.models.auth.admin_role.AdminRole",
    "app.models.auth.tenant_admin_role.TenantAdminRole",
    # ── Tenant 子表（FK → tenants.id CASCADE），在 Tenant 之前清理 ──
    "app.models.tenant.tenant_plan.TenantPlan",
    "app.models.tenant.tenant_domain.TenantDomain",
    "app.models.system.periodic_task.PeriodicTask",
    # ── Tenant 最后处理 ──
    "app.models.tenant.tenant.Tenant",
]


def _import_model(model_path: str):
    """动态导入模型类"""
    module_path, class_name = model_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


@register_task(
    queue="scheduled",
    description="清理回收站过期记录（物理删除超过保留天数的软删除记录）",
    max_retries=1,
)
def cleanup_recycle_bin(self: BaseTask, retention_days: int = 30) -> dict:
    """
    清理回收站过期记录

    扫描所有注册的 Model，物理删除 deleted_at 超过 retention_days 天的记录。
    分批处理，每批 100 条，避免长事务。

    Args:
        retention_days: 保留天数，默认 30
    """
    from datetime import timedelta
    from sqlalchemy import delete as sa_delete, select

    start = time.monotonic()
    total_cleaned = 0
    results = {}

    cutoff = utc_now() - timedelta(days=retention_days)

    for model_path in RECYCLABLE_MODELS:
        session = None
        try:
            model_class = _import_model(model_path)
            model_name = model_class.__name__

            if not hasattr(model_class, "is_deleted") or not hasattr(model_class, "deleted_at"):
                continue

            session = sync_session_factory()
            batch_size = 100
            model_cleaned = 0

            while True:
                # 限制每批处理数量
                sub = (
                    select(model_class.id)
                    .where(
                        model_class.is_deleted.is_(True),
                        model_class.deleted_at.is_not(None),
                        model_class.deleted_at < cutoff,
                    )
                    .limit(batch_size)
                    .subquery()
                )

                # 技能包物理删除前清理磁盘存储
                if model_name == "SkillPackage":
                    ids_to_delete = session.execute(
                        select(sub.c.id)
                    ).scalars().all()
                    if ids_to_delete:
                        from app.ai.skills.packaging import cleanup_skill_storage
                        for pkg_id in ids_to_delete:
                            try:
                                cleanup_skill_storage(pkg_id)
                            except Exception as e:
                                logger.warning(
                                    "Failed to cleanup skill storage for package %d: %s",
                                    pkg_id, e,
                                )

                batch_stmt = (
                    sa_delete(model_class)
                    .where(model_class.id.in_(select(sub.c.id)))
                    .execution_options(synchronize_session=False)
                )

                result = session.execute(batch_stmt)
                batch_count = result.rowcount
                session.commit()

                if batch_count == 0:
                    break

                model_cleaned += batch_count

            if model_cleaned > 0:
                results[model_name] = model_cleaned
                total_cleaned += model_cleaned
                logger.info(
                    _("task.log.recycle_bin_cleaned"),
                    model=model_name,
                    count=model_cleaned,
                )

        except Exception as e:
            logger.error(
                _("task.log.recycle_bin_cleanup_failed"),
                error=f"{model_path}: {e}",
            )
            if session:
                session.rollback()
        finally:
            if session:
                session.close()

    elapsed = time.monotonic() - start
    logger.info(
        _("task.log.recycle_bin_cleanup_total"),
        total=total_cleaned,
        elapsed=elapsed,
    )

    return {
        "total_cleaned": total_cleaned,
        "details": results,
        "retention_days": retention_days,
        "elapsed_seconds": round(elapsed, 2),
    }
