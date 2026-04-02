# AI 会话记忆审计与整改方案

## 1. 目标与范围

本次审计聚焦以下问题：

1. AI 对话链路中的会话记忆是否符合项目规范
2. `mem:sess:*` Redis key 的 TTL、清理、删除归档生命周期是否闭环
3. `platform` 每天凌晨 `3:30` 清理无 TTL 会话记忆残留 key 的任务是否需要保留
4. 当前实现中是否存在会导致串记忆、残留记忆、越权读取记忆的设计缺口

审计范围覆盖：

- `.cursor/skills/novusai-saas/references/session-memory-spec.md`
- `backend/app/services/ai/agent_chat_service.py`
- `backend/app/services/ai/conversation_service.py`
- `backend/app/services/ai/session_memory_service.py`
- `backend/app/api/admin/ai_agent_chat.py`
- `backend/app/api/tenant/agent_chat.py`
- `backend/app/api/user/agent_chat.py`
- `backend/app/tasks/scheduled.py`
- `backend/app/tasks/scheduler.py`
- `backend/migrations/versions/20260302_seed_session_memory_cleanup_task.py`
- `frontend/apps/web-antd/src/api/shared/ai-chat.ts`
- `frontend/apps/web-antd/src/components/business/ai-chat-panel/use-ai-chat.ts`
- `frontend/apps/web-antd/src/components/business/ai-slide-panel/AIChatSlidePanel.vue`
- `frontend/apps/web-antd/src/views/user/ai-chat/index.vue`

## 2. 规范基线

根据当前项目规范，会话记忆必须满足以下原则：

1. 只属于有 `conversation_id` 的真实 AI Chat 场景
2. 只允许在 `ai_chat_page` 与 `admin_chat` 场景生效
3. 必须通过 `AgentChatService -> ConversationService -> SessionMemoryService` 统一处理
4. Redis key 必须走统一命名与 TTL 协议
5. 会话删除、归档、清空记忆时必须主动清理，不能只依赖 TTL
6. `stream_chat_ephemeral()` 等无对话持久化场景禁止写入会话记忆
7. 前端必须统一使用 `memory-state` 接口，不得自行保存另一套“记忆状态”

## 3. 审计结论摘要

### 3.1 总结论

当前实现 **主链路大体符合规范，但生命周期闭环尚未完全达标**。

可以明确确认的结论如下：

1. 主对话链路已经统一接入会话记忆，整体方向正确
2. `TTL=24h`、`CAS`、`event_id` 幂等、防 Redis 不可用降级等基础能力已经具备
3. 管理端、企业端、用户端都已经提供统一的 `memory-state` 读/清接口
4. 每天凌晨 `3:30` 清理无 TTL `mem:sess:*` 残留 key 的平台任务已经存在，且确实由 `periodic_tasks` 表调度
5. 但“智能体删除导致会话级联软删”这条链路没有同步清理会话记忆，仍存在依赖 TTL 自然过期的残留窗口
6. 此外还存在一个更严重的身份建模问题：`AgentConversation` 仅记录 `user_id`，未区分 `tenant_admin` 与 `tenant_user`，在同企业下存在跨角色 ID 冲突导致对话与记忆误访问的风险

### 3.2 对问题本身的最终判断

对于“是否需要 `platform` 每天凌晨 `3:30` 清理无 TTL 的会话记忆 Redis 残留 key”这个问题，答案是：

- **需要保留**
- **但它只能是兜底，不是主清理机制**
- **当前项目已经实现了这项兜底任务，不应该重复新增第二个同类任务**

## 4. 已符合规范的部分

### 4.1 会话记忆只在允许场景启用

`AgentChatService._resolve_memory_context()` 运行时只允许以下场景开启记忆：

- `MemorySceneEnum.AI_CHAT_PAGE`
- `MemorySceneEnum.ADMIN_CHAT`

其他场景会被归一化为 `memory_enabled = False`。

同时，`stream_chat_ephemeral()` 明确写死：

- `memory_scene="ephemeral"`
- `memory_enabled=False`

这部分符合规范。

### 4.2 记忆开关遵守三层合并

`AgentChatService._resolve_effective_memory_enabled()` 没有在入口自行猜测开关，而是统一调用：

- 管理端：`AdminAgentService.get_memory_config()`
- 企业端：`AgentService.get_memory_config()`

这部分符合规范中“三层开关统一解析”的要求。

### 4.3 Redis key、TTL、CAS 与幂等实现到位

当前 Redis key 协议为：

```text
mem:sess:{tenant_id}:{channel}:{source}:{agent_id}:{user_id}:{conversation_id}
```

