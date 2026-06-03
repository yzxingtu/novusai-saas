"""
通知模板 Repository / Notification Template Repository

提供通知模板的数据访问层。
Provides notification template data access layer.
"""

from sqlalchemy import or_, select

from app.configs.service import PLATFORM_TENANT_ID
from app.core.base_repository import BaseRepository
from app.models.common.notification_template import NotificationTemplate
from app.models.tenant.tenant import Tenant
from app.schemas.common.query import FilterOp, FilterRule, QuerySpec


class NotificationTemplateRepository(BaseRepository[NotificationTemplate]):
    """通知模板仓库（全局，无企业过滤） / Notification template repository (global, no tenant filter)."""

    model = NotificationTemplate

    async def query_list(
        self,
        spec: QuerySpec,
        scope: str | None = None,
        forced_filters: list[FilterRule] | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[NotificationTemplate], int]:
        """中文: 支持 is_override 派生筛选，同时复用基础列表查询。

        EN: Support derived is_override filtering while reusing the base list query.
        """
        filters: list[FilterRule] = []
        for rule in spec.filters:
            if rule.field != "is_override":
                filters.append(rule)
                continue

            is_override = str(rule.value).strip().lower() in {"1", "true", "yes"}
            filters.append(
                FilterRule(
                    field="override_of",
                    op=FilterOp.notnull if is_override else FilterOp.isnull,
                    value=True,
                )
            )

        next_spec = spec.model_copy(update={"filters": filters})
        return await super().query_list(
            next_spec,
            scope=scope,
            forced_filters=forced_filters,
            include_deleted=include_deleted,
        )

    async def get_tenant_name_map(self, tenant_ids: set[int]) -> dict[int, str]:
        """中文: 批量加载通知模板归属企业名称。

        EN: Batch load tenant names for notification-template ownership display.
        """
        normalized_ids = {
            int(tenant_id)
            for tenant_id in tenant_ids
            if tenant_id not in (None, PLATFORM_TENANT_ID)
        }
        if not normalized_ids:
            return {}

        result = await self.db.execute(
            select(Tenant.id, Tenant.name).where(
                Tenant.id.in_(normalized_ids),
                Tenant.is_deleted.is_(False),
            )
        )
        return {int(row.id): str(row.name) for row in result.all()}

    async def resolve_effective_template(
        self,
        code: str,
        tenant_id: int | None = None,
    ) -> NotificationTemplate | None:
        """中文: 按租户覆盖、插件/source、平台默认顺序解析生效模板。

        EN: Resolve the effective template by tenant override, plugin/source, then platform default.
        """
        normalized_tenant_id = (
            None if tenant_id in (None, PLATFORM_TENANT_ID) else tenant_id
        )
        tenant_conditions = [
            NotificationTemplate.tenant_id.is_(None),
            NotificationTemplate.tenant_id == PLATFORM_TENANT_ID,
        ]
        if normalized_tenant_id is not None:
            tenant_conditions.append(
                NotificationTemplate.tenant_id == normalized_tenant_id
            )

        result = await self.db.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.code == code,
                NotificationTemplate.is_deleted.is_(False),
                NotificationTemplate.is_enabled.is_(True),
                or_(*tenant_conditions),
            )
        )
        templates = list(result.scalars().all())
        if not templates:
            return None
        templates.sort(
            key=lambda template: self._template_rank(template, normalized_tenant_id)
        )
        return templates[0]

    async def resolve_default_template(
        self,
        template: NotificationTemplate,
    ) -> NotificationTemplate | None:
        """中文: 查找覆盖模板可恢复的默认来源模板。

        EN: Find the default source template that an override can restore from.
        """
        if template.override_of:
            base = await self.get_by_id(template.override_of)
            if base is not None:
                return base

        result = await self.db.execute(
            select(NotificationTemplate)
            .where(
                NotificationTemplate.id != template.id,
                NotificationTemplate.code == template.code,
                NotificationTemplate.is_deleted.is_(False),
                NotificationTemplate.scope == "platform",
                or_(
                    NotificationTemplate.tenant_id.is_(None),
                    NotificationTemplate.tenant_id == PLATFORM_TENANT_ID,
                ),
            )
            .order_by(NotificationTemplate.id.asc())
        )
        return result.scalars().first()

    @staticmethod
    def _template_rank(
        template: NotificationTemplate,
        tenant_id: int | None,
    ) -> tuple[int, int]:
        scope = template.scope or "platform"
        template_id = template.id or 0
        if (
            tenant_id is not None
            and scope == "tenant"
            and template.tenant_id == tenant_id
        ):
            return (0, template_id)
        if (
            scope in {"plugin", "source"}
            or template.source == "plugin"
            or template.plugin_name
        ):
            return (1, template_id)
        if scope == "platform" and template.tenant_id in (None, PLATFORM_TENANT_ID):
            return (2, template_id)
        return (3, template_id)


__all__ = ["NotificationTemplateRepository"]
