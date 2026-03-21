# NovusAI SaaS 回收站双阶段改造审计报告

## 结论

本次回收站体系不是“局部修补”，而是一次有意的语义纠偏：

- 旧实现把 `delete_level` 同时承担了“删除侧别”和“回收阶段”两类含义，导致“管理端 / 企业端”和“模块回收站 / 总回收站”混成一层数据的两个入口。
- 现实现将两类概念拆开：
  - `delete_level` 仅表示删除侧别：`admin` / `tenant`
  - `recycle_stage` 明确表示回收阶段：`module` / `global`
  - `promoted_to_global_at` 记录进入总回收站时间

这属于破坏性语义修正，但数据迁移策略已内置：

- 旧数据中 `is_deleted = true` 且 `delete_level = 'admin'` 的记录，回填为 `recycle_stage = 'global'`
- 旧数据中 `is_deleted = true` 且 `delete_level in ('tenant', null)` 的记录，回填为 `recycle_stage = 'module'`
- 恢复时统一清空 `delete_level`、`recycle_stage`、`deleted_at`、`promoted_to_global_at`

## 审计表

| 模块/能力 | 当前行为（审计时） | 与目标差异 | 处理方式 |
| --- | --- | --- | --- |
| 数据模型 / 生命周期 | `delete_level` 混用“admin/tenant 侧别”和“是否进入总回收站”的旧语义，无法稳定表达“双层 30 天” | 无法区分“还在模块回收站”和“已进入总回收站” | 新增并落地 `recycle_stage`、`promoted_to_global_at`；`delete_level` 退回为纯侧别字段 |
| 列表页首次删除 | 软删除后进入统一 deleted 集合，但后续行为因模块不同而分裂 | 不满足“列表删除 -> 模块回收站”这一固定起点 | 统一为：首次删除必写入 `is_deleted=true`、`deleted_at=T0`、`recycle_stage='module'` |
| 模块回收站删除按钮 | 部分管理端实现是直接物理删除；部分企业端实现是“升级到管理端回收站”式旧语义 | 明确违反“模块回收站不是用户主路径终点” | 控制器路由统一改为 `promote_to_global` / `batch_promote_to_global` |
| 模块回收站恢复 | 恢复逻辑存在，但未严格限定阶段，容易把总回收站数据也从模块接口恢复 | 阶段边界不清 | 模块回收站恢复统一限定 `recycle_stage='module'` |
| 管理端总回收站聚合 API | 仅有管理端聚合能力，且查询语义仍受旧 `delete_level` 设计影响 | 不是真正第二层总回收站 | 改为只查询 `recycle_stage='global'`，并重建 summary/list/restore/permanent delete/clear API |
| 企业端总回收站聚合 API | 缺失对称企业端总回收站 API | 与目标“企业端同样模块 -> 总回收站”不一致 | 新增 `/tenant/recycle-bin/*` 聚合接口，并在服务定位中强制传入 `tenant_id` |
| 删除依赖检查 | 首次删除路径已有 `__delete_deps__` 体系，但前后端接入不完全一致 | 需要保证所有首次删除都继续返回 `4221 + dependencies` | 保留 `delete-preview` + `DependencyBlockedException(4221)`；`useCrudPage` / `useCrudList` / 非表格页继续走 `DependencyBlockModal` |
| 推进总回收站 / 恢复时依赖检查 | 旧实现没有阶段化规则 | 需要明确哪些动作重新检查依赖 | 规则定为：只有首次删除进入模块回收站时执行依赖检查；推进总回收站、从任一阶段恢复、总回收站物理删除不重复做 BLOCK 检查 |
| 定时任务 `cleanup_recycle_bin` | 清理逻辑围绕旧 `delete_level` 工作，不能表达模块阶段到总回收站的推进；同时存在通过批量语句/旧语义绕过服务钩子的风险 | “30 + 30” 无法生效，且不幂等不清晰 | 重写为两阶段：先推进 `module -> global`，再物理删除 `global -> purge`，每阶段按服务层逐条执行，保留级联钩子 |
| 定时任务无效果根因 | 1. 生命周期字段设计错误；2. 任务只看旧侧别，不看阶段；3. 部分旧清理路径绕过 service/repository 语义；4. 企业端缺少总回收站聚合链路；5. `20260213_seed_recycle_bin_cleanup_task.py` 中 seed 使用了无效 `scope='platform'` | 无法稳定推进，也难以从 UI 验证 | 修正字段设计、重写任务、修正 seed scope 为 `admin_only`、补足企业端 API 和 UI |
| 手动触发 cleanup API | 新增了分阶段参数，但默认 `retention_days=30` 会覆盖 `module_retention_days/global_retention_days` | 分阶段参数形同无效 | 将管理端 cleanup 路由的 `retention_days` 默认值改为 `None`，仅显式传入时才覆盖两个阶段 |
| 管理端总回收站 UI | 旧页面列窄、筛选假、与业务列表 schema 脱节 | 不满足“同源列/搜索/排序” | 重做为共享页：顶部 summary + 动态模块 chips + 动态 search form + 动态列 + 排序 + 恢复/最终删除/清空模块 |
| 企业端总回收站 UI | 缺失 | 与目标不符 | 新增企业端总回收站页面，并复用共享页基础设施 |
| 总回收站字段来源 | 旧实现主要靠页面内硬编码列和搜索项 | 与业务页 schema 不一致，难维护 | 采用“后端元数据 + 前端 adapter 覆盖”双层方案：后端 `build_module_metadata()` 下发 `columns/filterable/sortable/label_field/column_labels`；前端对重点模块复用业务页 `data.ts` 的 searchSchema/列定义 |
| RECYCLABLE_MODULES 对齐 | 旧管理端聚合模块表述较窄，重点模块列不全 | 总回收站信息密度不够 | 扩展 `backend/app/api/shared/recycle_bin_registry.py` 的重点模块列集合，覆盖 AI Provider / AI Model / Agent / KB / Periodic Task / Tenant Plan / Tenant |
| 管理端租户筛选 | 旧共享页实现会默认写死 `filter[tenant_id]` | 对 `owner_tenant_id` 型资源不稳 | 共享页改为按后端 `tenant_field` 动态生成租户筛选 schema |
| 总回收站排序 | 切模块时沿用上一模块的 sort 值，可能携带新模块不支持的排序字段 | 会触发 JSON:API unknown sort field | 切模块时校验候选 sort 是否在新模块 sort options 中，否则退回模块默认排序 |
| 前端声明式 CRUD 集成 | 旧 `RecycleBinDrawer` 仍保留“升级到管理端回收站”等旧文案 | 用户心智错误 | 改为明确文案：“移入总回收站”；保留两阶段 30+30 提示 |
| codegen / 模板同步 | CRUD 模板继续通过 `register_admin_recycle_bin_routes` / `register_tenant_recycle_bin_routes` 接入 | 若核心 helper 不同步，后续生成模块会回退 | 由于核心 helper 已改为新语义，现有 codegen 模板自动继承新行为；`db_introspector` 同步纳入 `recycle_stage/promoted_to_global_at` |
| i18n | 缺少双阶段相关 key，管理端/企业端总回收站文案不完整 | 新 UI 无法完整本地化 | 补齐 `common.recycleBin.*`、`admin.system.recycleBin.*`、`tenant.system.recycleBin.*` 中英对齐键值 |
| 权限与隔离 | 企业端总回收站缺失，无法形成完整 RBAC 面 | 不满足企业隔离 | 新增 tenant 端 `permission_resource("recycle_bin")` 菜单与接口；tenant 聚合 API 和 clear/delete/restore 均通过 tenant-scoped service 执行 |