当前实现具备：

- TTL：`86400` 秒
- `WATCH/MULTI` 的 CAS 更新
- `last_event_id` 幂等去重
- Redis 不可用时降级为空状态，不阻塞主链路

这部分实现质量是合格的。

### 4.4 单会话删除、归档、清空记忆链路是闭环的

`ConversationService` 已覆盖以下清理点：

- `archive_conversation()`
- `batch_archive()`
- `_after_delete()`
- `get_conversation_memory_state()`
- `clear_conversation_memory_state()`

也就是说，**用户/管理员主动操作某个 conversation 时**，记忆生命周期是闭环的。

### 4.5 前端没有自建第二套记忆存储

前端统一通过共享 API 和 `useAIChat()` 读写记忆：

- `getChatConversationMemoryApi()`
- `clearChatConversationMemoryApi()`
- `fetchConversationMemory()`
- `clearConversationMemory()`
- `memoryState`
- `lastMemoryUpdated`

UI 层展示也统一复用了这套能力。

这里需要特别说明：

- 历史上前端曾用 `sessionStorage` 记录会话级自动确认偏好，但它从来不是授权真相
- 它不是会话记忆本体
- 真正的会话记忆仍然在 Redis + `memory-state` API

因此该部分不构成规范违规。

## 5. 发现的问题与风险分级

## 5.1 P0 严重问题：会话所有者身份建模不完整，存在跨角色误访问对话与记忆的风险

### 现状

`AgentConversation` 只记录了：

- `tenant_id`
- `agent_id`
- `user_id`

但没有记录：

- `user_role`
- `user_type`
- `owner_type`

同时：

- `TenantAdmin` 和 `TenantUser` 是两张独立表
- 它们各自独立自增主键
- 因此在同一企业内，`tenant_admin.id == tenant_user.id` 完全可能发生

而当前企业端与用户端的对话访问控制都只按 `user_id` 比较：

- 企业端对话列表强制过滤 `user_id = tenant_admin.id`
- 用户端对话列表强制过滤 `user_id = tenant_user.id`
- `ConversationService.get_accessible_conversation()` 也只判断 `conversation.user_id != user_id`

### 风险

这意味着：

1. 如果同一企业中某个 `TenantAdmin.id` 与某个 `TenantUser.id` 数值相同
2. 则管理员端和用户端会把对方创建的 conversation 误判为“自己的会话”
3. 进而可能访问：
   - 对话详情
   - 删除对话
   - 更新标题
   - 读取 `memory-state`
   - 清空 `memory-state`

这不仅是对话权限问题，也直接是会话记忆隔离问题。

### 判断

这是本次审计中最严重的设计缺口，优先级高于“是否保留 3:30 兜底任务”。

### 结论

**必须修复。**

---

## 5.2 P1 高优先级问题：智能体删除时级联软删对话，但不会即时清理会话记忆

### 现状

当删除 Agent 时，`AgentService._before_delete()` 会调用：

- `repo.cascade_soft_delete_conversations(id, delete_level)`

该逻辑在 Repository 层直接对 `AgentConversation` 做批量 `UPDATE`，并没有经过 `ConversationService`，也没有同步调用：

- `SessionMemoryService.clear_conversation_memory()`

### 风险

这会产生以下问题：

1. 智能体删除后，Conversation 记录已经被软删
2. 但对应 `mem:sess:*` key 仍然存在
3. 如果 key 自身 TTL 正常，则不会被凌晨 `3:30` 的“无 TTL 清理任务”处理
4. 它只能等 24h TTL 自然过期

这与规范中的“删除不能只靠 TTL”相冲突。

### 结论

**必须修复。**

---

## 5.3 P1 高优先级问题：凌晨 3:30 的任务只能清理“无 TTL key”，无法清理“有 TTL 但已失效业务语义”的残留 key

### 现状

`clean_expired_session_memories()` 的逻辑是：

1. `SCAN mem:sess:*`
2. 读取每个 key 的 TTL
3. 只删除 `ttl == -1` 的 key

因此它的语义是：

- 清理 TTL 丢失的异常 key
- 清理不该长期存在但没有过期时间的残留 key

### 风险

对于如下情况它无能为力：

- key 仍有 TTL
- 但 conversation 已被级联软删
- 或业务语义已经结束

所以这个任务不能替代生命周期清理，只能作为“Redis TTL 失守后的保险丝”。

### 结论

**任务必须保留，但绝不能作为主清理逻辑。**

---

