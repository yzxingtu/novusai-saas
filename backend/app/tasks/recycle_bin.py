"""
Recycle bin auto-cleanup scheduled task / 回收站自动清理定时任务

Cleans up deleted records exceeding retention days (physical delete).
清理超过保留天数的已删除记录（物理删除）
Registered to the scheduling system via the periodic-tasks page.
通过 periodic-tasks 页面注册到调度系统
"""

import time

from app.core.base_model import utc_now
from app.core.database import sync_session_factory
from app.core.i18n import _
from app.core.logging import LogManager
from app.tasks.base import BaseTask, register_task

logger = LogManager.get_logger("task")

# List of models to clean up (lazy import to avoid circular dependency) / 需要清理的模型列表（延迟导入避免循环依赖）
RECYCLABLE_MODELS = [
    # ── Deep leaf nodes (no child table dependency), clean first / 深层叶子节点（无子表依赖），优先清理 ──
    "app.models.ai.agent_conversation.AgentConversation",    # child of Agent
    "app.models.ai.batch_run.BatchRun",                      # child of Agent
    "app.models.ai.knowledge_document.KnowledgeDocument",    # child of KnowledgeBase
    "app.models.ai.skill.Skill",                             # child of SkillPackage
    "app.models.ai.table_policy.AITablePolicyOverride",      # child of AITablePolicy
    "app.models.ai.tenant_quota.TenantQuota",                # child of AIModel
    "app.models.ai.tenant_rate_limit.TenantModelRateLimit",  # child of AIModel
    # ── Parent nodes (have child tables CASCADE_SOFT/CASCADE_DELETE) / 父节点（有子表 CASCADE_SOFT/CASCADE_DELETE） ──
    "app.models.ai.agent.Agent",
    "app.models.ai.knowledge_base.KnowledgeBase",
    "app.models.ai.skill_package.SkillPackage",
    "app.models.ai.table_policy.AITablePolicy",
    # ── Independent models (no parent-child relationship) / 独立模型（无父子关系） ──
    "app.models.ai.api_key.ProviderApiKey",
    "app.models.ai.model.AIModel",
    "app.models.ai.provider.AIProvider",
    "app.models.auth.admin_role.AdminRole",
    "app.models.auth.tenant_admin_role.TenantAdminRole",
    # ── Tenant child tables, clean before Tenant / Tenant 子表，在 Tenant 之前清理 ──
    "app.models.tenant.tenant_plan.TenantPlan",
    "app.models.tenant.tenant_domain.TenantDomain",
    "app.models.system.periodic_task.PeriodicTask",
    # ── Tenant processed last / Tenant 最后处理 ──
    "app.models.tenant.tenant.Tenant",
]


def _import_model(model_path: str):
    """Dynamically import model class / 动态导入模型类"""
    module_path, class_name = model_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


@register_task(
    queue="scheduled",
    description="Clean up expired recycle bin records (escalate tenant → admin, physically delete admin-level expired) / 清理回收站过期记录（租户级升级到管理级，管理级物理删除）",
    max_retries=1,
)
def cleanup_recycle_bin(self: BaseTask, retention_days: int = 30) -> dict:
    """
    Clean up expired recycle bin records (two-phase) / 清理回收站过期记录（两阶段）

    Phase 1: Escalate tenant-level expired records to admin level (reset deleted_at).
    Phase 2: Physically delete admin-level expired records.
    第一阶段：将租户级过期记录升级到管理级（重置 deleted_at）。
    第二阶段：物理删除管理级过期记录。

    Args:
        retention_days: Retention days, default 30 / 保留天数，默认 30
    """
    from datetime import timedelta

    from sqlalchemy import delete as sa_delete
    from sqlalchemy import select, update as sa_update

    start = time.monotonic()
    total_escalated = 0
    total_deleted = 0
    escalate_results = {}
    delete_results = {}

    cutoff = utc_now() - timedelta(days=retention_days)
    now = utc_now()

    # ── Phase 1: Escalate tenant-level expired → admin level ──
    for model_path in RECYCLABLE_MODELS:
        session = None
        try:
            model_class = _import_model(model_path)
            model_name = model_class.__name__

            if not hasattr(model_class, "is_deleted") or not hasattr(model_class, "delete_level"):
                continue

            session = sync_session_factory()
            batch_size = 100
            model_escalated = 0

            while True:
                sub = (
                    select(model_class.id)
                    .where(
                        model_class.is_deleted.is_(True),
                        model_class.deleted_at.is_not(None),
                        model_class.deleted_at < cutoff,
                        model_class.delete_level == "tenant",
                    )
                    .limit(batch_size)
                    .subquery()
                )

                batch_stmt = (
                    sa_update(model_class)
                    .where(model_class.id.in_(select(sub.c.id)))
                    .values(delete_level="admin", deleted_at=now, updated_at=now)
                    .execution_options(synchronize_session=False)
                )

                result = session.execute(batch_stmt)
                batch_count = result.rowcount
                session.commit()

                if batch_count == 0:
                    break

                model_escalated += batch_count

            if model_escalated > 0:
                escalate_results[model_name] = model_escalated
                total_escalated += model_escalated
                logger.info(
                    "Recycle bin escalated tenant→admin model=%s count=%d",
                    model_name,
                    model_escalated,
                )

        except Exception as e:
            logger.error(
                "%s error=%s",
                _("task.log.recycle_bin_cleanup_failed"),
                f"escalate {model_path}: {e}",
            )
            if session:
                session.rollback()
        finally:
            if session:
                session.close()

    # ── Phase 2: Physically delete admin-level expired records ──
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
                sub = (
                    select(model_class.id)
                    .where(
                        model_class.is_deleted.is_(True),
                        model_class.deleted_at.is_not(None),
                        model_class.deleted_at < cutoff,
                        model_class.delete_level == "admin",
                    )
                    .limit(batch_size)
                    .subquery()
                )

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
                delete_results[model_name] = model_cleaned
                total_deleted += model_cleaned
                logger.info(
                    "%s model=%s count=%d",
                    _("task.log.recycle_bin_cleaned"),
                    model_name,
                    model_cleaned,
                )

        except Exception as e:
            logger.error(
                "%s error=%s",
                _("task.log.recycle_bin_cleanup_failed"),
                f"delete {model_path}: {e}",
            )
            if session:
                session.rollback()
        finally:
            if session:
                session.close()

    elapsed = time.monotonic() - start
    logger.info(
        "%s escalated=%d deleted=%d elapsed=%.2fs",
        _("task.log.recycle_bin_cleanup_total"),
        total_escalated,
        total_deleted,
        elapsed,
    )

    return {
        "total_escalated": total_escalated,
        "total_deleted": total_deleted,
        "escalate_details": escalate_results,
        "delete_details": delete_results,
        "retention_days": retention_days,
        "elapsed_seconds": round(elapsed, 2),
    }
