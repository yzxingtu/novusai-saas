# 定时任务与任务日志重构方案

## 背景

当前系统的 `periodic_tasks` 与 `task_logs` 同时承担了以下几类职责：

- 系统级任务定义
- 资源投放范围表达
- 企业归属表达
- 企业端运行对象表达
- 运维日志与业务结果展示

这导致 `admin` / `tenant` 边界、任务投放模型、日志语义和前端信息架构全部发生耦合，已经无法通过局部字段修补解决。

## 现状问题

### 1. 端别边界错误

- 企业端历史上直接暴露了系统级定时任务管理与任务日志，现已从主链路移除。
- 这与项目规则中“企业端以使用权为主，不暴露系统运维能力”的约束冲突：
  - [tenant-architecture.md](E:/git_clone/novusai-saas-yudi/.cursor/rules/tenant-architecture.md)
  - [async-notification-websocket.md](E:/git_clone/novusai-saas-yudi/.cursor/rules/async-notification-websocket.md)

### 2. `periodic_tasks` 模型语义混杂

- [periodic_task.py](E:/git_clone/novusai-saas-yudi/backend/app/models/system/periodic_task.py) 同时表达：
  - 任务定义
  - 调度配置
  - 作用域
  - 归属企业
- 这让 `scope`、`owner_tenant_id`、`tenant_id` 的语义长期漂移。

### 3. 无法支持按企业下发 A/B/C 任务集

- 当前没有把 `periodic_task` 接入通用企业分配机制：
  - [resource_tenant_assignment_repository.py](E:/git_clone/novusai-saas-yudi/backend/app/repositories/system/resource_tenant_assignment_repository.py)
- `selected_tenants` / `admin_and_selected_tenants` 没有真正落地成“分配到哪些企业”的独立模型。

### 4. 调度执行链路不支持多企业多实例

- Beat 加载逻辑只读 `periodic_tasks` 表，不看企业分配：
  - [scheduler.py](E:/git_clone/novusai-saas-yudi/backend/app/tasks/scheduler.py)
- 运行中又按 `task_path` 回写时间戳：
  - [base.py](E:/git_clone/novusai-saas-yudi/backend/app/tasks/base.py)
- 这意味着同一底层任务无法稳定承载多企业多套策略。

### 5. tenant 任务自动执行会丢失企业上下文

- 历史 tenant 旧链路手动触发时才临时补 `tenant_id`，缺少统一包装层。
- Beat 自动执行只会发库中的 `kwargs`，没有统一 tenant 上下文包装层。

### 6. 日志模型缺少调度语义

- [task_log.py](E:/git_clone/novusai-saas-yudi/backend/app/models/system/task_log.py) 没有记录：
  - 属于哪条任务定义
  - 属于哪条企业绑定
  - 是谁触发的
  - 运行时 scope 快照
- 后续无法可靠分析“平台任务”和“企业结果”。

### 7. 前端信息架构失真

- admin 定时任务 UI 只开放 `admin_only` 与 `all_tenants`，无法表达“指定企业”：
  - [frontend/apps/web-antd/src/views/admin/system/periodic-tasks/data.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/system/periodic-tasks/data.ts)
- tenant 侧历史上曾把系统运维能力做成完整 CRUD 页面，其源码现已删除，但边界问题仍作为本次重构背景保留。

## 重构目标

### 业务目标

- 支持平台按企业下发不同任务组合
- 区分“平台管理权”和“企业使用权”
- 将系统运维日志与企业业务结果拆开
- 为后续插件任务、业务自动化、企业覆盖策略提供统一模型

### 技术目标

- 去除 `scope`、`owner_tenant_id`、`tenant_id` 的混用
- 让调度实例具有稳定主键，不再依赖 `task_path`
- 让日志与“任务定义 / 绑定 / 触发来源”建立强关联
- 让 tenant 侧彻底退出系统任务治理链路

## 目标架构

### 一、权限与作用域模型

保留 4 个概念，但严格分层：

1. `PermissionScope`
   - 只表达端别：`admin` / `tenant` / `user`
   - 系统任务治理能力只保留在 `admin`

2. `ResourceScopeEnum`
   - 只表达资源投放范围
   - 平台任务是否可被企业消费，应通过 `ResourceScopeEnum + resource_tenant_assignments` 表达

