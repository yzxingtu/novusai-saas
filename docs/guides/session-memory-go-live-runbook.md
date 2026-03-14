# 会话记忆上线手册（P2）

## 1. 目标与范围

本手册适用于会话记忆首版上线（仅 AI 对话页生效），覆盖以下内容：

- 观测指标与日志检查
- 灰度发布步骤
- 回滚预案
- 故障排查
- 合规与审计检查清单

不适用范围：

- 插件调用链（当前默认禁用会话记忆）
- 跨会话长期记忆能力

## 2. 上线前检查（Pre-flight）

### 2.1 代码与迁移

- 确认迁移链包含：
  - `20260302_9f2d1e34c7a1_add_agent_memory_switch_and_override.py`
  - `20260302_seed_session_memory_cleanup_task.py`
- 确认模型注册：
  - `Agent.memory_enabled`
  - `AgentMemoryOverride`
- 确认 API 可用：
  - `GET/PUT /admin/ai/agents/{id}/memory`
  - `GET/PUT /tenant/ai/agents/{id}/memory`
  - `DELETE .../conversations/{id}/memory-state`

### 2.2 功能行为

- 仅 `memory_scene=ai_chat_page` 时允许读写会话记忆。
- `admin_chat`、`plugin` 场景必须禁用记忆。
- 新会话不继承旧会话记忆（`conversation_id` 维度隔离）。
- TTL 为 24h（`SESSION_MEMORY_TTL_SECONDS = 86400`）。

### 2.3 测试基线

- 后端测试至少包含：
  - `test_agent_chat_service_memory_scene.py`
  - `test_agent_memory_switch_service.py`
  - `test_session_memory_service.py`
  - `test_agent_service.py`
  - `test_conversation_service.py`
- 前端至少完成：
  - `tsc` 类型检查
  - 记忆开关页面联调（admin/tenant）
  - 对话页“清空本会话记忆”联调

## 3. 观测与告警

### 3.1 关键日志事件

重点检索以下日志关键字（`ai.session_memory_service` / `ai.agent_chat_service`）：

- `Session memory hit`
- `Session memory miss`
- `Session memory CAS conflict`
- `Session memory idempotent hit`
- `Session memory write degraded`
- `Session memory load degraded`
- `Session memory context injected`
- `Session memory cleared by conversation`

### 3.2 建议阈值

- 降级率（`degraded` / `hit+miss`）：
  - 正常：< 1%
  - 预警：>= 1%
  - 严重：>= 5%
- CAS 冲突率（`CAS conflict` / `updated`）：
  - 正常：< 3%
  - 预警：>= 3%
  - 严重：>= 10%
- 清空失败率（接口错误）：
  - 预警：>= 1%

### 3.3 运行态检查

- Redis 中 `mem:sess:*` key 总量增速是否与对话活跃度匹配。
- 定时任务 `clean_expired_session_memories` 是否按计划执行。
- 无 TTL key 清理量是否异常升高（通常应接近 0）。

## 4. 灰度发布方案

### 4.1 分阶段

1. 阶段 A：仅管理端测试企业（内部）
2. 阶段 B：10% 企业（低风险企业）
3. 阶段 C：50% 企业
4. 阶段 D：100% 全量

### 4.2 每阶段验收

- 对话链路无主流程失败（记忆异常必须降级）。
- 内存 key 增长与清理趋势稳定。
- 用户侧无“对话错乱/串记忆”反馈。
- 清空会话记忆接口成功率稳定。

## 5. 回滚预案

### 5.1 软回滚（优先）

1. 平台配置 `platform_default_memory_enabled=false`
2. 保持代码不回滚，记忆逻辑自动短路失效
3. 继续观察 30 分钟确认故障收敛

### 5.2 硬回滚（必要时）

1. 回滚应用版本到上一稳定版本
2. 暂停 `clean_expired_session_memories` 任务（如存在副作用）
3. 保留数据，不主动删除 `mem:sess:*`（用于问题复盘）

## 6. 故障排查手册

### 6.1 现象：对话接口变慢

- 检查 Redis 延迟与连接池状态。
- 检索 `Session memory load degraded` 是否突增。
- 临时方案：关闭平台默认记忆开关止损。

### 6.2 现象：会话记忆不生效

- 校验入口 `memory_scene` 是否为 `ai_chat_page`。
- 校验三层开关最终值：
  - 平台默认
  - 管理端 Agent 开关
  - 企业 disabled 覆盖
- 检查是否误用新会话（`conversation_id` 变化）。

### 6.3 现象：清空记忆后仍有旧偏好

- 确认清空的是当前会话 ID。
- 检查是否切换到其他历史会话。
- 检查 `clear_conversation_memory` 返回 `deleted_count`。

## 7. 合规与审计检查

### 7.1 数据最小化

- 仅存储会话增量（偏好、约束、任务状态、事实）。
- 不存储无关敏感字段。

### 7.2 数据保留

- TTL 强制 24h。
- 定时任务兜底清理无 TTL 残留 key。

### 7.3 可追溯性

- 关键操作有日志：
  - 读写命中/未命中
  - CAS 冲突
  - 清空行为
  - 降级路径

### 7.4 权限边界

- 清空接口必须校验会话归属（企业、agent、user）。
- 管理端与企业端开关接口权限分离。

## 8. 上线后 24h 复盘项

- 降级率、冲突率、失败率趋势
- 典型错误样本与处理时长
- 是否需要调优：
  - 记忆提取规则
  - 日志采样策略
  - TTL 或清理任务频率
