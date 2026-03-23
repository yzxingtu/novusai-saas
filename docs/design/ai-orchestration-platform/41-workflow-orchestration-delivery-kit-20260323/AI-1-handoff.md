# AI-1 Handoff

## 0. 冻结信息

- `AI 编号`：`AI-1`
- `负责人`：`Codex / GPT-5`
- `工作副本路径`：`E:/git_clone/novusai-saas-yudi`
- `分支名`：`main`
- `最后提交 SHA`：`c6e2d7710516bc918abd3fdec5aa4671b6ba4253`
- `冻结时间`：`2026-03-23 19:51 +08:00`
- `本轮性质`：`审计后的纠偏轮次，不新增业务能力，只修模型/迁移/交接真相`

## 1. 本轮整改实际修改文件

| 文件路径 | 类型 | 用途 | 是否最终版 |
|---|---|---|---|
| `backend/plugins/workflow-orchestration/backend/models/template.py` | `update` | 用命名 `UniqueConstraint` / `Index` 收口模板相关模型真相，对齐 001 migration | `yes` |
| `backend/plugins/workflow-orchestration/backend/models/release.py` | `update` | 用命名 `UniqueConstraint` / `Index` 收口发布、环境、触发器、模块配置模型真相，对齐 001 migration | `yes` |
| `backend/plugins/workflow-orchestration/backend/models/runtime.py` | `update` | 收缩 runtime-support 模型的单列 `index=True` / `unique=True`，改为与 001 migration 一致的命名复合索引和唯一约束 | `yes` |
| `backend/plugins/workflow-orchestration/backend/migrations/versions/001_initial.py` | `update` | 补齐 `BaseModel` 自带 `id` / `is_deleted` / `recycle_stage` 索引，消除模型与迁移 drift | `yes` |
| `docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/AI-1-handoff.md` | `update` | 回填本轮整改后的模型、迁移、验证和剩余未决点真相 | `yes` |

## 2. 模型与迁移真相

- `迁移链`：
  - `001_initial.py`：建表、命名唯一约束、查询索引、默认环境 seed、默认模块配置 seed
  - `002_fix_workflow_version_nullability.py`：保留在迁移链中，最终真相明确为：
    - `px_workflow_orchestration_triggers.workflow_version_id`：`nullable=True`
    - `px_workflow_orchestration_releases.workflow_version_id`：`nullable=False`
- `本轮已收口的 drift`：
  - 模型里的匿名 `unique=True` 已改为与迁移同名的 `UniqueConstraint`
  - 模型里原先多余的单列 `index=True` 已移除，改为与迁移一致的命名 `Index`
  - `001_initial.py` 已补齐 `BaseModel` 自动生成的基础索引：
    - `ix_{table}_id`
    - `ix_{table}_is_deleted`
    - `ix_{table}_recycle_stage`
  - 经过脚本比对，当前 `models` 与 `001_initial.py` 的 `index/unique` 集合已一致
- `新增表`：
  - `px_workflow_orchestration_templates`
  - `px_workflow_orchestration_template_versions`
  - `px_workflow_orchestration_template_nodes`
  - `px_workflow_orchestration_template_edges`
  - `px_workflow_orchestration_environments`
  - `px_workflow_orchestration_change_sets`
  - `px_workflow_orchestration_triggers`
  - `px_workflow_orchestration_releases`
  - `px_workflow_orchestration_module_configs`
  - `px_workflow_orchestration_tenant_workflows`
  - `px_workflow_orchestration_tenant_workflow_versions`
  - `px_workflow_orchestration_runs`
  - `px_workflow_orchestration_node_runs`
  - `px_workflow_orchestration_checkpoints`
  - `px_workflow_orchestration_events`
  - `px_workflow_orchestration_artifacts`