3. `owner_tenant_id`
   - 只表达资源归属
   - 企业自建资源才有归属企业

4. `effective_tenant_id`
   - 只表达某次运行真正影响的企业

### 二、数据模型

建议拆成 3 层：

#### 1. `task_definition`

平台任务目录，字段建议：

- `id`
- `code`
- `name`
- `handler_path`
- `category`
- `description`
- `default_schedule_type`
- `default_cron_expression`
- `default_interval_seconds`
- `is_system_builtin`
- `is_editable`
- `is_deletable`
- `scope`
- `owner_tenant_id`

职责：

- 表达“这是什么任务”
- 不直接承载企业启停

#### 2. `tenant_task_binding`

企业绑定与覆盖层，字段建议：

- `id`
- `task_definition_id`
- `tenant_id`
- `is_enabled`
- `schedule_type_override`
- `cron_expression_override`
- `interval_seconds_override`
- `config_override`
- `last_run_at`
- `next_run_at`
- `last_status`

职责：

- 表达“企业 A 是否启用任务 B”
- 支持 A/B/C 按企业组合下发

#### 3. `task_run`

统一运行记录层，字段建议：

- `id`
- `celery_task_id`
- `task_definition_id`
- `binding_id`
- `task_code_snapshot`
- `task_name_snapshot`
- `trigger_source`
- `run_kind`
- `owner_tenant_id`
- `effective_tenant_id`
- `status`
- `summary`
- `args_summary`
- `result_summary`
- `error_code`
- `error_message_public`
- `error_message_internal`
- `traceback_internal`
- `trace_id`
- `started_at`
- `finished_at`
- `duration_ms`

职责：

- 统一平台运行观测
- 支持对 tenant 暴露脱敏后的业务结果

## 端侧设计

### admin 端

保留 3 个模块：

1. 任务模板库
   - 查看和维护任务定义
   - 区分系统任务 / 插件任务 / 可下发任务

2. 企业分配与绑定
   - 给企业启用或停用任务
   - 支持批量绑定
   - 支持企业侧覆盖频率或配置

3. 运行中心
   - 最近失败
   - 按任务模板看
   - 按企业看
   - 慢任务
   - 手动触发与重试

### tenant 端

移除以下系统菜单与接口：

- `/tenant/system/periodic-tasks`
- `/tenant/system/task-logs`

tenant 只保留两类能力：

1. 业务模块内的自动化配置开关
   - 如“自动发送日报”“自动同步数据”

2. 与企业相关的自动处理结果页
   - 仅展示脱敏结果
   - 不展示 task path、cron、queue、traceback

## 执行链路改造

### 现状问题

- Beat 直接读 `periodic_tasks`
- Worker 回写按 `task_path`
- tenant 任务自动执行缺少统一 tenant 上下文

### 目标方案

引入统一包装任务，例如：

- `run_task_definition(task_definition_id)`
- `run_tenant_task_binding(binding_id)`

Beat 不再直接调业务 `task_path`，而是只调包装任务。

包装任务职责：

- 解析最终调度实例
- 统一注入 `tenant_id`
- 写入 `task_run`
- 调用真实业务 handler
- 汇总结果并回写状态

## 日志展示改造

### admin 日志

列表字段改成摘要优先：

- 任务名称
- 类型
- 触发来源
- 企业
- 状态
- 耗时
- 结果摘要
- 时间

详情再展示：

- 输入摘要
- 输出摘要
- 失败原因
- trace_id
- 内部 traceback

### tenant 结果页

只展示：

- 自动任务名称
- 执行结果
- 影响对象
- 建议动作
- 发生时间
- trace_id

不展示：

- traceback
- 原始 args/kwargs
- 内部 queue / handler_path
- 系统级 retry / cancel

## 分阶段落地

### Phase 1：边界止血

目标：

- 立刻收回 tenant 系统任务治理入口

改动：

- tenant 主 router 不再挂载周期任务与任务日志
- tenant 权限注册不再导入这两个 controller
- tenant 前端不再导出这两组 API
- tenant 前端页面入口删除
- 新增回归测试，确保 tenant 主路由不再暴露 `/tasks` 与 `/periodic-tasks`

### Phase 2：模型奠基

目标：