## 5.4 P2 中优先级问题：`event_id` 设计不够稳健，理论上存在误判幂等导致记忆增量丢失的可能

### 现状

当前记忆写入使用的 `event_id` 形如：

```text
{conversation.id}:{history_count}:{int(time.time())}
```

这个值并不是严格的“请求唯一 ID”，而是：

- conversation_id
- 当时的 history_count
- 秒级时间戳

### 风险

如果同一会话在同一秒内出现两个并发请求，且它们读取到的 `history_count` 相同，则可能生成相同 `event_id`。

在这种情况下，第二次写入可能被 `last_event_id` 误判为幂等重试，导致本应写入的记忆增量被跳过。

### 结论

这是低频但真实存在的设计风险，建议修复。

---

## 5.5 P2 中优先级问题：会话记忆清理任务的 `periodic_tasks.scope` 值不符合当前资源作用域规范

### 现状

迁移 `20260302_seed_session_memory_cleanup_task.py` 插入的记录为：

- `scope = 'platform'`

但当前 `PeriodicTask.scope` 的规范语义来自 `ResourceScopeEnum`，合法值不包含 `platform`，而应使用：

- `admin_only`
- `global_shared`
- `all_tenants`
- `admin_and_selected_tenants`
- `selected_tenants`

并且项目在更早的 `20260224` 迁移里还专门执行过：

```sql
UPDATE periodic_tasks SET scope = 'admin_only' WHERE scope = 'platform'
```

说明 `'platform'` 已经被视为历史旧值。

### 风险

1. Beat 调度本身不受影响，因为调度器只依赖 `is_active/is_deleted`
2. 但该记录在后台管理、过滤、后续编辑、规范一致性上属于脏数据
3. 后续如果有严格按 `ResourceScopeEnum` 处理的逻辑，可能造成展示或更新异常

### 结论

建议一并修正，但优先级低于权限与生命周期问题。

---

## 5.6 P2 中优先级问题：测试覆盖不完整

当前已有测试覆盖：

- `SessionMemoryService` 的 upsert / clear
- `ConversationService` 的 memory-state 访问控制与删除清理
- `AgentChatService` 的场景透传与记忆持久化调用

但未看到以下测试：

1. `clean_expired_session_memories()` 定时任务本身的测试
2. 智能体删除导致 conversation 级联软删时，是否会同步清理记忆
3. `tenant_admin` 与 `tenant_user` 同 ID 冲突下的对话/记忆隔离测试
4. `event_id` 并发碰撞下的幂等行为测试

### 结论

如果不补这些测试，后续修复很容易回归。

## 6. 对“3:30 兜底清理任务”的明确结论

## 6.1 是否需要保留

**需要。**

理由：

1. Redis TTL 可能因历史写法、人工操作、迁移脚本、调试命令、故障恢复而丢失
2. 当前代码明确把它定位为“兜底清理无 TTL 或异常残留 key”
3. 文档运行手册也要求持续观察“无 TTL key 清理量是否异常升高”

## 6.2 是否需要重复新增

**不需要。**

原因：

1. 任务函数已经存在
2. 数据库调度种子已经存在
3. Cron 已经是 `30 3 * * *`
4. Beat 已经从 `periodic_tasks` 表加载

因此当前工作不是“新增任务”，而是：

- 验证生产环境是否已执行该迁移
- 确认任务处于启用状态
- 修正其 `scope`
- 保留并监控其执行结果

## 6.3 它是否足够

**不够。**

它只能处理：

- 无 TTL key

它不能处理：

- 有 TTL 但 conversation 已业务失效的残留 key
- 生命周期漏清理
- 身份隔离建模问题

## 7. 目标整改方案

整改建议分为四层。

### 7.1 第一层：修复身份隔离模型

### 目标

从根上消除 `tenant_admin` / `tenant_user` 共用 `user_id` 带来的歧义。

### 方案

为 `AgentConversation` 增加会话所有者类型字段，例如：

- `owner_type`
  - `tenant_admin`
  - `tenant_user`
  - `platform_admin`

或者：

- `user_role`

推荐字段名：

```text
owner_type
```

理由：

- 更接近“会话归属主体”的业务语义
- 不与 RBAC `role_id` 混淆

### 需要修改的点

1. `AgentConversation` 模型新增字段
2. 创建对话时写入：
   - 管理端：`platform_admin`
   - 企业端：`tenant_admin`
   - 用户端：`tenant_user`
3. `ConversationService.get_accessible_conversation()` 增加 `owner_type` 校验
4. 企业端/用户端 `/conversations` 列表强制过滤时同时带上 `owner_type`
5. 路由服务 `AgentRouterService._get_accessible_conversation()` 同步改造
6. `memory-state` 的读/清权限沿用新的会话归属校验

