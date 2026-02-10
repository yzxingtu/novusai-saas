"""
租户端智能体管理 API

提供智能体的 CRUD、发布等接口
"""

from fastapi import Request

from app.core.base_controller import TenantController
from app.core.deps import DbSession, ActiveTenantAdmin, QueryParams
from app.core.i18n import _
from app.core.response import success, created, deleted, paginated
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_create,
    action_update,
    action_delete,
)
from app.ai.agent_quota import AgentConcurrencyLimiter, AgentQuotaConfig, AgentQuotaManager
from app.ai.agent_stats import AgentStatsManager
from app.schemas.ai.agent import AgentCreate, AgentUpdate
from app.schemas.ai.agent_access import AgentAccessUpdate
from app.schemas.ai.agent_version import AgentPublishRequest, AgentRollbackRequest
from app.schemas.ai.batch_run import BatchRunCreate, BatchRunResponse, BatchRunProgress
from app.services.ai.agent_service import AgentService


def _build_agent_list_item(agent) -> dict:
    """从 ORM 对象构建列表项字典，提取 model_name"""
    model_name = None
    try:
        model_obj = getattr(agent, "model", None)
        if model_obj is not None:
            model_name = model_obj.name
    except (AttributeError, Exception):
        pass

    return {
        "id": agent.id,
        "tenant_id": agent.tenant_id,
        "name": agent.name,
        "avatar": agent.avatar,
        "description": agent.description,
        "status": agent.status,
        "execution_mode": agent.execution_mode,
        "model_name": model_name,
        "published_version": agent.published_version,
        "visibility": agent.visibility,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    }


