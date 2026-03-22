---
name: knowledge-base-rag
description: NovusAI 知识库 / RAG 技能。当需要开发、修复、审查知识库 CRUD、文档导入、重建索引、检索测试、多模态解析、智能体知识库绑定或 Agent.rag_config 时，参考此技能。
---

# 知识库 / RAG 技能

## 何时使用

- 新增或修改管理端 / 企业端知识库页面
- 调整知识库 CRUD、文档上传、文档处理、分块预览、检索测试
- 排查为什么文档没有出 chunk、没有 embedding、检索不到内容
- 开发或修复 Agent 的知识库绑定、平台知识库企业停用、RAG 配置面板
- 修改多模态知识库解析：PDF 图片、PPTX、图片、音频、视频
- 审查知识库相关改动是否符合当前架构

## 当前能力总览

### 1. 知识库资源层

- 管理端支持跨企业查看、创建、编辑、删除知识库，并支持资源作用域与企业分配
- 企业端支持创建和维护本企业自有知识库，同时可只读查看平台下发给本企业的知识库
- 知识库模型使用 `scope + owner_tenant_id + resource_tenant_assignments` 表达投放和归属
- 企业端是否可编辑，不看 `scope` 猜测，只看 `owner_tenant_id` 是否等于当前企业

### 2. 知识库配置层

- 必配 `embedding_model_id`
- 可选 `vision_model_id` / `audio_model_id` / `video_model_id`
- 支持 `extract_images`
- 支持 `chunk_size` / `chunk_overlap` / `chunk_strategy`
- KB 表上仍保留 `search_mode` / `top_k` / `score_threshold`，但现在主要用于兼容和检索测试

### 3. 文档录入层

- 文件上传
- 直接文本粘贴
- 单条 Q&A 手工录入
- Q&A 批量导入（CSV / XLSX）
- URL 网页导入

### 4. 文档处理层

- 文档状态：`pending / parsing / chunking / embedding / completed / error`
- 上传后通过 Celery 异步执行 `process_document`
- 前端通过 WebSocket 监听 `ai.kb_doc_progress`
- 也提供 Redis 进度接口作为兜底
- 支持失败重试
- 支持整库重建索引（reindex）
- 支持分块预览

### 5. 存储与索引层

- 不使用 Milvus / Qdrant / FAISS 这类外部向量库；当前向量主存储是 PostgreSQL `pgvector`
- `document_chunks` 同时保存 `content` 原文、`embedding` 向量、`metadata`
- 向量检索走 `DocumentChunk.embedding.cosine_distance(...)`
- 关键词检索走 PostgreSQL `content_tsv` + GIN
- 混合检索在应用层做 per-KB 独立召回 + RRF 融合
- Redis 仅用于文档处理进度和检索结果缓存，不持久化向量
- 上传文件走附件系统；原始文件在 `attachments` + 存储驱动，`knowledge_documents.attachment_id` 只保存关联
- 直接文本 / URL / Q&A 可无附件，原始输入保存在 `metadata_extra`，供解析与 reindex 使用

### 6. 多模态解析层

- 支持：`txt / md / pdf / docx / csv / xlsx / html / pptx`
- 支持图片：`.jpg .jpeg .png .webp .gif`
- 支持音频：`.mp3 .wav .m4a .flac .aac`
- 支持视频：`.mp4 .webm .mov .avi .mkv`
- PDF 可按 `extract_images` 提取嵌入图片并走 Vision 描述
- 显式上传的图片文件始终走 Vision 描述，不依赖 `extract_images`
- 音频 / 视频如果最终拿不到文本，会明确进入 `error`，不会假成功

### 7. 检索与 RAG 层

- 知识库详情页支持检索测试
- 检索测试接口支持 `query / top_k / score_threshold / search_mode`
- 运行时 Agent 问答真正使用的是 `Agent.rag_config`
- 多知识库运行时按 KB 独立召回，再做全局融合
- 绑定权重 `AgentKnowledgeBaseBinding.weight` 已真实参与融合排序
- 支持 `rewrite_strategy`、`reranker_enabled`、`context_token_ratio`

### 8. Agent 集成层

- Agent 详情页有独立 `知识库 (RAG)` tab，维护 `Agent.rag_config`
- Agent 详情页有 `知识库` 绑定 tab，维护 KB 绑定、权重、启用状态
- 企业端对平台下发智能体支持两类操作：
- 可追加本企业知识库绑定
- 可对平台全局知识库做“本企业不使用”停用

## 核心原则

- 运行时 RAG 配置中心是 `Agent.rag_config`，不是 `KnowledgeBase.search_mode/top_k/score_threshold`
- 企业端对平台下发知识库默认只读，变更操作必须先判断归属企业
- 知识库文档上传必须复用附件系统，不能自造上传链路
- 先区分“原始文件存储 / 文档记录 / chunk 原文 / embedding 向量 / Redis 缓存”这 5 层，再分析问题
- 向量持久化真源是 PostgreSQL `document_chunks.embedding`，不是 Redis，不是附件系统
- 文档处理失败必须进入明确错误状态，不能出现“无 chunk 但状态成功”
- 删除文档、重建索引后要记得失效检索缓存
- 知识库绑定权重不是展示字段，改动时要考虑真实检索融合影响
- 检索测试是 KB 级调试能力，不等于真实 Agent 运行时最终效果