### 数据迁移建议

历史数据需要一次性补齐 `owner_type`。

推荐策略：

1. 先根据来源端或已知业务路径回填高置信度数据
2. 对无法确定来源的历史 conversation，临时标记为 `unknown`
3. 对 `unknown` 会话：
   - 禁止跨端读取
   - 仅允许平台管理员审计
   - 后续按日志或归属规则逐步修复

如果现网 user/tenant AI 功能上线时间较短，也可以接受“一次性用来源路由/历史请求日志批量回填”的方式。

---

### 7.2 第二层：补齐生命周期即时清理

### 目标

让所有“conversation 失效”的路径都即时清理会话记忆，而不是等待 TTL。

### 方案

新增统一的批量清理能力，例如：

- `SessionMemoryService.clear_conversation_memories(conversation_ids: list[int])`

或在 `ConversationService` 中封装：

- `clear_memory_for_conversation_ids(conversation_ids: list[int])`

### 需要接入的链路

1. `AgentService._before_delete()` 删除智能体时
2. 未来任何对 `AgentConversation` 做批量软删/级联软删的路径
3. 如果后续出现“租户删除”“批量清理对话”等能力，也统一复用该方法

### 推荐实现方式

#### 同步路径

适用于会话数量较小：

1. 先查询受影响的 `conversation_id` 列表
2. 执行 conversation 软删
3. best-effort 批量清理 Redis key
4. 清理失败只记日志，不阻断主删除事务

#### 异步路径

适用于单个 Agent 下会话量很大：

1. 先同步完成 DB 软删
2. 把 `tenant_id + conversation_ids` 投递到 `scheduled` 或 `default` 队列
3. 异步执行 Redis 清理

### 推荐阈值

- `conversation_ids <= 200`：同步清理
- `conversation_ids > 200`：异步清理

这样可以在“删除即时性”和“请求耗时”之间取得平衡。

---

### 7.3 第三层：保留并规范化 3:30 平台兜底任务

### 目标

继续保留“无 TTL key 清理”这道保险，同时修正其规范漂移。

### 必做项

1. 保留 `clean_expired_session_memories`
2. 保持 Cron 为 `30 3 * * *`
3. 不新增重复任务
4. 修正任务记录的 `scope`：
   - 从 `platform`
   - 改为 `admin_only`

### 建议新增一条修复迁移

```sql
UPDATE periodic_tasks
SET scope = 'admin_only', updated_at = NOW()
WHERE task_path = 'app.tasks.scheduled.clean_expired_session_memories'
  AND scope = 'platform';
```

### 可选增强

增加一个“一次性历史修复任务”，只跑一次，用于清理当前已经残留的有 TTL 但已无效的 key。

建议名称：

- `reconcile_session_memory_orphans`

建议用途：

1. 扫描 `mem:sess:*`
2. 解析出 `tenant_id` 与 `conversation_id`
3. 检查 conversation 是否存在、是否已删除
4. 删除已无效的 key

注意：

- 这是**一次性存量修复**，不建议作为日常高频任务
- 日常仍应以“生命周期即时清理 + TTL + 无 TTL 兜底”三层为主

---

### 7.4 第四层：修复 `event_id` 设计

### 目标

避免不同请求在同一秒内被误判为同一个记忆事件。

### 方案

将 `event_id` 改为真正的请求级唯一值。

推荐方案：

1. 在进入 `chat()` / `stream_chat()` 时生成一次 `memory_event_id`
2. 该值在整个请求生命周期内保持不变
3. 非流式和流式回调都使用这个值

推荐格式：

```text
memevt:{conversation_id}:{uuid4}
```

或者：

```text
memevt:{conversation_id}:{trace_id}
```

如果使用 `trace_id`，必须确认：

- 同一 HTTP 请求重试时 trace_id 是否保持一致
- 流式完成回调是否能稳定拿到同一 trace_id

更稳妥的做法是直接使用 `uuid4`，并通过闭包传入回调。

## 8. 测试方案

## 8.1 后端单元测试

必须新增以下测试：

1. `test_agent_delete_clears_session_memory_for_cascaded_conversations`
2. `test_clean_expired_session_memories_deletes_only_no_ttl_keys`
3. `test_clean_expired_session_memories_keeps_ttl_keys`
4. `test_tenant_admin_and_tenant_user_same_numeric_id_cannot_access_each_other_conversation`
5. `test_memory_state_access_respects_owner_type`
6. `test_event_id_unique_between_concurrent_turns`

