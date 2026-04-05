"""
智能体知识库绑定 Service / Agent KB Binding Service
"""

from typing import Any

from sqlalchemy import select

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent_kb_binding import AgentKnowledgeBaseBinding
from app.models.tenant.tenant import Tenant
from app.repositories.ai.agent_kb_binding_repository import AgentKBBindingRepository
from app.repositories.ai.agent_repository import AgentRepository
from app.services.ai.tenant_platform_kb_suppression_service import (
    load_suppressed_platform_kb_ids,
)

logger = LogManager.get_logger("ai")


class AgentKBBindingService:
    """
    智能体知识库绑定 Service / Agent KB binding service.

    管理 Agent 与 KnowledgeBase 的 M:N 关系
    """

    def __init__(self, db, tenant_id: int | None):
        self.db = db
        self.tenant_id = tenant_id
        if tenant_id is not None:
            self.binding_repo = AgentKBBindingRepository(db, tenant_id)
            self.agent_repo = AgentRepository(db, tenant_id)
        else:
            from app.repositories.ai.agent_repository import AdminAgentRepository

            self.binding_repo = AgentKBBindingRepository(db, None)
            self.agent_repo = AdminAgentRepository(db)  # type: ignore[assignment]  # 类型存根 / typing stub

    async def _get_kb_repo(self):
        """延迟获取 KB 仓库（避免循环导入） / Lazy get KB repo (avoid circular import)."""
        from app.repositories.ai.knowledge_base_repository import (
            AdminKnowledgeBaseRepository,
            KnowledgeBaseRepository,
        )

        if self.tenant_id is not None:
            return KnowledgeBaseRepository(self.db, tenant_id=self.tenant_id)
        return AdminKnowledgeBaseRepository(self.db)

    def _binding_to_item(
        self,
        binding: AgentKnowledgeBaseBinding,
        *,
        owner_tenant_name_map: dict[int, str] | None = None,
    ) -> dict[str, Any]:
        """ORM 绑定行 -> API 字典（含 binding_scope）/ Binding row to API dict."""
        item: dict[str, Any] = {
            "id": binding.id,
            "agent_id": binding.agent_id,
            "knowledge_base_id": binding.knowledge_base_id,
            "weight": binding.weight,
            "enabled": binding.enabled,
            "sort_order": binding.sort_order,
            "platform_suppressed": False,
            "binding_scope": ("platform" if binding.tenant_id is None else "tenant"),
            "kb_name": None,
            "kb_description": None,
            "kb_scope": None,
            "kb_visibility": None,
            "kb_document_count": None,
            "kb_owner_tenant_id": None,
            "kb_owner_tenant_name": None,
        }
        if binding.knowledge_base:
            kb = binding.knowledge_base
            item["kb_name"] = kb.name
            item["kb_description"] = kb.description
            item["kb_scope"] = getattr(kb, "scope", None)
            item["kb_visibility"] = getattr(kb, "visibility", None)
            item["kb_document_count"] = getattr(kb, "document_count", None)
            item["kb_chunk_strategy"] = getattr(kb, "chunk_strategy", None)
            item["kb_embedding_model_id"] = getattr(kb, "embedding_model_id", None)
            item["kb_embedding_dimensions"] = getattr(kb, "embedding_dimensions", None)
            owner_tenant_id = getattr(kb, "owner_tenant_id", None)
            item["kb_owner_tenant_id"] = owner_tenant_id
            if owner_tenant_id is not None:
                item["kb_owner_tenant_name"] = (owner_tenant_name_map or {}).get(
                    int(owner_tenant_id)
                )
            embedding_model = getattr(kb, "embedding_model", None)
            item["kb_embedding_model_name"] = getattr(embedding_model, "name", None)
        else:
            item["kb_chunk_strategy"] = None
            item["kb_embedding_model_id"] = None
            item["kb_embedding_dimensions"] = None
            item["kb_embedding_model_name"] = None
        return item

    async def _load_owner_tenant_name_map(
        self,
        bindings: list[AgentKnowledgeBaseBinding],
    ) -> dict[int, str]:
        """批量加载绑定知识库的归属企业名称 / Batch load owner tenant names for bound KBs."""
        owner_ids = {
            int(owner_tenant_id)
            for binding in bindings
            if (kb := getattr(binding, "knowledge_base", None)) is not None
            if (owner_tenant_id := getattr(kb, "owner_tenant_id", None)) is not None
        }
        if not owner_ids:
            return {}

        stmt = select(Tenant.id, Tenant.name).where(
            Tenant.id.in_(owner_ids),
            Tenant.is_deleted.is_(False),
        )
        rows = (await self.db.execute(stmt)).all()
        return {int(tenant_id): str(name) for tenant_id, name in rows}

    async def _filter_bindings_by_kb_visibility(
        self,
        bindings: list[AgentKnowledgeBaseBinding],
    ) -> list[AgentKnowledgeBaseBinding]:
        """企业端读取绑定时复验 KB 当前可见性 / Re-check KB visibility when tenant reads bindings."""
        if self.tenant_id is None or not bindings:
            return list(bindings)

        kb_repo = await self._get_kb_repo()
        accessible_ids = await kb_repo.filter_accessible_ids(
            [binding.knowledge_base_id for binding in bindings]
        )
        return [
            binding
            for binding in bindings
            if binding.knowledge_base_id in accessible_ids
        ]

    async def get_agent_kb_bindings(
        self,
        agent_id: int,
        *,
        merge_platform_bindings: bool = False,
    ) -> list[dict[str, Any]]:
        """
        获取智能体的所有知识库绑定（含 KnowledgeBase 详情）/ Get agent KB bindings with KB details.

        Args:
            agent_id: 智能体 ID
            merge_platform_bindings: 企业上下文下合并「平台全局绑定 + 本企业叠加」/ Merge platform + tenant overlay

        Returns:
            绑定列表（含 KnowledgeBase 名称、描述等详情）
        """
        if merge_platform_bindings and self.tenant_id is not None:
            bindings = await self.binding_repo.list_merged_platform_and_tenant(
                agent_id, self.tenant_id
            )
            suppressed = await load_suppressed_platform_kb_ids(
                self.db, self.tenant_id, agent_id
            )
        else:
            bindings = await self.binding_repo.get_by_agent_id(agent_id)
            suppressed = set()

        bindings = await self._filter_bindings_by_kb_visibility(bindings)
        owner_tenant_name_map = await self._load_owner_tenant_name_map(bindings)

        items: list[dict[str, Any]] = []
        for b in bindings:
            item = self._binding_to_item(
                b,
                owner_tenant_name_map=owner_tenant_name_map,
            )
            if merge_platform_bindings and self.tenant_id is not None:
                item["platform_suppressed"] = (
                    item["binding_scope"] == "platform"
                    and item["knowledge_base_id"] in suppressed
                )
            else:
                item["platform_suppressed"] = False
            items.append(item)
        return items

    async def get_agent_kb_bindings_with_metadata(
        self,
        agent_id: int,
        *,
        merge_platform_bindings: bool = False,
    ) -> list[dict[str, Any]]:
        """
        获取知识库绑定及能力描述所需元数据 / Get KB bindings with capability metadata.

        Reuses the public binding payload and normalizes field names expected by
        capability awareness.
        复用现有绑定返回结构，并归一化能力感知需要的字段名。
        """
        bindings = await self.get_agent_kb_bindings(
            agent_id,
            merge_platform_bindings=merge_platform_bindings,
        )

        normalized_items: list[dict[str, Any]] = []
        for binding in bindings:
            kb_id = binding.get("kb_id")
            if kb_id is None:
                kb_id = binding.get("knowledge_base_id")
            if kb_id is None:
                continue

            normalized_item = dict(binding)
            normalized_item["kb_id"] = int(kb_id)
            normalized_item["knowledge_base_id"] = int(kb_id)
            normalized_item["kb_name"] = str(binding.get("kb_name") or "").strip()
            normalized_item["kb_description"] = str(
                binding.get("kb_description") or ""
            ).strip()
            try:
                normalized_item["kb_document_count"] = int(
                    binding.get("kb_document_count") or 0
                )
            except (TypeError, ValueError):
                normalized_item["kb_document_count"] = 0

            normalized_items.append(normalized_item)

        return normalized_items

    def serialize_binding_public(
        self, binding: AgentKnowledgeBaseBinding
    ) -> dict[str, Any]:
        """单条绑定 API 响应（与列表字段一致）/ Single binding payload for API responses."""
        return self._binding_to_item(binding)

    async def _validate_kb_accessible(self, knowledge_base_id: int) -> None:
        """校验知识库是否可访问（存在 + 权限范围内） / Validate KB accessible (exists + in scope)."""
        kb_repo = await self._get_kb_repo()
        kb = await kb_repo.get_by_id(knowledge_base_id)
        if not kb:
            raise NotFoundException(message=_("agent_kb_binding.error.kb_not_found"))

    async def bind_kb(
        self,
        agent_id: int,
        knowledge_base_id: int,
        weight: float = 1.0,
        sort_order: int = 0,
        enabled: bool = True,
    ) -> AgentKnowledgeBaseBinding:
        """
        绑定知识库到智能体 / Bind knowledge base to agent.

        Args:
            agent_id: 智能体 ID
            knowledge_base_id: 知识库 ID
            weight: 检索权重（0.1~2.0）
            sort_order: 排序
            enabled: 是否启用

        Returns:
            AgentKnowledgeBaseBinding 实例
        """
        agent = await self.agent_repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent_kb_binding.error.agent_not_found"))

        await self._validate_kb_accessible(knowledge_base_id)

        existing_any = await self.binding_repo.get_binding_any(
            agent_id, knowledge_base_id
        )
        if existing_any:
            raise BusinessException(message=_("agent_kb_binding.error.already_bound"))

        binding = await self.binding_repo.create(
            {
                "agent_id": agent_id,
                "knowledge_base_id": knowledge_base_id,
                "tenant_id": self.tenant_id,
                "weight": weight,
                "sort_order": sort_order,
                "enabled": enabled,
            }
        )

        logger.info(
            "KnowledgeBase {} bound to agent {} (tenant={})",
            knowledge_base_id,
            agent_id,
            self.tenant_id,
        )

        return binding

    async def unbind_kb(self, agent_id: int, knowledge_base_id: int) -> None:
        """
        解绑知识库 / Unbind knowledge base from agent.

        Args:
            agent_id: 智能体 ID
            knowledge_base_id: 知识库 ID
        """
        binding = await self.binding_repo.get_binding(agent_id, knowledge_base_id)
        if not binding:
            raise NotFoundException(
                message=_("agent_kb_binding.error.binding_not_found")
            )

        # KB bindings are active rows, not recycle-bin entries. Use a direct hard delete
        # instead of permanent_delete(), which only removes already-soft-deleted records.
        deleted = await self.binding_repo.delete(binding.id, soft=False)
        if not deleted:
            raise BusinessException(message=_("common.failed"))

        logger.info(
            "KnowledgeBase {} unbound from agent {} (tenant={})",
            knowledge_base_id,
            agent_id,
            self.tenant_id,
        )

    async def batch_bind(
        self,
        agent_id: int,
        knowledge_base_ids: list[int],
    ) -> list[AgentKnowledgeBaseBinding]:
        """
        批量绑定知识库（替换模式：先清空再批量插入）/ Batch bind KBs (replace mode: clear then insert).

        Args:
            agent_id: 智能体 ID
            knowledge_base_ids: 知识库 ID 列表（有序）

        Returns:
            新绑定列表
        """
        agent = await self.agent_repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent_kb_binding.error.agent_not_found"))

        kb_ids = list(knowledge_base_ids)
        if agent.owner_tenant_id is None and self.tenant_id is not None:
            filtered: list[int] = []
            for kb_id in kb_ids:
                row = await self.binding_repo.get_binding_any(agent_id, kb_id)
                if row is not None and row.tenant_id is None:
                    continue
                filtered.append(kb_id)
            kb_ids = filtered

        # 校验所有 KB 可访问
        for kb_id in kb_ids:
            await self._validate_kb_accessible(kb_id)

        async with self.db.begin_nested():
            await self.binding_repo.delete_by_agent_id(agent_id)

            bindings = []
            for idx, kb_id in enumerate(kb_ids):
                binding = await self.binding_repo.create(
                    {
                        "agent_id": agent_id,
                        "knowledge_base_id": kb_id,
                        "tenant_id": self.tenant_id,
                        "weight": 1.0,
                        "sort_order": idx,
                        "enabled": True,
                    }
                )
                bindings.append(binding)

        logger.info(
            "Batch bound {} knowledge bases to agent {} (tenant={})",
            len(kb_ids),
            agent_id,
            self.tenant_id,
        )

        return bindings

    async def update_binding(
        self,
        binding_id: int,
        data: dict[str, Any],
    ) -> AgentKnowledgeBaseBinding:
        """
        更新绑定配置 / Update binding config.

        Args:
            binding_id: 绑定 ID
            data: 更新数据（weight / enabled / sort_order）

        Returns:
            更新后的 AgentKnowledgeBaseBinding
        """
        binding = await self.binding_repo.get_by_id(binding_id)
        if not binding:
            raise NotFoundException(
                message=_("agent_kb_binding.error.binding_not_found")
            )

        updated = await self.binding_repo.update(binding_id, data)
        return updated

    async def get_by_id(self, binding_id: int) -> AgentKnowledgeBaseBinding | None:
        """获取绑定详情 / Get binding detail."""
        return await self.binding_repo.get_by_id(binding_id)

    async def delete_all_for_agent(self, agent_id: int) -> int:
        """
        删除智能体的所有知识库绑定（用于版本回滚前清空）/ Delete all KB bindings for agent (e.g. before version rollback).
        """
        return await self.binding_repo.delete_by_agent_id(agent_id)


__all__ = ["AgentKBBindingService"]