- 建立 `task_definition / tenant_task_binding / task_run`

改动：

- 增加 model / schema / repository / migration
- 增加旧数据到新模型的一次性迁移脚本

### Phase 3：执行链路切换

目标：

- Beat 改为调包装任务

改动：

- scheduler 改读新 binding 模型
- worker 改写 `task_run`
- 补统一 tenant context 注入
- 插件任务定义同步切到 `TaskDefinition`

### Phase 4：admin UI 重构

目标：

- 定时任务页与任务日志页彻底脱离旧 `PeriodicTask / TaskLog`
- 定时任务页拆成“模板 / 分配 / 运行中心”

### Phase 5：tenant 业务结果接入

目标：

- 不再暴露系统任务中心
- 在具体业务模块落“自动处理结果”

## 本轮实际启动内容

本轮先执行 Phase 1：

1. 文档落地
2. 移除 tenant 主路由暴露
3. 移除 tenant 前端入口
4. 增加回归测试

已启动的落地点：

- [backend/app/api/tenant/__init__.py](E:/git_clone/novusai-saas-yudi/backend/app/api/tenant/__init__.py)
- [frontend/apps/web-antd/src/api/tenant/index.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/api/tenant/index.ts)
- [backend/tests/core/test_tenant_system_task_boundaries.py](E:/git_clone/novusai-saas-yudi/backend/tests/core/test_tenant_system_task_boundaries.py)

Phase 2 已启动的落地点：

- [backend/app/models/system/task_definition.py](E:/git_clone/novusai-saas-yudi/backend/app/models/system/task_definition.py)
- [backend/app/models/system/tenant_task_binding.py](E:/git_clone/novusai-saas-yudi/backend/app/models/system/tenant_task_binding.py)
- [backend/app/models/system/task_run.py](E:/git_clone/novusai-saas-yudi/backend/app/models/system/task_run.py)
- [backend/migrations/versions/20260325_0002_task_scheduling_foundation.py](E:/git_clone/novusai-saas-yudi/backend/migrations/versions/20260325_0002_task_scheduling_foundation.py)
- [backend/migrations/versions/20260325_0003_task_definition_operational_fields.py](E:/git_clone/novusai-saas-yudi/backend/migrations/versions/20260325_0003_task_definition_operational_fields.py)
- [backend/migrations/versions/20260325_0004_backfill_task_definitions_from_periodic_tasks.py](E:/git_clone/novusai-saas-yudi/backend/migrations/versions/20260325_0004_backfill_task_definitions_from_periodic_tasks.py)
- [backend/migrations/versions/20260325_0005_drop_legacy_task_tables.py](E:/git_clone/novusai-saas-yudi/backend/migrations/versions/20260325_0005_drop_legacy_task_tables.py)

Phase 3 已启动的落地点：

- [backend/app/tasks/task_scheduling.py](E:/git_clone/novusai-saas-yudi/backend/app/tasks/task_scheduling.py)
- [backend/app/tasks/scheduler.py](E:/git_clone/novusai-saas-yudi/backend/app/tasks/scheduler.py)
- [backend/app/tasks/base.py](E:/git_clone/novusai-saas-yudi/backend/app/tasks/base.py)

当前 Phase 3 的策略已切换为“新模型主链路”：

- scheduler 以 `task_definitions` 与 `tenant_task_bindings` 为主
- 历史 `periodic_tasks` 数据通过迁移脚本回填到新模型
- `task_runs` 在 wrapper 分发并附带上下文 header 时写入
- 旧 tenant periodic-task / task-log 后端源码已删除
- 旧 `periodic_tasks` / `task_logs` 表已进入 drop 迁移队列

## 验收标准

### Phase 1 验收

- tenant 主 API 不再暴露 `/tenant/tasks`
- tenant 主 API 不再暴露 `/tenant/periodic-tasks`
- tenant 菜单同步后不再出现“定时任务 / 任务日志”
- tenant 前端不再保留对应系统页面入口
- admin 端现有页面不受影响

## 风险与注意事项

1. 旧权限与菜单数据需要依赖后端权限同步清理
2. 旧 tenant 直接访问收藏 URL 可能失效，这是符合新边界的预期变化
3. 配置服务当前已对重复 `system_configs.key` 做读取容错，但仍建议后续增加数据清理迁移
