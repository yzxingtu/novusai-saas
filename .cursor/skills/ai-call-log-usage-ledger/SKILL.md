---
name: ai-call-log-usage-ledger
description: NovusAI AI 调用日志与使用量账本。说明 AICallLog 不可变快照、Celery 队列写入（tasks.ai.log_ai_call / ai_gateway）、log_call 与 log_call_async 区别、billing_context、Worker 与 API 代码版本一致、流式对话尾部落日志风险。在排查「调用日志为空」「统计无数据」「unexpected keyword billing_context」、或扩展计费/统计字段时使用。
---

# NovusAI：AI 调用日志与使用量账本

## 何时查阅本技能

- 管理端 / 企业端 / 用户端 **调用日志、用量统计页面无数据**，但对话实际成功。
- Celery / `task_logs` 报错：`log_ai_call_task() got an unexpected keyword argument 'billing_context'` 等 **任务签名与入参不一致**。
- 需要区分 **`log_call`（进程内直写）** 与 **`log_call_async`（队列入库）**。
- 扩展 **`billing_context`**、账本快照列、或统计聚合口径（`AICallLogRepository`）。

---

## 核心数据模型

- **事实表**：`ai_call_logs`（ORM：`app.models.ai.call_log.AICallLog`）。
- **设计目标**：用量与展示尽量 **不随智能体/企业/模型改名或删除而漂移** —— 关键展示与归属字段以 **调用时快照** 写入（如 `agent_name_snapshot`、`billing_tenant_name_snapshot`、`model_name_snapshot`、`provider_name_snapshot` 及发布相关快照等）。
- **旧表**：`ai_usage_stats` 已废弃并由合并迁移删除；统计应基于 **`AICallLog` 聚合**，勿再依赖旧聚合表心智。

---

## 写入路径：默认是队列，不是 HTTP 进程内当场 INSERT

### 1. `log_call_async`（主路径 / Primary path）

- **位置**：`app/services/ai/call_log_service.py` → `CallLogService.log_call_async`。
- **行为**：调用 `app.tasks.ai.log_ai_call_task.delay(...)`，将日志写入任务投递到 Celery。
- **任务**：`tasks.ai.log_ai_call`（`app/tasks/ai.py`），队列 **`ai_gateway`**（与 `async-tasks` 规范一致）。
- **执行环境**：Worker 内使用 **`sync_session_factory()`** 同步 Session 执行 `db.add` + `commit`（避免在 Celery 中混用 async ORM）。

### 2. `log_call`（直写 / In-process write）

- **同一 Service** 中的 `log_call`：在当前 **async 请求上下文** 的 `self.db` 上 **直接** 插入并 `flush`。
- **现状**：网关、对话引擎、用量记录器等 **热路径普遍调用 `log_call_async`**，**不是** `log_call`。保留 `log_call` 便于测试、脚本或未来「同步降级」等场景。

### 3. 主要调用方（便于排查）

- `app/ai/gateway.py`：非流式成功、流式 `on_complete`、生图等 → `log_call_async`。
- `app/ai/engine/conversation.py`：流式 `_stream_llm_chunks` **结束后** → `log_call_async`。
- `app/ai/usage_recorder.py`：失败记录、部分流式完成回调 → `log_call_async`。

---

## `billing_context` 是什么

- **含义**：一次调用当时的 **计费归属、访问渠道、智能体分发语义、企业侧发布规则快照** 等结构化字典。
- **构建**：典型在 `AgentChatService`（如 `_build_billing_context`）注入到 `ExecutionRequest.billing_context`，再经引擎 / Gateway 传到 `log_call_async` → Celery 任务。
- **落库**：`log_ai_call_task` 将字典拆到 `AICallLog` 各列（`billing_tenant_id`、`access_channel`、`agent_owner_type`、`tenant_publication_id`、各类 `*_snapshot` 等）。