- `命名唯一约束真相`：
  - `uq_px_workflow_orchestration_templates_code`
  - `uq_px_workflow_orchestration_template_versions_template_version`
  - `uq_px_workflow_orchestration_template_nodes_template_node`
  - `uq_px_workflow_orchestration_template_edges_template_edge`
  - `uq_px_workflow_orchestration_environments_code`
  - `uq_px_workflow_orchestration_change_sets_code`
  - `uq_px_workflow_orchestration_releases_code`
  - `uq_px_workflow_orchestration_tenant_workflows_tenant_code`
  - `uq_px_wo_twf_versions_wf_ver`
  - `uq_px_workflow_orchestration_runs_code`
  - `uq_px_workflow_orchestration_node_runs_run_node_attempt`
  - `uq_px_workflow_orchestration_checkpoints_resume_token`
  - `uq_px_workflow_orchestration_artifacts_code`
- `查询索引真相`：
  - `ix_px_workflow_orchestration_templates_status`
  - `ix_px_workflow_orchestration_templates_category`
  - `ix_px_workflow_orchestration_templates_builder_surface`
  - `ix_px_workflow_orchestration_templates_release_scope`
  - `ix_px_workflow_orchestration_template_versions_template_id`
  - `ix_px_workflow_orchestration_template_versions_status`
  - `ix_px_workflow_orchestration_template_versions_snapshot_hash`
  - `ix_px_workflow_orchestration_template_versions_published_flags`
  - `ix_px_workflow_orchestration_template_nodes_template_type`
  - `ix_px_workflow_orchestration_template_edges_template_nodes`
  - `ix_px_workflow_orchestration_environments_scope_status`
  - `ix_px_workflow_orchestration_change_sets_workflow_status`
  - `ix_px_workflow_orchestration_triggers_workflow_status`
  - `ix_px_workflow_orchestration_triggers_type_owner`
  - `ix_px_workflow_orchestration_releases_workflow_status`
  - `ix_px_workflow_orchestration_releases_scope_channel`
  - `ix_px_workflow_orchestration_releases_published_at`
  - `uq_px_workflow_orchestration_module_configs_global`
  - `uq_px_workflow_orchestration_module_configs_tenant`
  - `ix_px_workflow_orchestration_tenant_workflows_status`
  - `ix_px_workflow_orchestration_tenant_workflows_builder`
  - `ix_px_workflow_orchestration_tenant_workflow_versions_status`
  - `ix_px_wo_twf_versions_snap_hash`
  - `ix_px_workflow_orchestration_runs_tenant_status`
  - `ix_px_workflow_orchestration_runs_workflow_version`
  - `ix_px_workflow_orchestration_runs_trace`
  - `ix_px_workflow_orchestration_node_runs_status`
  - `ix_px_workflow_orchestration_checkpoints_run_type`
  - `ix_px_workflow_orchestration_events_run_type`
  - `ix_px_workflow_orchestration_events_trace`
  - `ix_px_workflow_orchestration_artifacts_run_status`
  - `ix_px_workflow_orchestration_artifacts_type_visibility`
  - `ix_px_workflow_orchestration_artifacts_hash`
  - 以及每张插件表的基础索引：
    - `ix_{table}_id`
    - `ix_{table}_is_deleted`
    - `ix_{table}_recycle_stage`
- `版本快照表`：
  - `px_workflow_orchestration_template_versions`
  - `px_workflow_orchestration_tenant_workflow_versions`
- `版本快照真相规则`：
  - 发布、运行、回滚统一以 `*_versions.snapshot_json` 为准
  - `template_nodes` / `template_edges` 仅用于结构化查询与 UI 友好层，不是运行时最终真相
- `首版 migration seed`：
  - 环境：`draft_env`、`test_env`、`staging_env`、`prod_env`、`tenant_sandbox`、`tenant_pilot`、`tenant_prod`
  - 模块配置：`global/module_settings`、`tenant_default/module_settings`
- `未纳入当前迁移链的延期表`：
  - `px_workflow_orchestration_solution_bindings`
  - `px_workflow_orchestration_eval_links`
  - `px_workflow_orchestration_daily_metrics`

