# 会话记忆审计补漏里程碑（补充版）

## 1. 背景

本补充里程碑用于修复“会话记忆 P0/P1/P2”深度审计中发现的关键缺口，避免“任务状态已完成但运行时行为不完整”的风险。

当前发现的关键问题：

1. 非流式 `chat` 路径会话记忆写入异常被吞，实际未写入（`history_count` 变量未定义）。
2. 三层开关（平台默认 + 管理端 Agent + 企业覆盖）未接入对话运行时启停判定。
3. 会话删除路径未做主动记忆清理，依赖 TTL 兜底，未满足删除即清理目标。
4. Alembic 存在双 head，迁移链尚未收敛。

---

## 2. 补充里程碑设计

### 里程碑 A（P0-Remediate）

- 里程碑名称：`会话记忆 P0 补漏修复（运行时一致性）`
- 目标：修复会话记忆运行时核心缺陷，确保“对话页记忆”在真实链路可用且可控。

#### A-T1 修复非流式 chat 记忆写入异常

- 优先级：高
- 范围：
  - 修复 `AgentChatService.chat` 中 `event_id` 构造使用未定义变量问题。
  - 保证 `event_id` 在单会话内可去重、跨轮次稳定递增或可追踪。
- 验收标准：
  - 非流式 chat 完成后，`SessionMemoryService.upsert_state` 确实被调用。
  - 无 `name 'history_count' is not defined` 异常。
  - 新增单测覆盖非流式写入路径。

#### A-T2 接入三层开关到运行时判定

- 优先级：高
- 范围：
  - 在 `AgentChatService` 运行时计算 `memory_enabled`，规则为：
    - `scene == ai_chat_page`
    - `platform_default_memory_enabled == true`
    - `agent.memory_enabled == true`
    - `tenant_disabled == false`
  - 管理端代测与插件场景继续默认禁用。
- 验收标准：
  - 管理端关闭 Agent 记忆后，对话页不再读写会话记忆。
  - 企业关闭覆盖后，对话页不再读写会话记忆。
  - 单测覆盖“场景 + 三层开关”组合判定。

#### A-T3 补齐删除会话主动清理

- 优先级：高
- 范围：
  - 在删除会话链路中增加 `clear_conversation_memory` 调用（tenant/admin 两端一致）。
  - 保持不存在会话、越权会话时的安全返回行为不变。
- 验收标准：
  - 删除会话后，`mem:sess:*:{conversation_id}` 不再存在。
  - 归档、批量归档、删除、手动清空四条路径行为一致。
  - 单测新增删除路径清理断言。

#### A-T4 回归测试补齐与稳定性复核

- 优先级：高
- 范围：
  - 扩展 `test_agent_chat_service_memory_scene.py` 覆盖运行时开关逻辑。
  - 扩展 `test_conversation_service.py` 覆盖删除清理。
  - 对 `test_session_memory_service.py` 增加 event_id 幂等边界用例。
- 验收标准：
  - 目标测试集全绿。
  - 修复用例可稳定复现旧缺陷并验证新逻辑。

---

### 里程碑 B（Migration-Governance）

- 里程碑名称：`会话记忆迁移链治理与发布保护`
- 目标：收敛迁移链并降低发布失败风险。

#### B-T1 合并迁移 head（单链收敛）

- 优先级：高
- 范围：
  - 为当前双 head 创建 merge migration。
  - 校验 `alembic history` 连续性与可升级性。
- 验收标准：
  - `HEAD_COUNT == 1`。
  - 新环境可从空库升级到最新。

#### B-T2 迁移链回归与回滚校验

- 优先级：中
- 范围：
  - 验证新增记忆相关迁移的 upgrade/downgrade。
  - 校验 `system_configs` 和 `periodic_tasks` 种子行为幂等。
- 验收标准：
  - 升级、回滚无断链。
  - 重复执行不产生重复脏数据。

---

### 里程碑 C（Ops-Ready+）

- 里程碑名称：`会话记忆观测与上线门禁增强`
- 目标：让运维与灰度发布具备可观测、可回滚、可核验能力。

#### C-T1 观测字段与日志事件规范化

- 优先级：中
- 范围：
  - 统一 `hit/miss/cas_conflict/idempotent/degraded/cleared` 日志字段。
  - 增加 tenant/agent/conversation 维度统一输出格式。
- 验收标准：
  - 关键事件可通过日志快速筛选定位。
  - runbook 示例与线上日志字段一致。

#### C-T2 runbook 与上线核对清单更新

- 优先级：中
- 范围：
  - 更新 `session-memory-go-live-runbook.md`，补充“已知缺陷修复验证段”。
  - 加入开关回滚、迁移单链校验、删除清理核验脚本。
- 验收标准：
  - 值班人员可按文档独立完成核验与回滚。
  - 与当前代码行为一致，无过时步骤。

---

## 3. 推荐认领顺序

1. A-T1
2. A-T2
3. A-T3
4. A-T4
5. B-T1
6. B-T2
7. C-T1
8. C-T2

---

## 4. 状态说明

本文件为会话记忆治理相关里程碑草案，可按 **trytrellis** 工作流拆解与跟踪（见 `/.trellis/workflow.md`）。
