---
name: novusai-saas
description: Umbrella skill for cross-cutting NovusAI SaaS work across FastAPI backend, Vue admin/tenant/user frontend, RBAC, AI modules, codegen, trace_id, and operations. Use when the task spans multiple subsystems or no narrower NovusAI skill fully covers it.
metadata:
  short-description: NovusAI umbrella guide
---

# NovusAI SaaS 全栈开发技能

> 当前 skill 是项目级总入口，不是大而全 reference。
> 若已有更窄的专用 skill 可以完整覆盖任务，优先使用专用 skill。
> 所有 reference 文件位于 `references/` 目录，按需加载，不要整包读入。

## 何时使用

- 任务同时跨前端、后端、AI、权限、trace_id、codegen 或运维治理
- 需要先判断该走哪个专用 skill 或哪个本地 reference
- 需要对 NovusAI 分层、约束和交付清单做整体把关

## 专题技能入口

- 上传 / 附件 / 图片：[attachment-storage](../attachment-storage/SKILL.md)
- AI 写作：[ai-writing](../ai-writing/SKILL.md)
- 页面感知 / 页面操作：[ai-page-awareness](../ai-page-awareness/SKILL.md)
- 知识库 / RAG：[knowledge-base-rag](../knowledge-base-rag/SKILL.md)
- 会话记忆：[session-memory](../session-memory/SKILL.md)
- AI 调用日志与账本：[ai-call-log-usage-ledger](../ai-call-log-usage-ledger/SKILL.md)
- WebSocket：[websocket-guide](../websocket-guide/SKILL.md)
- 数据库迁移：[database-migration-best-practices](../database-migration-best-practices/SKILL.md)
- 测试与浏览器验证：[testing-validation](../testing-validation/SKILL.md)
- 偏好设置：[preferences-governance](../preferences-governance/SKILL.md)
- 用户端：[user-endpoint](../user-endpoint/SKILL.md)
- Codegen Builder：[codegen-builder](../codegen-builder/SKILL.md)
- 插件开发：[plugin-development](../plugin-development/SKILL.md)
- Vben 升级 / 前端 lint 治理：[vben-upgrade-lint-governance](../vben-upgrade-lint-governance/SKILL.md)

## 快速开始

1. 先确认任务归属端：`admin` / `tenant` / `user` / `shared`
2. 再确认是 CRUD、AI、权限、用户端、迁移、codegen、trace_id，还是跨域任务
3. 优先加载对应专用 skill；没有专用 skill 时再读本 skill 的相关 reference
4. 不要启动前后端开发服务器，用户已预启动
5. 涉及图标时，必须同步查阅 [references/icon-spec.md](references/icon-spec.md)

开发环境默认信息：

- 后端：`http://localhost:8000`
- 前端：`http://localhost:5666`
- 管理端：`/admin/login`，`admin / admin123456`
- 企业端：`/tenant/login`，`adminsss / admin123456`

## 技术栈

| 端 | 技术 |
|---|---|
| 前端 | Vue 3.5 + TypeScript + Vben Admin 5.x + Ant Design Vue + Vite 6.x + Tailwind CSS |
| 后端 | Python 3.11+ + FastAPI + SQLAlchemy 2.x Async + PostgreSQL + Alembic |
| 鉴权 | JWT（access / refresh / impersonate） |
| 查询协议 | JSON:API（`filter` / `sort` / `page`） |

## 全局硬约束

- 禁止硬编码用户可见文本：前端统一 `$t()` / `t()`，后端统一 `_()`
- 禁止 `console.log`；前端调试只保留 `console.warn` / `console.error`
- 禁止业务代码滥用 `any`
- 禁止魔法字符串；后端用 `LabeledEnum`，前端用常量/枚举
- 禁止跨端导入：admin 页面不导入 tenant/user 模块，跨端共享逻辑放共享层
- 禁止层级越权：Controller 不写业务，Service 不直接拼裸 SQL，Repository 不写业务判断
- 禁止裸返回；后端统一用 `success()` / `created()` / `paginated()` / `deleted()`
- 禁止手写重复 Schema；前端优先用 `searchInput()` / `inputField()` 等辅助函数
- 禁止在宿主主系统里写插件业务代码；插件逻辑必须留在 `backend/plugins/{name}/`
- 禁止依赖在线图标 API；平台功能图标统一用本地图标方案
- 插件菜单标题来自 `plugin.yaml -> pages[*].menu.title`，不要写回后端 `menu.json`
- 普通插件页面只允许走 `/plugin-assets/...` + `{ endpoint }`；公开登录页 captcha 才允许走 `/plugin-public-assets/...` + `{ publicEndpoint }`
- 插件切语言后，宿主必须同时刷新 `/permissions/menus`、`/plugins/slots` 和当前活动 route meta；插件专题细则统一以下面的 [plugin-development](../plugin-development/SKILL.md) 为准

基础设施统一规则：

