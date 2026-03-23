# AI-2 Handoff

## 0. 冻结信息

- `AI 编号`：AI-2
- `负责人`：Codex
- `工作副本路径`：`E:/git_clone/novusai-saas-yudi`
- `分支名`：`main`
- `最后提交 SHA`：`c6e2d7710516bc918abd3fdec5aa4671b6ba4253`
- `冻结时间`：`2026-03-23 18:45:02 +08:00`

## 1. 文件清单

| 文件路径 | 类型 | 用途 | 是否最终版 |
|---|---|---|---|
| `backend/plugins/workflow-orchestration/backend/runtime/{constants.py,executor.py,graph.py,model_access.py,serializer.py,storage_access.py}` | `new/update` | 运行时常量、模型绑定、快照提取、执行器、序列化、插件 namespaced storage | `yes` |
| `backend/plugins/workflow-orchestration/backend/services/{tenant_workflow_service.py,run_service.py,run_query_service.py,recovery_service.py,artifact_service.py}` | `new/update` | 企业工作流副本、Run 启动、Run/Artifact 查询、恢复与清理任务 | `yes` |
| `backend/plugins/workflow-orchestration/backend/api/{admin_runtime.py,tenant_home.py,tenant_workflows.py,runs.py,artifacts.py}` | `new/update` | Admin runtime API、Tenant 首页/API、Run/API、Artifact/API | `yes` |
| `backend/plugins/workflow-orchestration/backend/tasks/{run_timeout_sweeper.py,run_retry_dispatcher.py,artifact_retention.py}` | `new/update` | 超时扫描、自动重试派发、Artifact 保留清理 | `yes` |
| `backend/plugins/workflow-orchestration/backend/tests/runtime/{conftest.py,test_graph.py,test_model_access_and_serializer.py,test_recovery_and_retention_correctness.py,test_state_machine.py,test_storage_and_service_contracts.py}` | `new/update` | 运行时辅助、状态机、服务契约、序列化与 correctness 回归测试 | `yes` |

## 2. 运行时对象真相

- `run` 主字段与状态：
  - 真相列以 `WorkflowRun` 为准：`tenant_id`、`workflow_id`、`workflow_version_id`、`release_id`、`code`、`status`、`entrypoint`、`initiated_by`、`initiated_from`、`started_by_type`、`mode`、`current_node_key`、`trace_id`、`idempotency_key`、`retry_count`、`input_payload_json`、`output_payload_json`、`cost_summary_json`、`control_envelope_json`、`budget_snapshot_json`、`risk_snapshot_json`、`metrics_json`、`error_summary`、`started_at`、`ended_at`、`last_heartbeat_at`。
  - 运行时固定把 `workflow_version_id` 锁定到 `TenantWorkflowVersion.id`；执行快照优先取 `TenantWorkflowVersion.snapshot_json`，仅在缺版本时回退 `TenantWorkflow.workflow_json`。
  - `replay_run` 当前正式语义：优先复用原 run 的 `workflow_version_id`；若版本记录缺失但原 `control_envelope_json.workflow_snapshot` 仍在，则继续以 `原 workflow_version_id + 原快照` 重放；若原版本缺失且原快照也缺失，则直接报冲突，禁止 silently rerun latest。
  - API 继续返回兼容 alias：`tenant_workflow_id`、`trigger_source`、`started_by_id`、`input_payload`、`output_payload`、`final_output`、`cost_summary`。
  - 当前实现会识别/返回这些状态：`pending`、`queued`、`validating`、`planning`、`running`、`waiting_human`、`waiting_approval`、`waiting_input`、`paused`、`recovering`、`compensating`、`succeeded`、`completed`、`partially_completed`、`failed`、`cancelled`。前端应优先读 `status_bucket` 和 `available_actions`。