**若任务函数签名缺少 `billing_context` 而调用方仍传入**：任务会整单失败，**库中无该行日志** —— 这通常是 **Worker 未重启、仍跑旧代码**，而非 broker 配置错误。

---

## 队列写入的优点与代价（排查时要讲清楚）

| 优点 | 说明 |
|------|------|
| 低延迟响应 | 主请求只做 `delay`，不把脱敏、截断、hash、INSERT 全压在 HTTP/SSE 路径上。 |
| 削峰 | 高峰时由 Worker 消费，减轻 Web 进程与 DB 瞬时压力。 |
| 可重试 | Task 可配置 `max_retries`，短时故障可自动重试。 |
| Worker 同步写库 | 与项目「Celery 用 sync_session」规范一致，避免 asyncio 与 ORM 混用问题。 |

| 代价 / 风险 | 说明 |
|-------------|------|
| **必须运行消费 `ai_gateway` 的 Worker** | 否则任务堆积或从未执行，**页面永远 0 条**。 |
| **API 与 Worker 代码必须同版本** | 任务参数增删（如 `billing_context`）后 **必须重启 Worker**。 |
| **流式对话** | 日志往往在生成器 **尾部** 入队；客户端提前断开可能导致 **未执行到尾部** 而缺日志（与是否队列无关，属流式生命周期问题）。 |

---

## 运维检查清单（中英）

1. **Worker**：`novusai celery worker`（或项目文档中的等价命令）是否在跑，且消费 **`ai_gateway`**。 / Ensure a Celery worker consumes the **`ai_gateway`** queue.
2. **部署**：发布含 `tasks/ai.py` 或 `call_log_service` 的变更后 **重启 Worker**。 / Restart workers after task signature or payload changes.
3. **日志**：搜 `tasks.ai`、`AI call log failed`、`Engine stream call log failed`、`AI call log queued`。 / Search backend logs for enqueue / failure messages.
4. **DB**：`task_logs` 表中 `tasks.ai.log_ai_call` 的失败原因与 traceback。 / Inspect `task_logs` for failed `log_ai_call` rows.

---

## 与「三层分发」的关系（简要）

- **管理端**：平台智能体对企业可用性（`owner_type`、`distribution_mode`、分配、`agent_access.admin_role_ids` 等）。
- **企业端**：是否向 **用户端** 发布及规则（`tenant_agent_publications`，与 `agent_access.tenant_role_ids` 等企业后台角色限制区分）。
- **统计**：管理端侧重 **按企业计费维度**；企业端侧重 **本企业 + 用户**；均以 **`AICallLog` + `billing_tenant_id` / 渠道等** 聚合，而非旧 `ai_usage_stats`。

详见智能体与权限相关规则与 `novusai-saas` 技能中的 AI 模块引用。

---

## 相关代码路径（速查）

| 用途 | 路径 |
|------|------|
| 异步队列任务 | `backend/app/tasks/ai.py` → `log_ai_call_task` |
| Service | `backend/app/services/ai/call_log_service.py` |
| 聚合 / 统计查询 | `backend/app/repositories/ai/call_log_repository.py` |
| 合并迁移（账本列、publication、agents 字段、删 usage 表） | `backend/migrations/versions/20260322_ai_billing_ledger_merge.py` |

---

## 给 Agent 的固定结论（Fixed conclusions）

1. **主链路下，调用日志是 Celery 异步写入 `ai_call_logs`，不是浏览器直连写库。** / Main path persists call logs via Celery into `ai_call_logs`.
2. **`log_call` 是进程内直写，存在但对话主路径默认不用。** / `log_call` is in-process; hot paths use `log_call_async`.
3. **「无日志 + 任务报参数错误」优先怀疑 Worker 旧代码，重启 Worker。** / Stale worker process is the first suspect for signature mismatches.
4. **统计与调用日志页应以 `AICallLog` 为准，并理解快照字段含义。** / Treat `AICallLog` as the source of truth for usage UIs.
