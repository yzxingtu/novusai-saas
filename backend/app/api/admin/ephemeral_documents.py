"""
Ephemeral document debug API (admin) / 临时资料文档调试 API（管理端）
"""

from fastapi import Query
from sqlalchemy import func, select

from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.response import paginated, success
from app.enums.rbac import PermissionScope
from app.models.ai.ephemeral_document import EphemeralDocument
from app.rbac.decorators import action_create, action_read, permission_resource
from app.services.ai.ephemeral_document_service import EphemeralDocumentService


@permission_resource(
    resource="ai_ephemeral_document",
    name="menu.admin.ai_knowledge_base",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_knowledge_base",
)
class AdminEphemeralDocumentController(GlobalController):
    prefix = "/ai/ephemeral-rag/documents"
    tags = ["AI Ephemeral Documents Debug"]

    def _register_routes(self) -> None:
        router = self.router

        @router.get("", summary="临时资料文档列表")
        @action_read("action.ai_ephemeral_document.list")
        async def list_ephemeral_documents(
            db: DbSession,
            admin: ActiveAdmin,
            tenant_id: int | None = Query(None),
            conversation_id: int | None = Query(None),
            agent_id: int | None = Query(None),
            user_id: int | None = Query(None),
            scope_type: str | None = Query(None),
            status: str | None = Query(None),
            page: int = Query(1, ge=1),
            page_size: int = Query(20, ge=1, le=100),
        ):
            _ = admin
            stmt = select(EphemeralDocument).where(
                EphemeralDocument.is_deleted.is_(False)
            )
            count_stmt = select(func.count(EphemeralDocument.id)).where(
                EphemeralDocument.is_deleted.is_(False)
            )

            if tenant_id is not None:
                stmt = stmt.where(EphemeralDocument.tenant_id == tenant_id)
                count_stmt = count_stmt.where(EphemeralDocument.tenant_id == tenant_id)
            if conversation_id is not None:
                stmt = stmt.where(EphemeralDocument.conversation_id == conversation_id)
                count_stmt = count_stmt.where(EphemeralDocument.conversation_id == conversation_id)
            if agent_id is not None:
                stmt = stmt.where(EphemeralDocument.agent_id == agent_id)
                count_stmt = count_stmt.where(EphemeralDocument.agent_id == agent_id)
            if user_id is not None:
                stmt = stmt.where(EphemeralDocument.user_id == user_id)
                count_stmt = count_stmt.where(EphemeralDocument.user_id == user_id)
            if scope_type:
                stmt = stmt.where(EphemeralDocument.scope_type == scope_type)
                count_stmt = count_stmt.where(EphemeralDocument.scope_type == scope_type)
            if status:
                stmt = stmt.where(EphemeralDocument.status == status)
                count_stmt = count_stmt.where(EphemeralDocument.status == status)

            stmt = stmt.order_by(EphemeralDocument.updated_at.desc(), EphemeralDocument.id.desc())
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)

            items = list((await db.execute(stmt)).scalars().all())
            total = int((await db.execute(count_stmt)).scalar() or 0)
            payload = [
                {
                    "id": item.id,
                    "tenant_id": item.tenant_id,
                    "conversation_id": item.conversation_id,
                    "agent_id": item.agent_id,
                    "user_id": item.user_id,
                    "scope_type": item.scope_type,
                    "scope_key": item.scope_key,
                    "title": item.title,
                    "content_kind": item.content_kind,
                    "source_ref": item.source_ref,
                    "status": item.status,
                    "expires_at": item.expires_at,
                    "promoted_knowledge_base_id": item.promoted_knowledge_base_id,
                    "promoted_document_id": item.promoted_document_id,
                    "last_used_at": item.last_used_at,
                    "updated_at": item.updated_at,
                    "created_at": item.created_at,
                }
                for item in items
            ]
            return paginated(items=payload, total=total, page=page, page_size=page_size)

        @router.get("/{document_id}", summary="临时资料文档详情")
        @action_read("action.ai_ephemeral_document.detail")
        async def get_ephemeral_document(
            document_id: int,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            _ = admin
            item = await db.get(EphemeralDocument, document_id)
            if item is None or item.is_deleted:
                return success(data=None)
            return success(
                data={
                    "id": item.id,
                    "tenant_id": item.tenant_id,
                    "conversation_id": item.conversation_id,
                    "agent_id": item.agent_id,
                    "user_id": item.user_id,
                    "scope_type": item.scope_type,
                    "scope_key": item.scope_key,
                    "title": item.title,
                    "content_kind": item.content_kind,
                    "content": item.content,
                    "source_ref": item.source_ref,
                    "status": item.status,
                    "expires_at": item.expires_at,
                    "promoted_knowledge_base_id": item.promoted_knowledge_base_id,
                    "promoted_document_id": item.promoted_document_id,
                    "last_used_at": item.last_used_at,
                    "updated_at": item.updated_at,
                    "created_at": item.created_at,
                }
            )

        @router.post("/{document_id}/promote", summary="将临时资料提升为正式知识库文档")
        @action_create("action.ai_ephemeral_document.promote")
        async def promote_ephemeral_document(
            document_id: int,
            knowledge_base_id: int,
            db: DbSession,
            admin: ActiveAdmin,
        ):
            _ = admin
            item = await db.get(EphemeralDocument, document_id)
            if item is None or item.is_deleted:
                return success(data=None)
            service = EphemeralDocumentService(db, tenant_id=int(item.tenant_id or 0))
            document = await service.promote_to_knowledge_base(
                ephemeral_id=document_id,
                knowledge_base_id=knowledge_base_id,
            )
            await db.commit()
            return success(
                data={
                    "document_id": document.id,
                    "knowledge_base_id": knowledge_base_id,
                    "status": document.status,
                }
            )


router = AdminEphemeralDocumentController.get_router()


__all__ = ["AdminEphemeralDocumentController", "router"]