## 状态机说明

### 1. 首次删除

- 入口：业务列表页 / 声明式 CRUD 页的 Delete
- 前置：执行 `delete-preview` 与 `__delete_deps__`
- 结果：
  - `is_deleted = true`
  - `deleted_at = T0`
  - `delete_level = admin | tenant`
  - `recycle_stage = module`
  - `promoted_to_global_at = null`

### 2. 推进到总回收站

- 入口：
  - 模块回收站手动删除
  - `cleanup_recycle_bin` 第一阶段定时推进
- 结果：
  - `recycle_stage = global`
  - `promoted_to_global_at = T1`
  - 其他软删字段保留

### 3. 恢复

- 入口：
  - 模块回收站 restore：仅限 `recycle_stage = module`
  - 总回收站 restore：仅限 `recycle_stage = global`
- 结果：
  - `is_deleted = false`
  - `deleted_at = null`
  - `delete_level = null`
  - `recycle_stage = null`
  - `promoted_to_global_at = null`

### 4. 最终物理删除

- 入口：
  - 总回收站手动永久删除
  - `cleanup_recycle_bin` 第二阶段定时清理
- 前置：仅允许 `recycle_stage = global`
- 执行：走 `service.permanent_delete()`，保留 repository/service 钩子与级联行为

## 总回收站元数据复用方案

