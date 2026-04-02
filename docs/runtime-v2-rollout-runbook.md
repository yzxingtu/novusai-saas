# Runtime V2 灰度 Runbook

## 1. 目标与范围

- 目标：在不修改运行时核心引擎代码的前提下，验证 runtime v2 的实际运行稳定性、turn-level 诊断、partial/interrupted 持久化、576/577 回放与识别链路，并以可回滚方式逐步灰度到真实用户流量。
- 范围：
  - 后端：
    - `ConversationEngine` / `ConversationQueryEngine`
    - `ConversationService` / `AgentChatService`
    - `CallLogService` / `UsageRecorder`
  - 前端：
    - `ai-chat-panel` 的 turn-level diagnostics 展示
    - interrupted/partial / failed / protocol_fallback 语义一致性
  - CLI：
    - `novusai ai conversation show` 的 turn diagnostics + turn_record 可见性

## 2. 运行时开关

### 主开关

环境变量：`CLAUDE_CODE_STYLE_RUNTIME`

支持值：
- `legacy`
- `shadow`
- `pageaware_only`
- `active`

默认值：
- 未设置或非法值时回落到 `legacy`

### Shadow 护栏

可选环境变量：
- `CLAUDE_CODE_STYLE_RUNTIME_SHADOW_ENABLED`
- `CLAUDE_CODE_STYLE_RUNTIME_SHADOW_WHITELIST`
- `CLAUDE_CODE_STYLE_RUNTIME_SHADOW_SAMPLE_RATE`
- `CLAUDE_CODE_STYLE_RUNTIME_SHADOW_MAX_PER_MINUTE`

说明：
- `shadow` 目前是**非流式双跑**：
  - 用户拿到 legacy 结果
  - 后台再跑一次 runtime-v2 做对比
- `shadow` 不适合生产全量开启
- `SHADOW_MAX_PER_MINUTE` 当前是**进程内限流**，不是分布式硬限

## 3. 灰度分阶段

### 阶段 A：`legacy`
- 全量基线
- 持续 24h
- 目标：
  - 建立错误率、SSE 断流率、P95/P99、平均 tokens/cost 的基线
  - 建立 page-aware 操作错误类型基线

### 阶段 B：`shadow`
- 预发可全量
- 生产只允许：
  - 极低采样
  - 或白名单租户 / agent
- 推荐持续：
  - 预发 1 天
  - 生产 canary 1 天
- 目标：
  - 验证 runtime-v2 与 legacy 在工具选择、协议路径、终止原因上的差异分布
  - 不影响用户结果

### 阶段 C：`pageaware_only`
- 第一个真实用户灰度模式
- 仅让 page-aware 工具场景进入 runtime-v2
- 推荐流量：
  - 1% -> 5% -> 20%
- 每档至少观察 24h
- 目标：
  - 验证 page-aware 场景下 runtime-v2 真实稳定性
  - 验证空 assistant success 是否已经归零

### 阶段 D：`active`
- 全场景 runtime-v2
- 推荐流量：
  - 1% -> 5% -> 20% -> 50% -> 100%
- 每档至少观察 24h
- 目标：
  - 验证非 page-aware 场景也稳定
  - 观察 fallback 比例是否处于可接受范围

## 4. 发布前检查

- 后端强相关回归通过：
  - `backend/tests/services/test_conversation_service.py`
  - `backend/tests/services/test_runtime_v2_replay.py`
  - `backend/tests/services/test_stream_handler_real_stream.py`
  - `backend/tests/test_openai_adapter_responses.py`
  - `backend/tests/services/test_conversation_engine_prepare_execution.py`
  - `backend/tests/services/test_ai_gateway_platform_logging.py`
- 前端回归通过：
  - `frontend/apps/web-antd/src/components/business/ai-chat-panel/__tests__/ChatMessageItem.turn-diagnostics.test.ts`
  - `pnpm -C frontend run check:type`
  - `pnpm -C frontend run build`
- 已知 CI 风险：
  - `pnpm -C frontend run lint` 当前失败，但失败点集中在**与本次改造无关**的既有文件：
    - `frontend/apps/web-antd/src/views/admin/plugins/marketplace/index.vue`
    - `frontend/apps/web-antd/src/views/tenant/ai/action-logs/*`
    - `frontend/apps/web-antd/src/views/tenant/ai/agents/detail.vue`
    - `frontend/packages/effects/common-ui/package.json`
  - 因此 lint 失败不作为 runtime-v2 灰度阻塞项，但需要单独排期修复