- trace_id 通过请求头 `X-Trace-ID` 贯穿全链路，后端通过 `trace_id_var.get()` 取值
- 日志统一走 `app.core.logging`，常规模块 `get_logger(__name__)`，Service 优先 `LoggerMixin`
- 上传必须走 `AttachmentService`；前端业务页面必须用 `smartUploadFile` 或其业务封装
- 下载必须走 `requestClient.download` + `downloadBlob`

参考：

- [references/platform-infrastructure.md](references/platform-infrastructure.md)
- [references/public-config-branding-captcha.md](references/public-config-branding-captcha.md)
- [references/download-spec.md](references/download-spec.md)
- [references/trace-id-logging-spec.md](references/trace-id-logging-spec.md)

## 交付主流程

1. 先判定任务域：后端 CRUD、前端 CRUD、AI、权限、用户端、异步任务、trace_id、codegen、迁移
2. 只读取当前任务直接需要的专用 skill 或 reference
3. 在正确层级落实现：Controller / Service / Repository / Model，或 views / composables / api / utils
4. 补上必要的 i18n、权限、菜单、迁移、测试和 trace_id 验证
5. 完成后按 [references/delivery-checklist.md](references/delivery-checklist.md) 做自检

## 后端 CRUD

标准顺序：

1. `Model`
2. `Schema`
3. `Repository`
4. `Service`
5. `Controller`
6. 路由注册
7. Alembic 迁移

关键要点：

- Model 按场景继承 `TenantModel` / `BaseModel`
- 需要列表过滤和排序时声明 `__filterable__` / `__sortable__`
- 被其他表引用的父实体声明 `__delete_deps__`
- 如果数据需要被 AI 数据智能或 Text-to-SQL 看见，必须声明 `__ai_policy__`
- `TenantController.get_service(db, tenant_id)` 第二参数必须是 `int`
- 新增手写 Model 后，记得注册到 `models/__init__.py` 和 `migrations/env.py`
- 启动时会自动 `upgrade`，但开发改库仍要生成迁移文件

优先读取：

- [references/backend-crud.md](references/backend-crud.md)
- [references/backend-spec.md](references/backend-spec.md)
- [references/ai-table-policy-spec.md](references/ai-table-policy-spec.md)
- [../database-migration-best-practices/SKILL.md](../database-migration-best-practices/SKILL.md)

## 前端 CRUD

模式选择：

- 数据密集型列表优先 `useCrudPage`
- 卡片、分栏、配置面板优先 `useCrudList`
- 表单抽屉优先 `useCrudDrawer`

关键要点：

- 页面分层固定为 `views -> composables -> api/store -> utils`
- 搜索和表单 schema 优先使用辅助函数，不要手写重复结构
- scope 相关字段统一走 `useScopeFields()` / `getScopeOptions()` / `ScopeSelect`
- 企业端“是否可编辑”看 `tenant_id` 或 `owner_tenant_id`，不要用 `scope` 推断
- `requestClient` 统一从 `#/utils/request` 导入
- 权限按钮统一用 `v-access:code`

优先读取：

- [references/frontend-crud.md](references/frontend-crud.md)
- [references/frontend-spec.md](references/frontend-spec.md)
- [references/icon-spec.md](references/icon-spec.md)

## AI 模块

核心原则：

- 所有 AI 功能必须走 `Agent -> Skill -> AIGateway`，不要在业务链路直接调用 AIGateway
- Executor 注册不等于功能可用；必须同时有 `SkillPackage + Skill + AgentSkillGrant`
- 知识库运行时配置中心是 `Agent.rag_config`，不是旧的 KB 单表字段
- 页面感知遵循三层结构：prompt 注入、`get_page_context`、`invoke_page_operation`
- 高频页面操作优先展开为 `pageop_*` 专用工具，而不是一律回退通用调用
- 页面操作必须校验 `page_key`，写操作必须走确认流
- 改配额/限速后，必须做真实运行时拦截验证，而不是只看 CRUD 回显
- AI 配额/限速页必须同步覆盖 `admin` 与 `tenant` 两端；不要只改 `/admin/ai/quotas`
- 企业端配额页默认是只读诊断/查看页：重点核对配额规则、速率限制、模型筛选、运行态与生效值展示；不要默认加创建/编辑/删除入口
- 企业端速率限制接口路径固定为 `/tenant/ai/quotas/rate-limits`，不要误写成 `/tenant/ai/rate-limits`
- 企业端若需要“全部 / 启用 / 停用”筛选，后端列表接口必须支持 `is_active` 查询；详情页计算使用量时必须基于当前记录本身，不能按 `tenant + model + period` 重新回查“最新规则”

优先读取：

- [references/ai-module.md](references/ai-module.md)
- [references/ai-routing.md](references/ai-routing.md)
- [references/ai-writing-spec.md](references/ai-writing-spec.md)
- [references/session-memory-spec.md](references/session-memory-spec.md)
- [references/page-awareness-spec.md](references/page-awareness-spec.md)
- [references/multimodal-model-usage.md](references/multimodal-model-usage.md)
- [references/multimodal-rag.md](references/multimodal-rag.md)

## 异步任务、WebSocket 与可观测性

关键要点：

