# 数据范围治理审计与整改记录

日期：2026-03-24

## 目标

把“组织负责人控制表格可见数据范围”从组织架构页面的配置能力，真正落到后端统一查询层。

本次整改的核心要求：

- 负责人在组织树上的数据范围，不再只影响组织页本身。
- 仓储层、插件服务层、运行态查询，都要尽量复用统一数据权限上下文。
- 对没有 `org_node_id` / `dept_id` 的业务表，允许通过“创建人所在组织”回退过滤。
- 对运行态链路表，允许通过父资源继承数据范围。

## 已完成整改

### 1. 统一数据权限基础层

- `backend/app/middleware/permission.py`
  - 数据权限上下文新增 `current_user_scope`
  - 数据权限上下文新增 `current_tenant_id`
- `backend/app/core/data_permission.py`
  - 新增统一启用判断：不再只依赖显式 `__data_permission__`
  - 支持 `created_by` / 自定义创建人字段回退
  - 支持创建人类型字段（例如 `started_by_type`）
  - 支持父资源继承数据范围
  - 支持不同身份范围不匹配时跳过错误过滤，避免跨域共享资源被误拦截
- `backend/app/core/base_repository.py`
  - 创建时自动补齐 `created_by / org_node_id / dept_id`
  - 批量更新、批量删除、回收站恢复、物理删除增加数据范围约束
  - 回收站计数增加数据范围约束

### 2. AI 模块接入

- `backend/app/models/ai/agent_version.py`
- `backend/app/models/ai/batch_run.py`
- `backend/app/repositories/ai/agent_version_repository.py`
- `backend/app/repositories/ai/batch_run_repository.py`

已将版本记录、批量运行记录纳入组织数据范围；仓储里的手写 `select(...)` 也补上统一过滤。

### 3. NovusDoc 文档接入

- `backend/plugins/novusdoc/backend/models/document.py`
- `backend/plugins/novusdoc/backend/services/document_service.py`

文档列表、详情、更新、删除已经接入统一数据范围。

### 4. Workflow Orchestration 接入

已接入的模型：

- `backend/plugins/workflow-orchestration/backend/models/template.py`
- `backend/plugins/workflow-orchestration/backend/models/release.py`
- `backend/plugins/workflow-orchestration/backend/models/runtime.py`

本次处理了两类场景：

- 根资源表：
  - 模板
  - 模板版本
  - 发布记录
  - 变更集
  - 环境
  - 模块配置
  - 租户工作流
  - 租户工作流版本
- 运行态链路表：
  - 运行记录
  - 节点运行
  - 检查点
  - 事件
  - 产物

运行态链路不再只靠 `tenant_id`。对于无直接组织字段的表，本次通过父级关系继承范围：

- `WorkflowNodeRun -> WorkflowRun`
- `WorkflowCheckpoint -> WorkflowRun`
- `WorkflowEvent -> WorkflowRun`
- `WorkflowArtifact -> WorkflowRun`
- `TenantWorkflowVersion -> TenantWorkflow`
- `WorkflowTemplateVersion -> WorkflowTemplate`

已接入的服务层：

- `backend/plugins/workflow-orchestration/backend/services/template_service.py`
- `backend/plugins/workflow-orchestration/backend/services/release_service.py`
- `backend/plugins/workflow-orchestration/backend/services/tenant_workflow_service.py`
- `backend/plugins/workflow-orchestration/backend/services/run_query_service.py`
- `backend/plugins/workflow-orchestration/backend/services/artifact_service.py`
- `backend/plugins/workflow-orchestration/backend/services/module_config_service.py`
- `backend/plugins/workflow-orchestration/backend/services/run_service.py`
- `backend/plugins/workflow-orchestration/backend/services/_data_scope.py`

## 仍需补齐的结构性问题

以下问题不是“代码没接过滤器”，而是“模型本身缺少稳定的组织归属字段”，所以只能先做部分回退，无法像主系统组织表那样绝对精确：

### 1. NovusDoc 文件夹 / 标签

- `backend/plugins/novusdoc/backend/services/folder_service.py`
- `backend/plugins/novusdoc/backend/services/tag_service.py`

现状：

- 只有 `tenant_id`
- 没有 `org_node_id`
- 没有 `created_by`
- 也没有稳定的父资源链路可继承组织范围

影响：

- 目前仍只能做到租户隔离，不能做到组织负责人级别的精细过滤

建议：

- 给文件夹、标签补 `created_by`
- 或者补 `org_node_id`

### 2. 某些运行态动作类服务仍建议继续做专项回归

- `backend/plugins/workflow-orchestration/backend/services/recovery_service.py`

原因：

- 本次已把它依赖的运行查询主链路打通
- 但恢复动作类逻辑较长，建议后续做一轮专门的 API 场景回归

## 验证结果

已通过：

- `pytest tests/core/test_data_permission.py -q`
- `pytest plugins/workflow-orchestration/backend/tests/runtime/test_storage_and_service_contracts.py -q`
- `pytest plugins/workflow-orchestration/backend/tests/runtime/test_artifact_download_paths.py -q`
- `pytest plugins/workflow-orchestration/backend/tests/runtime/test_model_access_and_serializer.py -q`
- 相关文件 `compileall`

## 本次治理后的判定

可以认定：

- 主系统组织负责人的数据范围，已经不再只是“组织页配置”
- AI 版本/批量运行、NovusDoc 文档、Workflow 的模板态与运行查询主链路，已经接入统一数据范围

不能认定完全 100% 结束的部分：

- 所有缺少组织归属字段的历史插件表
- 尤其是 NovusDoc 文件夹 / 标签 这类没有 `created_by` 也没有父链继承的表

如果要彻底做满，全仓最稳的下一步不是继续补 if 判断，而是补字段：

- `org_node_id`
- 或 `created_by`
- 或可继承的父资源外键