## 标准流程

### A. 新建知识库

1. 选择端：admin 或 tenant
2. 创建知识库基础信息：名称、描述、作用域/归属
3. 选择 Embedding 模型
4. 按需要配置 Vision / Audio / Video 模型
5. 配置 `extract_images`
6. 配置 `chunk_size / chunk_overlap / chunk_strategy`
7. 保存后进入详情抽屉导入文档

### B. 导入文档

1. 打开知识库详情抽屉
2. 选择录入方式：
- 上传文件
- 粘贴文本
- 单条 Q&A
- 批量 Q&A
- URL 导入
3. 等待异步处理进入 `completed`
4. 如失败，先看 `error_stage / error_message`
5. 必要时使用重试或整库 reindex

### C. 验证知识库是否可用

1. 在知识库详情页执行检索测试
2. 调整 `search_mode / top_k / score_threshold`
3. 检查返回的 chunk、分数、来源文档
4. 必要时打开文档分块预览，确认分块内容是否合理
5. 如果检索测试正常但 Agent 效果不对，再转去看 `Agent.rag_config`

### D. 给 Agent 接入知识库

1. 打开 Agent 详情页
2. 在 `知识库` tab 绑定一个或多个知识库
3. 配置每个绑定的 `weight / enabled`
4. 在 `知识库 (RAG)` tab 配置：
- `search_mode`
- `rewrite_strategy`
- `top_k`
- `score_threshold`
- `reranker_enabled`
- `context_token_ratio`
5. 用真实对话验证最终效果

### E. 企业端处理平台知识库

1. 如果是平台下发智能体，不允许改平台全局绑定
2. 可以追加本企业知识库
3. 对平台全局知识库可设置“本企业不使用”
4. 该停用仅影响当前企业的 RAG，不回写管理端配置

## 当前实现边界

- KB 级 `search_mode/top_k/score_threshold` 仍在模型和接口中保留，但主要是兼容字段
- 真实对话时优先使用 Agent 级 `rag_config`
- 检索测试接口当前走 `VectorRetriever.search(...)`，更偏 KB 调试，不等同完整 Agent 运行时的多 KB 融合链路
- 企业端只能上传/删除/重试/重建“自有知识库”的文档；平台下发知识库在企业端是只读
- ORM 模型写成 `Vector()` 且 KB 表保留 `embedding_dimensions`，但最早迁移实际建列是 `document_chunks.embedding vector(1536)`；在确认后续迁移修正前，不要假设任意维度 embedding 可以直接上线
- 如果切换非 `1536` 维 embedding 模型，必须先核对 `document_chunks.embedding` 列类型、HNSW 索引和历史数据兼容性
- chunk 原文与向量同表存储，原始文件仍在附件系统；排查“检索不到”时不要只看 `knowledge_documents`

## 常见坑

- 不要再用 `scope === 'all_tenants'` 判断是不是企业自有知识库，必须看 `tenant_id / owner_tenant_id`
- 不要把 KB 表上的检索参数当成最终运行时真源
- 不要把 Redis 检索缓存误当成向量存储
- 不要把 `embedding_dimensions` 字段存在误当成数据库已经支持多维度混用
- 不要只看 `knowledge_documents` 就判断“文档内容在哪”；真正召回的是 `document_chunks`
- 不要忘记重建索引和删除文档后的缓存失效
- 不要绕过 `KnowledgeDocumentPicker` 和标准上传 API 自己拼一套录入方式
- 不要宣称“音频/视频知识库已完全可用”，除非当前部署环境里的描述模型确实能稳定产出文本
- 不要把“检索测试通过”误当成“Agent 真实回答一定正确”，两者配置层级不同

## 关键文件

### 前端

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

### 前端 API

- `frontend/apps/web-antd/src/api/admin/knowledge-bases.ts`
- `frontend/apps/web-antd/src/api/tenant/knowledge-bases.ts`

### 后端 API / Service / Model

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

### RAG 管线

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

## 推荐排障顺序

1. 先看知识库是不是当前端可见且可操作
2. 再看文档状态是不是 `completed`
3. 再看文档是否真的产出了 chunk
4. 再看检索测试是否能召回
5. 再看 Agent 是否真的绑定了正确的知识库
6. 最后看 `Agent.rag_config`、改写、重排序、上下文预算

## 参考

- `../novusai-saas/references/ai-module.md`
- `../novusai-saas/references/multimodal-rag.md`
- `../novusai-saas/references/multimodal-model-usage.md`
- `../novusai-saas/references/upload-storage-spec.md`
- `../attachment-storage/SKILL.md`
