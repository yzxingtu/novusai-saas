---
name: knowledge-base-rag
description: NovusAI knowledge base and RAG skill. Use when working on knowledge base CRUD, document ingest and reindex, retrieval testing, multimodal parsing, agent knowledge-base binding, or Agent.rag_config runtime behavior.
metadata:
  short-description: Knowledge base and RAG guide
---

# 知识库 / RAG 技能

> 当前 skill 是知识库与 RAG 的入口页，不再把架构、流程、文件索引全部堆在一个 `SKILL.md`。
> 涉及上传链路时，和 [../attachment-storage/SKILL.md](../attachment-storage/SKILL.md) 配合使用。

## 何时使用

- 新增或修改 admin / tenant 知识库页面
- 调整知识库 CRUD、文档导入、重建索引、分块预览、检索测试
- 排查为什么没有 chunk、没有 embedding、检索不到内容
- 调整 Agent 的知识库绑定、平台知识库企业停用、`Agent.rag_config`
- 修改图片、音频、视频、PPTX、PDF 图片提取等多模态知识库解析
- 审查知识库相关改动是否符合当前架构

## 先记住的几条

- 运行时 RAG 配置中心是 `Agent.rag_config`，不是 `KnowledgeBase.search_mode/top_k/score_threshold`
- 企业端是否可编辑平台下发知识库，只看 `owner_tenant_id` / `tenant_id` 归属，不靠 `scope` 猜
- 知识库文档上传必须复用附件系统，不能另起上传链路
- 向量持久化真源是 PostgreSQL `document_chunks.embedding`，不是 Redis，不是附件系统
- 检索测试是 KB 级调试能力，不等于完整 Agent 运行时最终效果

## 推荐阅读顺序

- 架构、能力分层、运行时边界：
  [references/architecture-and-runtime.md](references/architecture-and-runtime.md)
- 日常操作流程、排障顺序、常见坑：
  [references/workflows-and-troubleshooting.md](references/workflows-and-troubleshooting.md)
- 关键前端/后端/RAG 管线路径：
  [references/file-map.md](references/file-map.md)
- 多模态 RAG 细节：
  [../novusai-saas/references/multimodal-rag.md](../novusai-saas/references/multimodal-rag.md)
- 多模态模型与删除依赖：
  [../novusai-saas/references/multimodal-model-usage.md](../novusai-saas/references/multimodal-model-usage.md)
- 知识库所属 AI 模块总规范：
  [../novusai-saas/references/ai-module.md](../novusai-saas/references/ai-module.md)
- 上传、图片、附件：
  [../novusai-saas/references/upload-storage-spec.md](../novusai-saas/references/upload-storage-spec.md)

## 快速判障

1. 先确认当前端是否能看到且允许操作该知识库
2. 再确认文档状态是不是 `completed`
3. 再确认是否真的生成了 chunk 和 embedding
4. 再确认知识库检索测试能否召回
5. 最后再看 Agent 绑定、`Agent.rag_config`、改写、重排序和上下文预算

## 不该在这里停留太久的情况

- 只是附件、图片、预览、存储驱动问题：
  看 [../attachment-storage/SKILL.md](../attachment-storage/SKILL.md)
- 只是项目级总规则或多模块协同问题：
  看 [../novusai-saas/SKILL.md](../novusai-saas/SKILL.md)