- `node_run` 主字段与状态：
  - 真相列以 `WorkflowNodeRun` 为准：`run_id`、`tenant_id`、`parent_node_run_id`、`node_key`、`node_type`、`status`、`attempt_no`、`executor_type`、`executor_ref`、`trace_id`、`input_envelope_json`、`output_envelope_json`、`cost_json`、`metrics_json`、`error_summary`、`duration_ms`、`started_at`、`ended_at`。
  - API 兼容返回 `workflow_run_id`、`input_payload`、`output_payload`、`error_detail`。
  - 当前使用的节点状态：`pending`、`ready`、`running`、`waiting_human`、`waiting_approval`、`waiting_input`、`retry_scheduled`、`succeeded`、`failed_retryable`、`failed_terminal`、`skipped`、`compensated`、`cancelled`。
  - `retry_scheduled` 当前正式语义：属于自动重试调度状态；`dispatch_retryable_runs()` 会扫描 `Run.status in {failed, partially_completed, recovering}` 且节点存在 `retry_scheduled/failed_retryable` 的运行，并复用 `retry_run()` 统一转回 `ready`，不再出现 dispatcher 命中但 retry 逻辑拒绝处理的死角。

- `checkpoint` 主字段：
  - 真相列以 `WorkflowCheckpoint` 为准：`run_id`、`node_run_id`、`tenant_id`、`checkpoint_type`、`resume_token`、`state_hash`、`snapshot_json`、`created_by`、`expires_at`、`restored_at`。
  - 运行时会在 bootstrapping 时写入 `run_start_checkpoint`，并自动计算 `state_hash`。

- `artifact` 主字段与类型：
  - 真相列以 `WorkflowArtifact` 为准：`tenant_id`、`run_id`、`node_run_id`、`workflow_id`、`workflow_version_id`、`code`、`name`、`artifact_type`、`status`、`schema_ref`、`mime_type`、`storage_uri`、`storage_path`、`summary`、`content_json`、`content_text`、`visibility_scope`、`size_bytes`、`content_hash`、`feedback_summary`、`download_filename`、`retention_policy_json`、`metadata_json`、`ready_at`、`expires_at`。
  - API 兼容返回 `title`、`visibility`、`hash`、`workflow_run_id`、`workflow_node_run_id`、`preview_text`、`can_feedback`、`can_download`。
  - 当前使用/兼容的 Artifact 状态：`draft`、`ready`、`adopted`、`rejected`、`archived`、`expired`、`failed`。
  - `artifact_retention` 当前正式语义：每条 Artifact 单独解析真实 tenant context；优先取 `artifact.tenant_id`，缺失时回查 `run.tenant_id`，再按该上下文获取 namespaced storage 执行删除，禁止继续用单一 storage proxy 横扫所有租户。

- `event` 主字段与类型：
  - 真相列以 `WorkflowEvent` 为准：`run_id`、`node_run_id`、`tenant_id`、`event_type`、`event_level`、`event_code`、`status_from`、`status_to`、`message`、`trace_id`、`payload_json`、`occurred_at`。
  - 当前实现会产出：`run_created`、`run_status_changed`、`recovery_requested`、`recovery_completed`、`run_timed_out`、`artifact_feedback_submitted`、`artifact_retention_cleaned`。

## 3. API 摘要

- `Admin API`：
  - `GET runs` → `api.admin_runtime.list_runs`
  - `GET runs/{run_id}` → `api.admin_runtime.get_run_detail`
  - `POST runs/{run_id}/replay` → `api.admin_runtime.replay_run`
  - `POST runs/{run_id}/recover` → `api.admin_runtime.recover_run`
  - `POST runs/{run_id}/terminate` → `api.admin_runtime.terminate_run`

- `Tenant API`：
  - `GET home` → `api.tenant_home.get_home`
  - `GET builder-capabilities` → `api.tenant_home.get_builder_capabilities`
  - `GET workflows` → `api.tenant_workflows.list_workflows`
  - `POST workflows` → `api.tenant_workflows.create_workflow`
  - `POST workflows/copy-from-template` → `api.tenant_workflows.copy_from_template`
  - `GET workflows/{workflow_id}` → `api.tenant_workflows.get_workflow_detail`
  - `PUT workflows/{workflow_id}` → `api.tenant_workflows.update_workflow`
  - `GET workflows/{workflow_id}/versions` → `api.tenant_workflows.list_workflow_versions`
  - `POST workflows/{workflow_id}/publish` → `api.tenant_workflows.publish_workflow`
  - `POST workflows/{workflow_id}/run` → `api.runs.create_run`
  - `GET runs` → `api.runs.tenant_list_runs`
  - `GET runs/{run_id}` → `api.runs.tenant_get_run_detail`
  - `POST runs/{run_id}/pause` → `api.runs.tenant_pause_run`
  - `POST runs/{run_id}/resume` → `api.runs.tenant_resume_run`
  - `POST runs/{run_id}/retry` → `api.runs.tenant_retry_run`
  - `POST runs/{run_id}/terminate` → `api.runs.tenant_terminate_run`
  - `GET artifacts` → `api.artifacts.list_artifacts`
  - `GET artifacts/{artifact_id}` → `api.artifacts.get_artifact_detail`
  - `POST artifacts/{artifact_id}/feedback` → `api.artifacts.submit_feedback`
  - `GET artifacts/{artifact_id}/download` → `api.artifacts.download_artifact`

