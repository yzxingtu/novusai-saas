# Architecture And Runtime

## 能力分层

### 知识库资源层

- 管理端支持跨企业查看、创建、编辑、删除知识库，并支持资源作用域与企业分配
- 企业端支持创建和维护本企业自有知识库，同时可只读查看平台下发给本企业的知识库
- 知识库模型使用 `scope + owner_tenant_id + resource_tenant_assignments` 表达投放和归属
- 企业端是否可编辑，不看 `scope` 猜测，只看 `owner_tenant_id` 是否等于当前企业

### 知识库配置层

- 必配 `embedding_model_id`
- 可选 `vision_model_id` / `audio_model_id` / `video_model_id`
- 支持 `extract_images`
- 支持 `chunk_size` / `chunk_overlap` / `chunk_strategy`
- KB 表上仍保留 `search_mode` / `top_k` / `score_threshold`，但主要用于兼容和检索测试

### 文档录入层

- 文件上传
- 直接文本粘贴
- 单条 Q&A 手工录入
- Q&A 批量导入（CSV / XLSX）
- URL 网页导入

### 临时资料侧车层 / Ephemeral RAG lane

- 正式 KB 之外，新增 `EphemeralDocument` 作为临时资料真源
- 支持：
  - conversation-scoped
  - agent workspace scoped
  - tenant private scratch
- 临时资料允许：
  - HTML
  - Markdown
  - CSV
  - Text
  - URL 正文
- 当前前端主入口在 AI Chat composer 的 scratch / 临时资料入口，不应再另造一套脱离会话的临时 RAG UI 协议
- 临时资料检索复用正式 parser / chunker / retriever
- 临时资料 citation 必须标记为 `ephemeral_doc`
- 提升为正式文档时，必须走：
  - `EphemeralDocumentService.promote_to_knowledge_base`
  - `KnowledgeDocument`
  - `process_document`

### 文档处理层

- 文档状态：`pending / parsing / chunking / embedding / completed / error`
- 上传后通过 Celery 异步执行 `process_document`
- 前端通过 WebSocket 监听 `ai.kb_doc_progress`
- 也提供 Redis 进度接口作为兜底
- 支持失败重试
- 支持整库重建索引（reindex）
- 支持分块预览

### 存储与索引层

- 当前向量主存储是 PostgreSQL `pgvector`，不是外部向量库
- `document_chunks` 同时保存 `content` 原文、`embedding` 向量、`metadata`
- 向量检索走 `DocumentChunk.embedding.cosine_distance(...)`
- 关键词检索走 PostgreSQL `content_tsv` + GIN
- 混合检索在应用层做 per-KB 独立召回 + RRF 融合
- Redis 仅用于文档处理进度和检索结果缓存，不持久化向量
- 上传文件走附件系统；原始文件在 `attachments` + 存储驱动，`knowledge_documents.attachment_id` 只保存关联
- 直接文本 / URL / Q&A 可无附件，原始输入保存在 `metadata_extra`，供解析与 reindex 使用

### 多模态解析层

- 支持：`txt / md / pdf / docx / csv / xlsx / html / pptx`
- 支持图片：`.jpg .jpeg .png .webp .gif`
- 支持音频：`.mp3 .wav .m4a .flac .aac`
- 支持视频：`.mp4 .webm .mov .avi .mkv`
- PDF 可按 `extract_images` 提取嵌入图片并走 Vision 描述
- 显式上传的图片文件始终走 Vision 描述，不依赖 `extract_images`
- 音频 / 视频如果最终拿不到文本，会明确进入 `error`，不会假成功

### 检索与 Agent 集成层

- 知识库详情页支持检索测试
- 检索测试接口支持 `query / top_k / score_threshold / search_mode`
- 运行时 Agent 问答真正使用的是 `Agent.rag_config`
- 多知识库运行时按 KB 独立召回，再做全局融合
- 绑定权重 `AgentKnowledgeBaseBinding.weight` 已真实参与融合排序
- 支持 `rewrite_strategy`、`reranker_enabled`、`context_token_ratio`
- Agent 详情页有独立 `知识库 (RAG)` tab，维护 `Agent.rag_config`
- Agent 详情页有 `知识库` 绑定 tab，维护 KB 绑定、权重、启用状态
- 企业端对平台下发智能体可以追加本企业知识库绑定，也可对平台全局知识库做“本企业不使用”停用
- 正式 KB 路径已补：
  - exact technical term keyword boost
  - relevance-gap filtering

## 核心原则

- 运行时 RAG 配置中心是 `Agent.rag_config`，不是 `KnowledgeBase.search_mode/top_k/score_threshold`
- 企业端对平台下发知识库默认只读，变更操作必须先判断归属企业
- 知识库文档上传必须复用附件系统，不能自造上传链路
- 分析问题前先拆清楚“原始文件存储 / 文档记录 / chunk 原文 / embedding 向量 / Redis 缓存”这 5 层
- 向量持久化真源是 PostgreSQL `document_chunks.embedding`
- 文档处理失败必须进入明确错误状态，不能出现“无 chunk 但状态成功”
- 删除文档、重建索引后要记得失效检索缓存
- 知识库绑定权重不是展示字段，改动时要考虑真实检索融合影响
- 检索测试是 KB 级调试能力，不等于真实 Agent 运行时最终效果
- 临时资料不是正式 KB，不能把 `EphemeralDocument` 当成 `KnowledgeBase` 替代品
- `Agent.rag_config` 仍然是正式 KB 运行时真相；临时资料只作为 sidecar context lane

## 当前实现边界

- KB 级 `search_mode/top_k/score_threshold` 仍在模型和接口中保留，但主要是兼容字段
- 真实对话时优先使用 Agent 级 `rag_config`
- 检索测试接口当前走 `VectorRetriever.search(...)`，更偏 KB 调试，不等同完整 Agent 运行时的多 KB 融合链路
- 企业端只能上传、删除、重试、重建“自有知识库”的文档；平台下发知识库在企业端是只读
- ORM 模型写成 `Vector()` 且 KB 表保留 `embedding_dimensions`，但最早迁移实际建列是 `document_chunks.embedding vector(1536)`
- 如果切换非 `1536` 维 embedding 模型，必须先核对 `document_chunks.embedding` 列类型、HNSW 索引和历史数据兼容性
- chunk 原文与向量同表存储，原始文件仍在附件系统；排查“检索不到”时不要只看 `knowledge_documents`