## 3. 零宿主约束核对

- `是否修改任何 backend/app/**（必须为否）`：`否`
- `是否修改主系统前端源码（必须为否）`：`否`
- `是否修改 runtime / tasks / tenant API 禁区文件（必须为否）`：`否`
- `数据边界真相`：
  - 所有业务数据只落 `px_workflow_orchestration_*`
  - 只使用插件内部表之间的 FK
  - 未新增到宿主 tenant/user/业务表的 FK
  - `tenant_id`、`created_by`、`updated_by`、`published_by`、`initiated_by` 仅以标量 ID 保存
  - 设计时设置仍落 `px_workflow_orchestration_module_configs`
- `延期能力项`：
  - `runtime_state_machine`
  - `tenant_runtime_routes`
  - `frontend_pages`
  - `generic_host_plugin_settings_ui`
  - `hosted_trigger_execution_entrypoints`
  - `solution_bindings / eval_links / daily_metrics`
- `当前替代口径`：
  - 当前交付只承诺插件壳、设计时模型、迁移、管理端接口、AI-2 可依赖的 runtime-support 表结构
  - 触发器当前只建模与持久化，不实现第一版执行入口

## 4. 对 AI-2 的共享真相

- `模板主字段`：
  - `WorkflowTemplate`：`code`、`name`、`description`、`category`、`status`、`builder_surface`、`release_scope`、`tags_json`、`metadata_json`、`risk_policy_json`、`contract_summary_json`、`default_trigger_json`、`latest_version_no`、`latest_version_id`、`current_published_version_id`、`latest_release_id`
  - `WorkflowTemplateVersion`：`template_id`、`version_no`、`status`、`snapshot_version`、`workflow_schema_version`、`snapshot_hash`、`snapshot_json`、`change_summary`、`release_notes`、`compiled_at`、`compiled_by`、`published_at`、`published_by`、`is_latest`、`is_published`
  - `WorkflowTemplateNode`：`node_key`、`node_type`、`title`、`description`、`sort_order`、`timeout_minutes`、`retry_limit`、`config_json`、`position_json`、`input_contract_json`、`output_contract_json`、`policy_json`、`metadata_json`
  - `WorkflowTemplateEdge`：`edge_key`、`from_node_key`、`from_port`、`to_node_key`、`to_port`、`sort_order`、`condition_json`、`metadata_json`
- `企业工作流主字段`：
  - `TenantWorkflow`：`tenant_id`、`source_template_id`、`source_release_id`、`code`、`name`、`description`、`status`、`mode`、`editable_level`、`is_simple_builder`、`builder_surface`、`workflow_json`、`summary_json`、`settings_json`、`metadata_json`、`latest_version_no`、`latest_version_id`、`active_version_id`、`current_release_id`
  - `TenantWorkflowVersion`：`workflow_id`、`version_no`、`status`、`source_template_version_id`、`snapshot_version`、`workflow_schema_version`、`snapshot_hash`、`snapshot_json`、`change_summary`、`compiled_at`、`compiled_by`、`published_at`、`published_by`、`is_latest`、`is_published`
