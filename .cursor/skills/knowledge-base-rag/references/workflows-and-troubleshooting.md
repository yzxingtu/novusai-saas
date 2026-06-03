# Workflows And Troubleshooting

## 常规流程

### 新建知识库

1. 选择端：admin 或 tenant
2. 创建知识库基础信息：名称、描述、作用域/归属
3. 选择 Embedding 模型
4. 按需要配置 Vision / Audio / Video 模型
5. 配置 `extract_images`
6. 配置 `chunk_size / chunk_overlap / chunk_strategy`
7. 保存后进入详情抽屉导入文档

### 导入文档

1. 打开知识库详情抽屉
2. 选择录入方式：上传文件、粘贴文本、单条 Q&A、批量 Q&A、URL 导入
3. 等待异步处理进入 `completed`
4. 如失败，先看 `error_stage / error_message`
5. 必要时使用重试或整库 reindex

### 验证知识库是否可用

1. 在知识库详情页执行检索测试
2. 调整 `search_mode / top_k / score_threshold`
3. 检查返回的 chunk、分数、来源文档
4. 必要时打开文档分块预览，确认分块内容是否合理
5. 如果检索测试正常但 Agent 效果不对，再转去看 `Agent.rag_config`

### 给 Agent 接入知识库

1. 打开 Agent 详情页
2. 在 `知识库` tab 绑定一个或多个知识库
3. 配置每个绑定的 `weight / enabled`
4. 在 `知识库 (RAG)` tab 配置 `search_mode`、`rewrite_strategy`、`top_k`、`score_threshold`、`reranker_enabled`、`context_token_ratio`
5. 用真实对话验证最终效果

### 企业端处理平台知识库

1. 平台下发智能体的全局绑定不允许 tenant 直接改写
2. tenant 可以追加本企业知识库
3. tenant 可以对平台全局知识库设置“本企业不使用”
4. 该停用仅影响当前企业的 RAG，不回写管理端配置

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

## 推荐排障顺序

1. 先看知识库是不是当前端可见且可操作
2. 再看文档状态是不是 `completed`
3. 再看文档是否真的产出了 chunk
4. 再看检索测试是否能召回
5. 再看 Agent 是否真的绑定了正确的知识库
6. 最后看 `Agent.rag_config`、改写、重排序、上下文预算