- 抽检 3 类场景：
  - 正常完成（`turn_outcome=success`）
  - 用户手动停止/连接中断（`termination_reason=interrupted`）
  - runtime v2 fallback（`protocol_path` + `fallback_history`）

## 5. 线上观测项

- 对话详情接口（admin/tenant/user）：
  - `context_diagnostics.last_interrupted`
  - `context_diagnostics.selected_skill_names`
  - `last_run_summary.turn_outcome / termination_reason / protocol_path`
- 消息级 metadata：
  - `partial` / `interrupted` / `completion_reason`
  - `turn_record.fallback_history`
  - `turn_record.metadata.shadow_diff`
- 失败指标：
  - interrupted 后会话回放缺失率
  - diagnostics 字段空值率
  - UI 端“生成被中断/未完成”提示与真实状态不一致率
  - `Engine stream upstream failed` 比例
  - `Runtime-v2 non-stream fallback to legacy` 比例
  - `Runtime-v2 shadow compare skipped` 比例
  - page operation timeout / `error_type` 分布

### shadow 模式特别关注
- `has_diff=true` 比例
- `protocol_path` 差异
- `termination_reason` 差异
- shadow 成本增长

### pageaware_only 特别关注
- page-aware 触发比例
- 空 assistant success 是否为 0
- page operation timeout / invalid_input / user_cancelled / not_registered 分布

### active 特别关注
- non-stream fallback 到 legacy 比例
- `protocol_fallback` 比例
- `turn_outcome=failed/tool_round_failed` 分布

## 6. CLI 抽查流程

1. 获取目标会话 ID（抽样 recent 对话）。
 2. 执行：

```bash
novusai ai conversation show <conversation_id>
```

3. 检查输出中的：
- `Turn diagnostics: outcome=... termination_reason=... protocol_path=...`
- `Turn selected tools: ...`
- `Turn selected skills: ...`
- `Turn context sources: ...`
- 最近 assistant 消息的 `metadata.turn_record`
  - `fallback_history`
  - `shadow_diff`
  - `sync_rescue`
- `Recent call logs (#): ...`
  - 观察 `turn_outcome` / `termination_reason` / `protocol_path` 是否与最新 turn 保持一致，任何 drop-in 失败都会先写在这里
  - 注意 `selected_tool_names` / `selected_skill_names` / `fallback_history` / `sync_rescue`，这组字段经常成为 conversation 579 这类 shadow/v2 rollforward 问题的 first signal
- 为了拿到未经截断的 `metadata.turn_record` 与 call log `turn_diagnostics`，可加 `--full-content`（保留文本格式）或 `--json`（便于快速 copy/paste）
- 历史样本提醒：conversation 580 的最后两轮用户问“今天北京天气怎么样？”/“你不是有天气技能包吗？”在修复前曾触发 `tool_planner.family=none`、`allowed_tool_names=[]`，CLI 输出直接写出“还没有实时天气数据接口”，对应日志 `backend/logs/app.log` 行 8616/8634 也清晰记录了这次旧策略回退。灰度前可用它作为对照样本；修复后应再跑天气探针，确认新请求已经进入 `family=weather`，再放量
- 修复后真实样本：
- `conversation 584` 已可在 CLI 中看到 `get_current_weather` tool call，assistant metadata 内的 `tool_planner.family=weather` 也与日志 `backend/logs/app.log` 中 `conversation_id=584 family=weather` 保持一致，可作为 weather 工具链的 pending-consent 中间态样本
- `conversation 586` 在批准 `pending_consent` 后，已经真正执行了 `get_current_weather`，CLI 可看到工具失败结果与 assistant 的自然语言总结，证明 non-stream confirm 路径不再陷入“二次 ask 不执行”的旧行为；即便外部 geocoding 超时，这条样本也足以说明 consent 后续执行链路已经恢复
- `conversation 589` 是 `588` 同型混合请求（健康表述 + 天气问题 + page_context）的修复后正样本：CLI 第一跳已经直接发起 `get_current_weather`，不再被 `get_page_context` 抢走，说明显式 family 与最终暴露给模型的工具集合已经重新对齐
- pending consent 说明：conversation 584 的 `tool_calls` 里带 `pending_consent` 结构，后续 tool response 返回 `requires_confirmation=true`，这是呼叫天气工具后等待用户许可的正常中间态，不应被误判为 runtime-v2 失败；只要 CLI/log 仍打印 pending consent 与 tool response，说明调用已经达到了正确的路径，只是还差用户确认
- 历史缺口说明：conversation 584 曾经出现过“批准后又重复 ask 一次”的 non-stream consent continuation 现象；现在可以把它当作修复前对照样本。修复后请优先看 conversation 586，这条样本已经证明批准 consent 后会真正执行 `get_current_weather`，不再把重复 pending_consent 当成当前版本的既知缺口

