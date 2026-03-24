"""
企业任务绑定仓储 / Tenant Task Binding Repository
"""

from app.core.base_repository import BaseRepository
from app.models.system.tenant_task_binding import TenantTaskBinding


class TenantTaskBindingRepository(BaseRepository[TenantTaskBinding]):
    """
    企业任务绑定仓储 / Tenant task binding repository.
    """

    model = TenantTaskBinding


__all__ = ["TenantTaskBindingRepository"]