@permission_resource(
    resource="agent",
    name="menu.tenant.agent",
    scope=PermissionScope.TENANT,
    menu=MenuConfig(
        icon="lucide:bot",
        path="/ai/agents",
        component="ai/agents/index",
        parent="ai_mgmt",
        sort_order=10,
    ),
)
class TenantAgentController(TenantController):
    """
    租户智能体管理控制器

    提供智能体 CRUD、发布等操作
    """

    prefix = "/ai/agents"
    tags = ["智能体管理"]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("", summary="获取智能体列表")
        @action_read("action.agent.list")
        async def list_agents(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            query: QueryParams,
        ):
            """
            获取智能体列表

            支持 JSON:API 分页、筛选、排序
            权限: agent:list
            """
            service = AgentService(db, tenant_admin.tenant_id)
            items, total = await service.query_list(spec=query)
            result = [_build_agent_list_item(item) for item in items]

            return paginated(
                items=result,
                total=total,
                page=query.page,
                page_size=query.size,
            )

        @router.get("/{agent_id}", summary="获取智能体详情")
        @action_read("action.agent.detail")
        async def get_agent(
            request: Request,
            db: DbSession,
            agent_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取智能体详情

            权限: agent:detail
            """
            service = AgentService(db, tenant_admin.tenant_id)
            result = await service.get_agent_detail(agent_id)

            return success(data=result)

        @router.post("", summary="创建智能体")
        @action_create("action.agent.create")
        async def create_agent(
            request: Request,
            db: DbSession,
            data: AgentCreate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            创建智能体

            权限: agent:create
            """
            service = AgentService(db, tenant_admin.tenant_id)
            agent = await service.create(data.model_dump(exclude_unset=True))
            await db.commit()

            return created(data=agent.to_dict(), message=_("agent.created"))

        @router.put("/{agent_id}", summary="更新智能体")
        @action_update("action.agent.update")
        async def update_agent(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentUpdate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            更新智能体

            权限: agent:update
            """
            service = AgentService(db, tenant_admin.tenant_id)

            agent = await service.repo.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            update_data = data.model_dump(exclude_unset=True)
            updated = await service.update(agent_id, update_data)
            await db.commit()

            return success(data=updated.to_dict(), message=_("agent.updated"))

        @router.delete("/{agent_id}", summary="删除智能体")
        @action_delete("action.agent.delete")
        async def delete_agent(
            request: Request,
            db: DbSession,
            agent_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            删除智能体（软删除）

            权限: agent:delete
            """
            service = AgentService(db, tenant_admin.tenant_id)

            agent = await service.repo.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            await service.delete(agent_id)
            await db.commit()

            return deleted(message=_("agent.deleted"))

        @router.get("/{agent_id}/quota-usage", summary="获取智能体配额用量")
        @action_read("action.agent.quota_usage")
        async def get_quota_usage(
            request: Request,
            db: DbSession,
            agent_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取智能体配额使用情况

            权限: agent:quota_usage
            """
            service = AgentService(db, tenant_admin.tenant_id)
            agent = await service.repo.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            config = AgentQuotaConfig.from_dict(agent.quota_config)
            usage = await AgentQuotaManager.get_usage_summary(
                tenant_id=tenant_admin.tenant_id,
                agent_id=agent_id,
                config=config,
            )

            return success(data=usage)

        @router.post("/{agent_id}/publish", summary="发布智能体")
        @action_update("action.agent.publish")
        async def publish_agent(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentPublishRequest,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            发布智能体

            将当前配置冻结为新版本快照，状态设为 published。
            权限: agent:publish
            """
            service = AgentService(db, tenant_admin.tenant_id)
            agent = await service.publish_agent(
                agent_id,
                change_log=data.change_log,
                created_by=tenant_admin.id,
            )
            await db.commit()

            return success(data=agent.to_dict(), message=_("agent.published"))

        @router.post("/{agent_id}/rollback", summary="回滚智能体")
        @action_update("action.agent.rollback")
        async def rollback_agent(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentRollbackRequest,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            回滚智能体到指定版本

            将指定版本的配置回写到主记录，状态重置为 draft。
            权限: agent:rollback
            """
            service = AgentService(db, tenant_admin.tenant_id)
            agent = await service.rollback_agent(agent_id, data.version)
            await db.commit()

            return success(
                data=agent.to_dict(),
                message=_("agent.version.rolled_back"),
            )

        # ========================================
        # 用量统计
        # ========================================

        @router.get("/{agent_id}/stats", summary="获取智能体用量统计")
        @action_read("action.agent.stats")
        async def get_agent_stats(
            request: Request,
            db: DbSession,
            agent_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取智能体用量统计（对话次数、Token 消耗）

            权限: agent:stats
            """
            service = AgentService(db, tenant_admin.tenant_id)
            agent = await service.repo.get_by_id(agent_id)
            if not agent:
                raise NotFoundException(message=_("agent.error.not_found"))

            stats = await AgentStatsManager.get_stats(
                tenant_id=tenant_admin.tenant_id,
                agent_id=agent_id,
            )

            return success(data=stats)

        # ========================================
        # 访问权限配置
        # ========================================

        @router.get("/{agent_id}/access", summary="获取智能体访问权限配置")
        @action_read("action.agent.access_config")
        async def get_access_config(
            request: Request,
            db: DbSession,
            agent_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取智能体访问权限配置

            权限: agent:access_config
            """
            service = AgentService(db, tenant_admin.tenant_id)
            config = await service.get_access_config(agent_id)

            return success(data=config)

        @router.put("/{agent_id}/access", summary="更新智能体访问权限配置")
        @action_update("action.agent.update_access")
        async def update_access_config(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: AgentAccessUpdate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            更新智能体访问权限配置

            权限: agent:update_access
            """
            service = AgentService(db, tenant_admin.tenant_id)
            config = await service.update_access_config(
                agent_id=agent_id,
                visibility=data.visibility,
                access_type=data.access_type,
                org_node_ids=data.org_node_ids,
                user_ids=data.user_ids,
            )
            await db.commit()

            return success(data=config, message=_("agent.access.updated"))

        # ========================================
        # 版本管理
        # ========================================

        @router.get("/{agent_id}/versions", summary="获取智能体版本历史")
        @action_read("action.agent.versions")
        async def list_versions(
            request: Request,
            db: DbSession,
            agent_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取智能体版本历史列表（降序）

            权限: agent:versions
            """
            service = AgentService(db, tenant_admin.tenant_id)
            versions = await service.get_versions(agent_id)

            return success(data=versions)

        # 注意：diff 路由必须在 {version} 之前注册，避免 "diff" 被匹配为版本号
        @router.get("/{agent_id}/versions/diff", summary="对比两个版本")
        @action_read("action.agent.version_diff")
        async def diff_versions(
            request: Request,
            db: DbSession,
            agent_id: int,
            v1: int,
            v2: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            对比两个版本的字段差异

            Query params: v1, v2
            权限: agent:version_diff
            """
            service = AgentService(db, tenant_admin.tenant_id)
            diff = await service.diff_versions(agent_id, v1, v2)

            return success(data=diff)

        @router.get("/{agent_id}/versions/{version}", summary="获取智能体版本详情")
        @action_read("action.agent.version_detail")
        async def get_version_detail(
            request: Request,
            db: DbSession,
            agent_id: int,
            version: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            获取智能体指定版本的完整配置快照

            权限: agent:version_detail
            """
            service = AgentService(db, tenant_admin.tenant_id)
            detail = await service.get_version_detail(agent_id, version)

            return success(data=detail)

        # ========================================
        # 批处理
        # ========================================

        @router.post("/{agent_id}/batch", summary="提交批处理任务", status_code=202)
        @action_create("action.agent.batch_submit")
        async def submit_batch(
            request: Request,
            db: DbSession,
            agent_id: int,
            data: BatchRunCreate,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            提交智能体批处理任务

            立即返回 batch_run_id，实际执行由 Celery Worker 异步完成。
            通过 GET /{agent_id}/batch/{run_id} 查询进度。

            权限: agent:batch_submit
            """
            from app.ai.engine.dispatcher import ExecutionDispatcher
            from app.ai.engine.types import BatchItem, ExecutionRequest
            from app.enums.agent import AgentExecutionModeEnum

            # 构建 BatchItem 列表
            items = [
                BatchItem(
                    item_id=str(idx),
                    input_variables=item_data,
                )
                for idx, item_data in enumerate(data.items)
            ]

            exec_request = ExecutionRequest(
                agent_id=agent_id,
                tenant_id=tenant_admin.tenant_id,
                user_id=tenant_admin.id,
                execution_mode=AgentExecutionModeEnum.BATCH.value,
            )

            dispatcher = ExecutionDispatcher(db)
            result = await dispatcher.dispatch_batch(
                request=exec_request,
                items=items,
                max_workers=data.max_workers,
                created_by=tenant_admin.id,
            )

            return success(data={
                "batch_run_id": result.batch_run_id,
                "total": result.total,
                "status": "pending",
            })

        @router.get("/{agent_id}/batch/{run_id}", summary="查询批处理进度")
        @action_read("action.agent.batch_progress")
        async def get_batch_progress(
            request: Request,
            db: DbSession,
            agent_id: int,
            run_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            查询批处理进度和结果

            权限: agent:batch_progress
            """
            from app.repositories.ai.batch_run_repository import (
                BatchRunRepository,
            )

            repo = BatchRunRepository(db, tenant_admin.tenant_id)
            batch_run = await repo.get_by_id(run_id)
            if not batch_run or batch_run.agent_id != agent_id:
                raise NotFoundException(
                    message=_("agent.error.batch_run_not_found"),
                )

            return success(data=BatchRunResponse.model_validate(
                batch_run, from_attributes=True,
            ).model_dump())

        @router.post(
            "/{agent_id}/batch/{run_id}/cancel",
            summary="取消批处理任务",
        )
        @action_update("action.agent.batch_cancel")
        async def cancel_batch(
            request: Request,
            db: DbSession,
            agent_id: int,
            run_id: int,
            tenant_admin: ActiveTenantAdmin,
        ):
            """
            取消批处理任务

            将 BatchRun 状态设为 cancelled，worker 会在下一项开始前检测并停止。
            权限: agent:batch_cancel
            """
            from app.enums.agent import BatchRunStatusEnum
            from app.repositories.ai.batch_run_repository import (
                BatchRunRepository,
            )

            repo = BatchRunRepository(db, tenant_admin.tenant_id)
            batch_run = await repo.get_by_id(run_id)
            if not batch_run or batch_run.agent_id != agent_id:
                raise NotFoundException(
                    message=_("agent.error.batch_run_not_found"),
                )

            if batch_run.status not in (
                BatchRunStatusEnum.PENDING.value,
                BatchRunStatusEnum.RUNNING.value,
            ):
                from app.exceptions import BusinessException
                raise BusinessException(
                    message=_("agent.error.batch_not_cancellable"),
                )

            batch_run.status = BatchRunStatusEnum.CANCELLED.value
            await db.commit()

            # 尝试撤销 Celery 任务
            if batch_run.celery_task_id:
                try:
                    from app.celery_app import celery_app
                    celery_app.control.revoke(
                        batch_run.celery_task_id, terminate=False,
                    )
                except Exception:
                    pass

            return success(message=_("agent.batch.cancelled"))


# 导出路由器
router = TenantAgentController.get_router()

__all__ = ["router", "TenantAgentController"]