## 7. 回滚条件与操作

- 任一条件触发立即暂停放量并回滚：
  - interrupted 场景历史回放错误率持续超过 1%
  - turn diagnostics 核心字段缺失率持续超过 5%
  - 多端（admin/tenant/user）出现不可恢复 UI 回归
  - `Engine stream upstream failed` 明显高于基线
  - page operation timeout 激增
  - 用户反馈中“工具卡住 / 空回复 / retry 激增”明显增加
  - shadow 成本异常上涨

- 回滚步骤：
1. 将 canary 实例环境变量改回：
   - `CLAUDE_CODE_STYLE_RUNTIME=legacy`
   - 或删除该 env var
2. 若当前在 `shadow`：
   - 同时设置 `CLAUDE_CODE_STYLE_RUNTIME_SHADOW_ENABLED=false`
3. 滚动重启 canary 实例
4. 将流量切回主实例组
5. 保留会话数据，不执行结构性清理
6. 导出异常样本：
   - 会话详情 API
   - CLI 输出
   - call log turn diagnostics
7. 验证：
   - runtime-v2 相关日志快速降为 0
   - 核心 SLI 恢复基线

## 8. 验收门槛

- 三端入口均能稳定展示 turn diagnostics（含 `selected_skill_names`）。
- interrupted/partial 持久化后，刷新页面仍可回放语义。
- 576/577 目标场景在前端与 CLI 均可识别到 `turn_record` 回放信息。
- `shadow` 不出现不可接受的 skipped/diff/cost 激增。
- `pageaware_only` 下空 assistant success 必须保持为 0。

## 9. 已知剩余风险

- `shadow` 采样/限流当前是进程内近似值，不是分布式全局硬限。
- 流式 runtime-v2 在“已产出有效 chunk 后再异常”的场景不会跨协议回退，这是为避免重复输出而保留的行为，需要重点观测。
- `turn_diagnostics` 更丰富后，`ai_call_logs.request_metadata` JSON 体积会增长，需要关注高并发下体积与查询成本。
- 这轮跑了大范围相关回归，但不是全仓所有测试；真正 100% 放量前，仍建议做一次准生产联调抽检。
- mixed capability（例如“先看页面，再查天气”）虽已支持同轮暴露多 family 工具，但在页面会话缺失时可能先触发 `pageop_* session_not_found`，并出现重复读取页面上下文的倾向；灰度时需重点盯 `selected_tool_names` 与 tool round 进展，避免出现长链路空转。

## 10. 2026-04-02 审计快照（发布前）

- runtime-v2 强相关回归（136 项）已通过：`test_agent_chat_page_context`、`test_conversation_engine_prepare_execution`、`test_runtime_v2_replay`、`test_stream_handler_real_stream`、`test_openai_adapter_responses`。
- 扩大后端相关回归（217 项）已通过，覆盖 memory / KB / health check / call log / scheduler 等与 runtime-v2 联动路径。
- CI 口径全量后端测试 `pytest tests/ -x --tb=short -q` 在当前仓库状态下会被既有用例阻断，首个阻断点是 `tests/api/test_public_config_group_wiring.py`（`settings.platform_domains_list` 只读属性被 monkeypatch 赋值）。
- 排除该阻断点继续全量后，仍有一组主要集中在插件、环境依赖与历史基线的失败（例如 Redis/Celery 依赖、插件历史快照路径、插件文案断言），不属于本轮 runtime-v2 主链改造引入。
- 结论：可以继续按 `legacy -> shadow -> pageaware_only -> active` 进行灰度；不建议在未单独清理上述既有失败前直接把“全仓全绿”作为 runtime-v2 上线前置条件。
