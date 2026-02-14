"""
知识库监控 API (Admin)

提供平台端知识库全局查询、统计监控接口（平台管理员专用）
"""

from fastapi import Request

from app.core.base_controller import GlobalController
from app.core.base_schema import PageResponse
from app.core.deps import DbSession, QueryParams, ActiveAdmin
from app.core.i18n import _
from app.core.response import success, created, deleted
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
from app.schemas.ai.knowledge_base import AdminKnowledgeBaseCreate, AdminKnowledgeBaseUpdate
from app.services.ai.knowledge_base_service import AdminKnowledgeBaseService


@permission_resource(
    resource="ai_knowledge_base",
    name="menu.admin.ai_knowledge_base",
    scope=PermissionScope.ADMIN,
    menu=MenuConfig(
        icon="lucide:book-open",
        path="/ai/monitor/knowledge-bases",
        component="ai/knowledge-bases/index",
        parent="ai_app",
        sort_order=40,
    ),
)
class AdminKnowledgeBaseController(GlobalController):
    """
    平台端知识库监控控制器

    提供全租户知识库查询和统计
    """

    prefix = "/ai/knowledge-bases"
    tags = [_("menu.tags.admin_ai_knowledge_base")]

    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router

        @router.get("", summary="查询知识库列表（全租户）")
        @action_read("action.ai_knowledge_base.list")
        async def list_knowledge_bases(
            request: Request,
            db: DbSession,
            spec: QueryParams,
            admin: ActiveAdmin,
        ):
            """
            查询全部租户的知识库列表

            支持 JSON:API 风格筛选:
            - filter[tenant_id][eq]: 租户 ID
            - filter[status][eq]: 状态
            - filter[name][ilike]: 名称模糊搜索

            权限: ai_knowledge_base:list
            """
            service = AdminKnowledgeBaseService(db)
            items, total = await service.query_list(spec)

            result = []
            for kb in items:
                item = kb.to_dict()
                item["embedding_model_name"] = None
                try:
                    if kb.embedding_model:
                        item["embedding_model_name"] = kb.embedding_model.name
                except Exception:
                    pass
                result.append(item)

            return success(
                data=PageResponse.create(
                    items=result,
                    total=total,
                    page=spec.page,
                    page_size=spec.size,
                ),
                message=_("common.success"),
            )

        @router.post("", summary="创建知识库（支持全局/租户/管理端专属）")
        @action_create("action.ai_knowledge_base.create")
        async def create_knowledge_base(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            body: AdminKnowledgeBaseCreate,
        ):
            """
            管理端创建知识库

            支持 3 种 scope:
            - tenant: 属于指定租户（需提供 tenant_id）
            - global: 全局共享（所有租户可见）
            - admin: 仅管理端可见

            权限: ai_knowledge_base:create
            """
            service = AdminKnowledgeBaseService(db)
            data = body.model_dump(exclude_unset=True)
            kb = await service.create(data)
            await db.commit()
            await db.refresh(kb)

            result = kb.to_dict()
            result["embedding_model_name"] = None
            try:
                if kb.embedding_model:
                    result["embedding_model_name"] = kb.embedding_model.name
            except Exception:
                pass

            return created(data=result, message=_("knowledge_base.created"))

        @router.put("/{kb_id}", summary="更新知识库")
        @action_update("action.ai_knowledge_base.update")
        async def update_knowledge_base(
            request: Request,
            db: DbSession,
            kb_id: int,
            admin: ActiveAdmin,
            body: AdminKnowledgeBaseUpdate,
        ):
            """
            管理端更新知识库

            权限: ai_knowledge_base:update
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            data = body.model_dump(exclude_unset=True)
            kb = await service.update(kb_id, data)
            await db.commit()
            await db.refresh(kb)

            result = kb.to_dict()
            result["embedding_model_name"] = None
            try:
                if kb.embedding_model:
                    result["embedding_model_name"] = kb.embedding_model.name
            except Exception:
                pass

            return success(data=result, message=_("knowledge_base.updated"))

        @router.get("/selectable", summary="获取可 @ 选择的知识库列表")
        @action_read("action.ai_knowledge_base.selectable")
        async def list_selectable_knowledge_bases(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            获取管理端可 @ 选择的知识库列表

            返回 scope=admin + scope=global 的知识库（精简字段）

            权限: ai_knowledge_base:selectable
            """
            from sqlalchemy import select, or_
            from app.models.ai.knowledge_base import KnowledgeBase
            from app.enums.common import ResourceScopeEnum

            stmt = (
                select(KnowledgeBase)
                .where(
                    KnowledgeBase.is_deleted.is_(False),
                    or_(
                        KnowledgeBase.scope == ResourceScopeEnum.ADMIN.value,
                        KnowledgeBase.scope == ResourceScopeEnum.GLOBAL.value,
                    ),
                )
                .order_by(KnowledgeBase.name.asc())
            )
            result = await db.execute(stmt)
            kbs = list(result.scalars().all())

            items = [
                {
                    "id": kb.id,
                    "name": kb.name,
                    "description": kb.description,
                    "scope": kb.scope,
                    "document_count": kb.document_count,
                }
                for kb in kbs
            ]
            return success(data=items)

        @router.get("/stats", summary="获取知识库全局统计")
        @action_read("action.ai_knowledge_base.stats")
        async def get_global_stats(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            """
            获取全局知识库统计

            返回总知识库数、总文档数、总分块数、总存储大小

            权限: ai_knowledge_base:stats
            """
            from sqlalchemy import select, func
            from app.models.ai.knowledge_base import KnowledgeBase

            stmt = select(
                func.count(KnowledgeBase.id).label("total_knowledge_bases"),
                func.coalesce(func.sum(KnowledgeBase.document_count), 0).label("total_documents"),
                func.coalesce(func.sum(KnowledgeBase.total_chunks), 0).label("total_chunks"),
                func.coalesce(func.sum(KnowledgeBase.total_size_bytes), 0).label("total_size_bytes"),
            ).where(KnowledgeBase.is_deleted.is_(False))

            result = await db.execute(stmt)
            row = result.one()

            return success(data={
                "total_knowledge_bases": row.total_knowledge_bases,
                "total_documents": row.total_documents,
                "total_chunks": row.total_chunks,
                "total_size_bytes": row.total_size_bytes,
            })

        @router.get("/{kb_id}", summary="获取知识库详情")
        @action_read("action.ai_knowledge_base.detail")
        async def get_knowledge_base_detail(
            request: Request,
            db: DbSession,
            kb_id: int,
            admin: ActiveAdmin,
        ):
            """
            获取知识库详情

            权限: ai_knowledge_base:detail
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            result = kb.to_dict()
            result["embedding_model_name"] = None
            try:
                if kb.embedding_model:
                    result["embedding_model_name"] = kb.embedding_model.name
            except Exception:
                pass

            return success(data=result)

        @router.delete("/{kb_id}", summary="强制删除知识库")
        @action_delete("action.ai_knowledge_base.delete")
        async def delete_knowledge_base(
            request: Request,
            db: DbSession,
            kb_id: int,
            admin: ActiveAdmin,
        ):
            """
            强制删除知识库（平台管理权限）

            权限: ai_knowledge_base:delete
            """
            service = AdminKnowledgeBaseService(db)
            kb = await service.get_by_id(kb_id)
            if not kb:
                raise NotFoundException(message=_("knowledge_base.error.not_found"))

            await service.delete(kb_id)
            await db.commit()

            return deleted(message=_("knowledge_base.deleted"))


# 导出路由器
router = AdminKnowledgeBaseController.get_router()

__all__ = ["router", "AdminKnowledgeBaseController"]