当前实现采用“后端下发为基础，前端共享 schema 为增强”的组合方案：

- 后端：
  - `backend/app/api/shared/recycle_bin_registry.py`
  - 统一下发 `columns`、`filterable`、`sortable`、`label_field`、`column_labels`、`tenant_field`
- 前端：
  - `frontend/apps/web-antd/src/views/_shared/recycle-bin/recycle-bin-page.vue`
  - `frontend/apps/web-antd/src/views/admin/system/recycle-bin/adapters.ts`
  - `frontend/apps/web-antd/src/views/tenant/system/recycle-bin/adapters.ts`

优先级如下：

1. 若模块已配置前端 adapter，则直接复用业务列表页 `data.ts` 的搜索 schema / 列定义
2. 若模块没有 adapter，则退回后端 metadata 驱动的动态搜索和动态列
3. 排序始终以后端 `sortable` 为底，默认优先 `promoted_to_global_at`、`deleted_at`

这样可以同时满足：

- 重点模块与业务列表“同源”
- 非重点模块不需要再维护第二套窄列配置
- `RECYCLABLE_MODULES` 仍是后端权威来源

## 已落地验证

- 后端新增 8 条定向 pytest 用例，覆盖：
  - 模块回收站路由阶段过滤
  - 模块回收站删除推进总回收站
  - 静态批量路由优先于动态 `{item_id}`
  - 管理端 / 企业端总回收站 global-stage 查询
  - tenant scoped service lookup
  - 两阶段 cleanup task
  - `4221` 依赖阻断
- 前端新增 3 条 vitest 用例，覆盖：
  - fallback tenant filter 使用后端 `tenant_field`
  - adapter schema 会被后端 `filterable` 收敛
  - 总回收站公共列与默认排序项生成
- locale JSON 已做语法校验
- `frontend/apps/web-antd` 已通过 `vue-tsc --noEmit --skipLibCheck`

## 风险与遗留

### 1. 空库 `alembic upgrade heads`

本次已执行验证，但当前仓库在本地环境失败，错误为：

- `Can't locate revision identified by 'sm_001_init'`

定位结果：

- 插件迁移文件存在：`backend/plugins/storage-migration/backend/migrations/versions/001_init.py`
- 但当前 core Alembic 调用路径无法在升级图中定位该 revision

这更像现有仓库的迁移装配问题，而不是本次回收站改动引入的问题；本次新增迁移本身未在验证中暴露语法错误。

### 2. 总回收站重点模块覆盖范围

当前已优先对齐的重点模块：

- Admin: `ai_providers`, `ai_models`, `periodic_tasks`, `tenant_plans`, `tenants`
- Tenant: `agents`, `knowledge_bases`, `periodic_tasks`

其余模块先使用后端 metadata fallback，可继续按业务优先级追加 adapter。