- `需要 integrator 回填到 plugin.yaml 的 API 路由增量`：
  - 当前 `plugin.yaml` 未包含 AI-2 的 admin runtime routes、tenant workflow/run/artifact routes，也未包含 AI-2 任务定义。
  - 管理端建议新增：
    - `GET runs` → `runtime_ops:list`
    - `GET runs/{run_id}` → `runtime_ops:view`
    - `POST runs/{run_id}/replay` → `runtime_ops:replay`
    - `POST runs/{run_id}/recover` → `runtime_ops:recover`
    - `POST runs/{run_id}/terminate` → `runtime_ops:terminate`
  - 企业端建议新增：
    - `GET home` → `workflow_center:view`
    - `GET builder-capabilities` → `workflow_center:view`
    - `GET workflows` → `workflow_center:list`
    - `POST workflows` → `workflow_builder:create`
    - `POST workflows/copy-from-template` → `workflow_builder:copy`
    - `GET workflows/{workflow_id}` → `workflow_center:view`
    - `PUT workflows/{workflow_id}` → `workflow_builder:edit`
    - `GET workflows/{workflow_id}/versions` → `workflow_center:view`
    - `POST workflows/{workflow_id}/publish` → `workflow_builder:publish`
    - `POST workflows/{workflow_id}/run` → `workflow_run:execute`
    - `GET runs` → `workflow_run:list`
    - `GET runs/{run_id}` → `workflow_run:view`
    - `POST runs/{run_id}/pause` → `workflow_run:pause`
    - `POST runs/{run_id}/resume` → `workflow_run:resume`
    - `POST runs/{run_id}/retry` → `workflow_run:retry`
    - `POST runs/{run_id}/terminate` → `workflow_run:terminate`
    - `GET artifacts` → `artifact_center:list`
    - `GET artifacts/{artifact_id}` → `artifact_center:view`
    - `POST artifacts/{artifact_id}/feedback` → `artifact_center:feedback`
    - `GET artifacts/{artifact_id}/download` → `artifact_center:export`

- `分页/过滤规则`：
  - 统一使用 JSON:API 风格：
    - 分页：`page[number]`、`page[size]`
    - 排序：`sort=-updated_at,name`
    - 过滤：`filter[field][eq|in|ilike|gte|lte]`

- `关键错误码或错误结构`：
  - 错误结构固定为：`{ "error": str, "code": int, "status_code": int }`
  - 关键码：`4001` 参数错误、`4030` 权限错误、`4040` 资源不存在、`4220` 状态冲突、`5001` 运行时依赖缺失

## 4. 后台任务

- `任务名`：`run_timeout_sweeper`
  - `调度方式`：周期任务，建议分钟级
  - `作用`：扫描 `running/recovering/compensating` 且心跳超时的 Run，写失败状态和超时事件

- `任务名`：`run_retry_dispatcher`
  - `调度方式`：周期任务，建议分钟级
  - `作用`：扫描 `status in {failed, partially_completed, recovering}` 且含 `failed_retryable/retry_scheduled` 节点的 Run，自动调度 `retry_run`

- `任务名`：`artifact_retention`
  - `调度方式`：周期任务，建议小时级或天级
  - `作用`：按每条 Artifact 真实租户上下文清理到期存储内容，更新为 `expired`，写审计事件

## 5. 前端依赖输出