## 8.2 集成测试

建议补两条集成用例：

1. 创建会话 -> 写入记忆 -> 删除会话 -> Redis 中对应 key 消失
2. 创建会话 -> 写入记忆 -> 删除智能体 -> 会话软删且 Redis key 被同步清除

## 8.3 迁移验证

对 `owner_type` 增量字段和 `periodic_tasks.scope` 修复迁移需要补数据迁移测试：

1. 升级后旧记录具备合法值
2. 回滚逻辑明确
3. 不会破坏 Beat 对现有任务的读取

## 9. 监控与运维方案

## 9.1 关键指标

建议补以下指标或至少结构化日志：

1. `session_memory_proactive_cleanup_keys_total`
   - 生命周期即时清理删掉的 key 数
2. `session_memory_fallback_no_ttl_cleanup_keys_total`
   - 凌晨 `3:30` 任务删掉的无 TTL key 数
3. `session_memory_load_degraded_total`
   - Redis 不可用导致读取降级次数
4. `session_memory_write_degraded_total`
   - Redis 不可用导致写入降级次数
5. `session_memory_orphan_cleanup_keys_total`
   - 若执行一次性历史修复任务，记录删掉的 orphan key 数

## 9.2 运行态判断标准

上线后应满足：

1. `fallback_no_ttl_cleanup_keys_total` 长期接近 `0`
2. `proactive_cleanup_keys_total` 与真实删除/归档行为一致
3. 删除智能体后，不再观察到对应会话的 `mem:sess:*` 长时间残留
4. 无管理员/用户串会话、串记忆投诉

## 9.3 运维核验 SQL

### 核验会话记忆清理任务是否存在

```sql
SELECT
  id,
  name,
  task_path,
  schedule_type,
  cron_expression,
  scope,
  is_active,
  is_locked,
  is_editable
FROM periodic_tasks
WHERE task_path = 'app.tasks.scheduled.clean_expired_session_memories';
```

预期：

- `schedule_type = 'cron'`
- `cron_expression = '30 3 * * *'`
- `is_active = true`
- `scope` 最终应为 `admin_only`

### 核验是否仍有无 TTL 会话记忆 key

由运维脚本或 Redis CLI 执行，统计：

- `mem:sess:*` 总量
- `ttl == -1` 数量

预期：

- 总量与活跃对话规模匹配
- `ttl == -1` 长期接近 `0`

## 10. 实施顺序

建议按以下顺序推进。

### 阶段 A：先修规范与运行治理

1. 确认生产环境已有 `clean_expired_session_memories` 调度任务
2. 若迁移已执行，核验是否启用
3. 新增迁移，把该任务 `scope` 修正为 `admin_only`
4. 增加运行日志/指标，确认当前无 TTL key 的真实数量

### 阶段 B：修复生命周期残留

1. 增加批量清理会话记忆能力
2. 在 Agent 删除级联软删 conversation 时同步调用
3. 补齐相关测试

### 阶段 C：修复身份建模

1. 为 `AgentConversation` 增加 `owner_type`
2. 修改创建、列表、详情、删除、memory-state、路由访问控制
3. 回填历史数据
4. 补齐 admin/user 冲突测试

### 阶段 D：补长期稳态优化

1. 将 `event_id` 改为请求级唯一值
2. 视需要执行一次性 orphan key 修复任务
3. 观察一周，确认 fallback 清理量趋近于 `0`

## 11. 最终建议

最终建议如下：

1. **保留** 当前每天凌晨 `3:30` 的 `clean_expired_session_memories` 平台兜底任务
2. **不要重复新增** 第二个同类任务，因为当前系统已经有这项调度
3. **立即修复** Agent 删除时 conversation 级联软删未同步清理记忆的问题
4. **优先修复** `AgentConversation` 缺失 `owner_type` 的身份隔离问题，这是本次审计最严重的缺陷
5. **补充修复** `event_id` 唯一性与测试覆盖
6. **补一条规范化迁移**，把该 periodic task 的 `scope='platform'` 改回 `admin_only`

## 12. 一句话结论

当前会话记忆体系已经具备主链路能力，`3:30` 平台兜底清理任务也已经存在且应该保留；但项目还不能判定为“完全符合规范”，因为仍有两项必须整改的问题：

1. `AgentConversation` 身份归属建模不完整，存在跨角色误访问对话与记忆的风险
2. 智能体删除导致的 conversation 级联软删没有同步清理记忆，仍在依赖 TTL 自然过期