- 业务 Celery 任务优先用 `@register_task`
- Worker 内优先通过 `BaseTask` / `TenantTask` 获取同步会话
- 主要队列包括 `default`、`high_priority`、`ai_gateway`、`scheduled`、`notification`
- 业务可运维定时任务优先落 `periodic_tasks`，系统兜底任务才写静态 `beat_schedule`
- 当前主干可观测性以日志、trace_id、AI 健康和 WebSocket presence 为主
- 不要假设仓库存在统一 `app/core/metrics.py`

优先读取：

- [references/async-tasks.md](references/async-tasks.md)
- [references/monitoring-spec.md](references/monitoring-spec.md)
- [references/trace-id-logging-spec.md](references/trace-id-logging-spec.md)
- [../websocket-guide/SKILL.md](../websocket-guide/SKILL.md)

## 鉴权、权限与用户端

关键要点：

- 三端鉴权主体分别是 `ActiveAdmin`、`ActiveTenantAdmin`、`ActiveTenantUser`
- 公开接口用 `@public`，仅登录后可访问的公开路由用 `@auth_only`
- `@permission_resource` 必须声明 `parent_resource`
- 新 Controller action 翻译写入现有 `messages.json` 的 `"action"` 节点内部
- 前端新增菜单页时，同时检查动态菜单和静态路由是否完整
- 用户端是独立架构：`/api/user/*`、`UserLayout`、响应式优先、共享 `/auth/*`
- 注册、登录、忘记密码、验证码等公开敏感入口必须经过 `IPRateLimiter`

优先读取：

- [references/rbac-permission-spec.md](references/rbac-permission-spec.md)
- [references/user-endpoint-spec.md](references/user-endpoint-spec.md)
- [references/public-config-branding-captcha.md](references/public-config-branding-captcha.md)
- [references/token-force-logout-spec.md](references/token-force-logout-spec.md)
- [references/tenant-domain-isolation.md](references/tenant-domain-isolation.md)

## 偏好、通知与审计

关键要点：

- 偏好设置使用三层模型：系统默认、全局偏好、个人覆盖
- 全局偏好页优先复用 `useGlobalPreferencePage`
- AI 工具执行和页面操作统一写 `AIActionLog`
- 通知系统与通知偏好有独立约束，不要把通知设置散落到业务模块里

优先读取：

- [references/preferences-spec.md](references/preferences-spec.md)
- [references/notification-spec.md](references/notification-spec.md)
- [references/notification-preference-spec.md](references/notification-preference-spec.md)
- [references/ai-action-log-spec.md](references/ai-action-log-spec.md)

## Codegen、迁移与插件

关键要点：

- 管理端 codegen UI 是 `/admin/system/codegen` + `/admin/system/codegen/new|:id/edit` 的三栏 Builder
- CLI 统一从 `novusai` 入口进入，不要再假设旧的散命令
- 代码生成器负责大量自动注册，但手写改动仍需人工核对路由、模型导出、i18n 与迁移
- Alembic 迁移要避免匿名外键、字符串拼 SQL、未参数化 `text(f\"...\")`
- 插件是零侵入架构；宿主只保留 loader/runtime/permission 桥接，插件业务逻辑留在插件目录

优先读取：

- [references/cli-spec.md](references/cli-spec.md)
- [references/codegen-spec.md](references/codegen-spec.md)
- [references/codegen-builder-spec.md](references/codegen-builder-spec.md)
- [../database-migration-best-practices/SKILL.md](../database-migration-best-practices/SKILL.md)
- [../plugin-development/SKILL.md](../plugin-development/SKILL.md)
- [references/plugin-spec.md](references/plugin-spec.md)

## 验证与交付

提交前至少确认：

- 改动已经落在正确分层，而不是把业务判断挤进 Controller 或页面组件
- i18n、权限、菜单、trace_id、下载上传、迁移、测试没有遗漏
- 请求失败路径没有绕开统一错误处理与 trace_id 展示
- 真实页面或接口路径至少回归一次，而不是只靠静态阅读

优先读取：

- [references/delivery-checklist.md](references/delivery-checklist.md)
- [references/browser-testing-spec.md](references/browser-testing-spec.md)
- [references/testing-spec.md](references/testing-spec.md)

## 高频 References

基础设施：

- [references/platform-infrastructure.md](references/platform-infrastructure.md)
- [references/backend-spec.md](references/backend-spec.md)
- [references/frontend-spec.md](references/frontend-spec.md)
- [references/trace-id-logging-spec.md](references/trace-id-logging-spec.md)

AI：

- [references/ai-module.md](references/ai-module.md)
- [references/ai-table-policy-spec.md](references/ai-table-policy-spec.md)
- [references/page-awareness-spec.md](references/page-awareness-spec.md)
- [references/session-memory-spec.md](references/session-memory-spec.md)

治理与业务：

- [references/rbac-permission-spec.md](references/rbac-permission-spec.md)
- [references/preferences-spec.md](references/preferences-spec.md)
- [references/user-endpoint-spec.md](references/user-endpoint-spec.md)
- [references/codegen-spec.md](references/codegen-spec.md)