- `运行时主字段`：
  - `WorkflowRun`：`tenant_id`、`workflow_id`、`workflow_template_id`、`workflow_version_id`、`release_id`、`trigger_id`、`environment_id`、`parent_run_id`、`code`、`status`、`entrypoint`、`initiated_by`、`initiated_from`、`started_by_type`、`mode`、`current_node_key`、`trace_id`、`idempotency_key`、`retry_count`、`input_payload_json`、`output_payload_json`、`cost_summary_json`、`control_envelope_json`、`budget_snapshot_json`、`risk_snapshot_json`、`metrics_json`、`error_summary`
  - `WorkflowNodeRun`：`run_id`、`tenant_id`、`parent_node_run_id`、`node_key`、`node_type`、`status`、`attempt_no`、`executor_type`、`executor_ref`、`trace_id`、`input_envelope_json`、`output_envelope_json`、`cost_json`、`metrics_json`、`error_summary`、`duration_ms`
  - `WorkflowCheckpoint`：`run_id`、`node_run_id`、`tenant_id`、`checkpoint_type`、`resume_token`、`state_hash`、`snapshot_json`
  - `WorkflowEvent`：`run_id`、`node_run_id`、`tenant_id`、`event_type`、`event_level`、`event_code`、`status_from`、`status_to`、`message`、`trace_id`、`payload_json`、`occurred_at`
  - `WorkflowArtifact`：`tenant_id`、`run_id`、`node_run_id`、`workflow_id`、`workflow_version_id`、`code`、`name`、`artifact_type`、`status`、`schema_ref`、`mime_type`、`storage_uri`、`storage_path`、`summary`、`content_json`、`content_text`、`visibility_scope`、`size_bytes`、`content_hash`、`feedback_summary`、`download_filename`、`retention_policy_json`、`metadata_json`
- `兼容别名真相`：
  - `WorkflowTemplateVersion.workflow_template_id -> template_id`
  - `TenantWorkflowVersion.tenant_workflow_id -> workflow_id`
  - `WorkflowRun.tenant_workflow_id -> workflow_id`
  - `WorkflowRun.started_by_id -> initiated_by`
  - `WorkflowRun.trigger_source -> initiated_from`
  - `WorkflowRun.input_payload -> input_payload_json`
  - `WorkflowRun.output_payload -> output_payload_json`
  - `WorkflowRun.cost_summary -> cost_summary_json`
  - `WorkflowNodeRun.workflow_run_id -> run_id`
  - `WorkflowNodeRun.input_payload -> input_envelope_json`
  - `WorkflowNodeRun.output_payload -> output_envelope_json`
  - `WorkflowNodeRun.error_detail -> error_summary`
  - `WorkflowCheckpoint.workflow_run_id -> run_id`
  - `WorkflowCheckpoint.workflow_node_run_id -> node_run_id`
  - `WorkflowCheckpoint.snapshot_payload -> snapshot_json`
  - `WorkflowEvent.workflow_run_id -> run_id`
  - `WorkflowEvent.workflow_node_run_id -> node_run_id`
  - `WorkflowEvent.detail -> payload_json`
  - `WorkflowArtifact.workflow_run_id -> run_id`
  - `WorkflowArtifact.workflow_node_run_id -> node_run_id`
  - `WorkflowArtifact.title -> name`
  - `WorkflowArtifact.visibility -> visibility_scope`
  - `WorkflowArtifact.hash -> content_hash`
- `默认值 / 可空策略真相`：
  - 自动默认值：`TenantWorkflow.code`、`WorkflowRun.code`、`WorkflowArtifact.code`、`WorkflowArtifact.name`
  - 自动快照哈希：`TenantWorkflowVersion.snapshot_hash` 基于 `snapshot_json` 计算
  - 兼容当前 AI-2 写入路径而放宽的字段：
    - `runs.workflow_version_id`
    - `node_runs.tenant_id`
    - `checkpoints.tenant_id`
    - `events.tenant_id`
    - `artifacts.tenant_id`
    - `artifacts.workflow_id`
    - `artifacts.workflow_version_id`
- `版本快照结构`：
  - `snapshot_version`
  - `workflow_schema_version`
  - `contract_refs`
  - `control_envelope_schema`
  - `graph`
  - `entrypoints`
  - `defaults`
  - `risk_policy_snapshot`
  - `trigger_snapshot`
  - `artifact_contracts`
  - `output_contracts`
  - `builder_surface`
  - `compiled_at`
  - `compiled_by`
- `快照字段真相`：
  - 平台模板真相：`px_workflow_orchestration_template_versions.snapshot_json`
  - 企业工作流真相：`px_workflow_orchestration_tenant_workflow_versions.snapshot_json`
