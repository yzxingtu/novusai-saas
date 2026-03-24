# File Map

## 前端

- `frontend/apps/web-antd/src/views/admin/ai/knowledge-bases/index.vue`
- `frontend/apps/web-antd/src/views/admin/ai/knowledge-bases/data.ts`
- `frontend/apps/web-antd/src/views/admin/ai/knowledge-bases/modules/form.vue`
- `frontend/apps/web-antd/src/views/admin/ai/knowledge-bases/modules/detail.vue`
- `frontend/apps/web-antd/src/views/tenant/ai/knowledge-bases/index.vue`
- `frontend/apps/web-antd/src/views/tenant/ai/knowledge-bases/data.ts`
- `frontend/apps/web-antd/src/views/tenant/ai/knowledge-bases/modules/KnowledgeBaseForm.vue`
- `frontend/apps/web-antd/src/views/tenant/ai/knowledge-bases/modules/KnowledgeBaseDetail.vue`
- `frontend/apps/web-antd/src/components/business/knowledge-document-picker/KnowledgeDocumentPicker.vue`
- `frontend/apps/web-antd/src/views/admin/ai/agents/detail.vue`
- `frontend/apps/web-antd/src/views/tenant/ai/agents/detail.vue`

## 前端 API

- `frontend/apps/web-antd/src/api/admin/knowledge-bases.ts`
- `frontend/apps/web-antd/src/api/tenant/knowledge-bases.ts`

## 后端 API / Service / Model

- `backend/app/api/admin/knowledge_bases.py`
- `backend/app/api/tenant/knowledge_bases.py`
- `backend/app/api/admin/agents.py`
- `backend/app/api/tenant/_agent_kbs.py`
- `backend/app/services/ai/knowledge_base_service.py`
- `backend/app/services/ai/agent_kb_binding_service.py`
- `backend/app/services/ai/tenant_platform_kb_suppression_service.py`
- `backend/app/models/ai/document_chunk.py`
- `backend/app/models/ai/knowledge_base.py`
- `backend/app/models/ai/knowledge_document.py`
- `backend/app/models/tenant/attachment.py`
- `backend/app/schemas/ai/knowledge_base.py`
- `backend/app/services/tenant/attachment_service.py`
- `backend/app/storage/__init__.py`
- `backend/migrations/versions/20260211_0010_add_knowledge_base_tables.py`

## RAG 管线

- `backend/app/ai/rag/parser.py`
- `backend/app/ai/rag/processor.py`
- `backend/app/ai/rag/chunker.py`
- `backend/app/ai/rag/embedding.py`
- `backend/app/ai/rag/retriever.py`
- `backend/app/ai/rag/query_rewriter.py`
- `backend/app/ai/rag/reranker.py`
- `backend/app/ai/rag/context_builder.py`
- `backend/app/ai/rag/vision_describer.py`
- `backend/app/ai/rag_injector.py`