- `给 AI-3 的字段`：
  - 首页：`summary`、`todos`、`alerts`、`builder_capabilities`、`highlighted_workflows`、`latest_runs`、`latest_artifacts`
  - 工作流列表/详情：`builder_mode`、`builder_surface`、`workflow_json`、`draft_snapshot`、`published_snapshot`、`versions`、`current_version`、`can_edit`、`can_publish`、`can_execute`
  - Run 详情：`status_bucket`、`available_actions`、`can_pause`、`can_resume`、`can_retry`、`can_terminate`、`node_counts`、`execution_graph`、`approvals`、`events`、`checkpoints`
  - Artifact：`name/title`、`preview_text`、`visibility_scope/visibility`、`content_hash/hash`、`download_filename`、`feedback`
  - 正式口径补充：前端如发起 replay，不需要自己猜版本；后端会以原 `workflow_version_id` 或原快照为真，不会静默切到最新发布版

- `给 AI-4 的字段`：
  - Admin runtime 监控可直接使用 `get_run_detail()` 返回的：
    - `run`
    - `node_runs`
    - `checkpoints`
    - `events`
    - `artifacts`
    - `execution_graph`
  - Tenant Run 详情已展平成单 payload，前端无需再拼嵌套结构

- `首页统计结构`：
  - `summary.pending_approvals`
  - `summary.failed_runs`
  - `summary.pending_artifacts`
  - `summary.active_workflows`
  - `summary.running_now`
  - `summary.quota_warnings`

- `共享枚举 / 常量建议`：
  - 前端统一以 `status_bucket` 渲染颜色和文案，不直接硬编码所有细分状态
  - Run action 统一读 `available_actions`
  - Artifact action 统一读 `can_feedback` / `can_download`

## 6. 已执行验证

- `运行时测试`：
  - `pytest backend/plugins/workflow-orchestration/backend/tests/runtime -q`
  - 结果：`23 passed`
  - 新增覆盖：
    - `replay_run` 版本锁定与原快照透传
    - `preferred workflow_version_id` 缺失时禁止 silently fallback latest
    - `retry_scheduled` 在 `recovering` 运行上的自动重试调度
    - `artifact_retention` 多租户上下文清理

- `接口冒烟`：
  - `python -c "... load_plugin_module('workflow-orchestration', <module>) ..."`
  - 结果：`runtime/*`、`services/*`、`api/*` 全部加载成功

- `其他`：
  - `python -c "import pathlib, py_compile; ... rglob('*.py') ..."` 覆盖 `backend/plugins/workflow-orchestration/backend/**/*.py`
  - 结果：通过
  - pytest 期间有 1 条 SQLAlchemy declarative reload warning，来源是测试里重复 unload/load 插件模块，不影响当前运行时逻辑

## 7. 已知问题与集成建议

- `已知问题`：
  - `plugin.yaml` 还没接入 AI-2 routes / tasks；当前代码可加载，但未经 manifest 注册前不能从宿主入口访问
  - 运行时真实执行目前是“创建 Run/NodeRun/Checkpoint/Event/Artifact 与恢复/清理/查询真相”，不包含真正节点执行器调用链
  - `create_workflow()` / `publish_workflow()` 依赖当前模型默认 code 生成器；如 AI-1 后续改了默认生成策略，AI-2 无需改接口，但需要联调唯一约束行为
  - 如果宿主返回的 Artifact 下载协议不是 `requestClient.download` 而是 signed URL，前端仍需按 AI-4 的下载 fallback 接口接入

- `需要 integrator 关注`：
  - 把第 3 节列出的 routes 和第 4 节列出的 tasks 增补到 `backend/plugins/workflow-orchestration/plugin.yaml`
  - 保持 permission 代码与 design doc 一致，不要把 AI-2 API 挂到宿主默认权限上
  - 前端联调时优先使用 AI-2 已暴露的稳定 alias，不要直接绑定数据库列名
  - 如果 AI-1/Integrator 后续补充 release/template publish 链，请确保 `TenantWorkflow.active_version_id/current_release_id` 在发布后保持一致
  - 若前端希望允许“重放未发布版本”，需在产品层决定是否放宽 replay_run 的发布校验；当前实现仍要求 workflow 处于 `published`