- `状态枚举`：
  - `TemplateStatusEnum`：`draft`、`published`、`deprecated`、`archived`
  - `ReleaseStatusEnum`：`draft`、`reviewing`、`approved`、`published`、`disabled`、`deprecated`、`rolled_back`
  - `ReleaseScopeEnum`：`platform_catalog`、`selected_tenants`、`tenant_private`
  - `ReleaseChannelEnum`：`stable`、`beta`、`internal`
  - `WorkflowKindEnum`：`template`、`tenant_workflow`
  - `BuilderSurfaceEnum`：`platform_workflow_studio`、`tenant_template_editor`、`tenant_simple_builder`
  - `TriggerTypeEnum`：`manual`、`schedule`、`api`、`webhook`、`event`
  - `TriggerStatusEnum`：`draft`、`active`、`disabled`
  - `EnvironmentScopeEnum`：`platform`、`tenant`
  - `EnvironmentStatusEnum`：`provisioned`、`activated`、`pilot`、`live`、`suspended`
  - `ChangeSetStatusEnum`：`draft`、`reviewing`、`approved`、`published`、`rolled_back`、`archived`
  - `ConfigScopeEnum`：`global`、`tenant_default`
  - `RunStatusEnum`：`pending`、`running`、`waiting_human`、`succeeded`、`failed`、`cancelled`
  - `ArtifactTypeEnum`：`draft`、`report`、`recommendation`、`approval_packet`、`evidence_bundle`、`dataset`、`media`
  - `ArtifactStatusEnum`：`draft`、`ready`、`archived`、`failed`
  - `EventLevelEnum`：`info`、`warning`、`error`、`audit`
  - `CheckpointTypeEnum`：`state_snapshot`、`artifact_snapshot`、`compensation_anchor`

## 5. 已执行验证

- `模型/迁移 drift 验证`：
  - 已运行只读脚本，对比 `backend/models/*.py` 的 `Table.indexes` / `UniqueConstraint` 与 `001_initial.py` 的 `create_index` / `UniqueConstraint`
  - 结果：`index/unique parity ok`
- `编译验证`：
  - `python -m compileall backend/plugins/workflow-orchestration/backend/models backend/plugins/workflow-orchestration/backend/migrations`
  - 结果：通过
- `加载验证`：
  - `load_plugin_module('workflow-orchestration', 'models')`：`True`
  - `load_plugin_module('workflow-orchestration', 'models.runtime')`：`True`
  - `runtime.model_access.resolve_model()` 对以下 key 返回正常：
    - `workflow_template`
    - `workflow_template_version`
    - `tenant_workflow`
    - `tenant_workflow_version`
    - `workflow_run`
    - `workflow_node_run`
    - `execution_checkpoint`
    - `execution_event`
    - `execution_artifact`
- `迁移执行验证`：
  - 未在真实 PostgreSQL 上执行 `upgrade` / `downgrade`
  - 当前只完成静态链路校验与元数据对齐校验

## 6. 已知问题与剩余未决点

- `已解决的旧问题`：
  - 旧 handoff 中关于 `models.runtime` loader 失败的 caveat 已失效，当前实测 `load_plugin_module('workflow-orchestration', 'models.runtime')` 返回成功
  - 旧的模型/迁移 index drift 已收口，不再把这一项留给 integrator
- `剩余未决点`：
  - 真实数据库上的 `001 -> 002` 执行结果尚未在 PostgreSQL 实库验证
  - `002_fix_workflow_version_nullability.py` 被保留在迁移链中；当前最终真相已明确，但该修正迁移在一套全新从头执行的链路中不会再引入额外 schema 变化
  - 宿主侧正式 `product_module` manifest 一等字段、宿主统一插件设置扩展口、frontend pages、tenant runtime routes 仍不在 AI-1 本轮写入范围内
