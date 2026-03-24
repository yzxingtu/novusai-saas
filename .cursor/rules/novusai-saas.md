# NovusAI SaaS 开发规则

本文件是 `.cursor/rules` 的总纲入口，不是完整手册。
需要细节时，优先跳转到对应专题规则或 `.cursor/skills/novusai-saas/references/` 下的 reference。

## 项目定位

- 多企业 SaaS 平台
- 前端：Vue 3 + Vben Admin 5.x + Ant Design Vue
- 后端：FastAPI + SQLAlchemy 2.x + PostgreSQL
- 三端分离：`admin` / `tenant` / `user`

## 规则入口

专题规则：

- [ai-architecture.md](ai-architecture.md): AI / Agent / Skill / 页面操作
- [attachments-and-storage.md](attachments-and-storage.md): 上传、下载、附件可见性、存储驱动
- [async-notification-websocket.md](async-notification-websocket.md): Celery、通知、邮件、Socket.IO
- [plugin-system.md](plugin-system.md): 插件 manifest、生命周期、权限同步、菜单注册
- [rbac-and-data-permission.md](rbac-and-data-permission.md): `parent_resource`、`messages.json`、数据权限
- [user-endpoint-and-domain-isolation.md](user-endpoint-and-domain-isolation.md): `/api/user/*`、UserLayout、域名隔离
- [testing-validation.md](testing-validation.md): 后端单元测试、浏览器验证
- [alembic-migration-authoring.md](alembic-migration-authoring.md): Alembic 迁移写法
- [trace-and-monitoring.md](trace-and-monitoring.md): `X-Trace-ID`、日志、监控
- [tenant-architecture.md](tenant-architecture.md): 企业端能力边界
- [menu-i18n.md](menu-i18n.md): 动态菜单与多语言边界

常用 reference：

- [../skills/novusai-saas/references/backend-spec.md](../skills/novusai-saas/references/backend-spec.md)
- [../skills/novusai-saas/references/frontend-spec.md](../skills/novusai-saas/references/frontend-spec.md)
- [../skills/novusai-saas/references/backend-crud.md](../skills/novusai-saas/references/backend-crud.md)
- [../skills/novusai-saas/references/frontend-crud.md](../skills/novusai-saas/references/frontend-crud.md)
- [../skills/novusai-saas/references/trace-id-logging-spec.md](../skills/novusai-saas/references/trace-id-logging-spec.md)
- [../skills/novusai-saas/references/icon-spec.md](../skills/novusai-saas/references/icon-spec.md)
- [../skills/novusai-saas/references/delivery-checklist.md](../skills/novusai-saas/references/delivery-checklist.md)

## 全局硬约束

- 禁止硬编码用户可见文本，前端走 `$t()`，后端走 `_()`
- 禁止 `console.log`
- 禁止业务代码滥用 `any`
- 禁止魔法字符串，优先枚举或常量
- 禁止跨端导入
- 禁止 Controller 写业务逻辑或直接查库
- 禁止 Service 直接承担 Repository 职责
- 禁止裸返回，后端统一走响应封装
- 禁止 `except Exception: pass/continue`
- 禁止未净化的 `v-html`
- 禁止迁移里 `text(f"...")` 拼接 SQL
- 禁止日志继续使用 `%s` / `%d`
- 禁止把插件业务代码写进宿主主系统

## 注释与备注

- 新增 `#`、`//`、`/* */`、docstring、`TODO`、`FIXME` 等注释时，必须中英双语同时存在
- 若没有必要，优先不加注释
- 详细规范看：
  - [../skills/novusai-saas/references/frontend-spec.md#注释与备注规范](../skills/novusai-saas/references/frontend-spec.md#注释与备注规范)
  - [../skills/novusai-saas/references/backend-spec.md#代码注释与文档字符串](../skills/novusai-saas/references/backend-spec.md#代码注释与文档字符串)

## 前端规则

- 分层固定为 `views -> composables -> store/api -> utils`
- 表格 CRUD 优先 `useCrudPage`
- 卡片、分栏、配置面板优先 `useCrudList`
- 表单优先 `useCrudDrawer`
- 搜索和表单 schema 优先用辅助函数，不手写重复结构
- scope 相关字段统一走 `useScopeFields()` / `getScopeOptions()` / `ScopeSelect`
- 企业端“是否可编辑”按 `tenant_id` / `owner_tenant_id` 判断，不按 `scope`
- 动态菜单标题由后端权限系统负责翻译，前端不要重复维护宿主菜单多语言
- 图标统一遵循本地图标规范，禁止依赖线上 Iconify API
- 页面 AI 操作优先复用平台 helper，不重新手写一套注册流程
- 请求错误只能有一个前端展示 owner；历史 `200 + success=false` 接口不应继续扩散为常规 HTTP 契约

详见：

- [../skills/novusai-saas/references/frontend-spec.md](../skills/novusai-saas/references/frontend-spec.md)
- [../skills/novusai-saas/references/frontend-crud.md](../skills/novusai-saas/references/frontend-crud.md)
- [../skills/novusai-saas/references/icon-spec.md](../skills/novusai-saas/references/icon-spec.md)
- [ai-architecture.md](ai-architecture.md)

## 后端规则

- 请求分层固定为 `Middleware -> Controller -> Service -> Repository -> Model/DB`
- 企业模型/仓储/服务/控制器优先复用 `TenantModel` / `TenantRepository` / `TenantService` / `TenantController`
- 平台级资源优先 `GlobalController` / `GlobalService`
- 新 Model 视情况声明 `__filterable__` / `__sortable__` / `__delete_deps__`
- 分页参数统一使用 `page[number]` / `page[size]`
- 新手写 Model 要注册到 `models/__init__.py` 和 `migrations/env.py`
- Service 写操作保护放在 `_before_create` / `_before_update` / `_before_delete`
- `TenantController.get_service(db, tenant_id)` 第二参数必须是 `int`
- 时间处理遵循统一工具与序列化规范，不混用旧写法
- 日志统一通过 `app.core.logging` 暴露的封装
- 新 CLI 子命令统一注册到 `app/cli.py`

详见：

- [../skills/novusai-saas/references/backend-spec.md](../skills/novusai-saas/references/backend-spec.md)
- [../skills/novusai-saas/references/backend-crud.md](../skills/novusai-saas/references/backend-crud.md)
- [alembic-migration-authoring.md](alembic-migration-authoring.md)

## AI 架构

- 任何业务 AI 功能必须走 `Agent -> Skill -> AIGateway`
- 禁止在 Controller / Service 直接调用 `AIGateway.chat()` / `embedding()`
- 禁止绕过 Agent-Skill 链路新增 AI 业务端点
- 已废弃的 `ToolRegistry` / `tool_bindings` 不能继续引入
- 页面感知、页面操作、会话记忆、多模型路由、多模态 RAG 都按既有架构接入

详见：

- [ai-architecture.md](ai-architecture.md)
- [../skills/novusai-saas/references/ai-routing.md](../skills/novusai-saas/references/ai-routing.md)
- [../skills/novusai-saas/references/multimodal-rag.md](../skills/novusai-saas/references/multimodal-rag.md)

## 上传、下载与存储

- 上传统一通过 `AttachmentService`
- 业务页上传统一走 `smartUploadFile` 或业务封装组件
- 文件下载统一走 `requestClient.download` + `downloadBlob`
- 展示类图片走统一公开附件图片端点
- `public` / `private` 可见性必须按真实用途区分

详见：

- [attachments-and-storage.md](attachments-and-storage.md)

## 异步任务、通知与实时通信

- 业务 Celery 任务统一使用 `@register_task`
- Worker 为同步进程，数据库会话按项目基类约定获取
- 定时任务优先使用 `periodic_tasks` 表
- 业务通知统一经 `NotificationService`
- Socket.IO namespace 固定为 `/admin` / `/tenant` / `/user`
- Celery 侧推送统一用 `sio_bridge.*_sync()`
- AI 调用日志默认通过 `log_call_async -> tasks.ai.log_ai_call -> ai_gateway` 异步落库；涉及 `billing_context` 或任务签名改动后必须重启 Worker

详见：

- [async-notification-websocket.md](async-notification-websocket.md)

## RBAC、数据权限与用户端

- `@permission_resource` 必须声明 `parent_resource`
- 新 action 翻译补到现有 `messages.json` 的 `"action"` 节点内
- 插件权限同步用 `sync_plugin_permissions(plugin.name)`
- 行级数据权限优先用 `__data_permission__ = True` 声明式开启
- 新页面要同时保证菜单注册和前端落点齐全
- 用户端前缀固定 `/api/user/*`
- 用户端布局固定 `UserLayout`
- 平台域名、企业域名、品牌与验证码都按统一域名隔离方案处理

详见：

- [rbac-and-data-permission.md](rbac-and-data-permission.md)
- [user-endpoint-and-domain-isolation.md](user-endpoint-and-domain-isolation.md)
- [tenant-architecture.md](tenant-architecture.md)
- [menu-i18n.md](menu-i18n.md)

## 测试、trace_id 与监控

- 新增或重构 Service 必须补测试
- 浏览器验证优先 `chrome-devtools`，上传流程再用 `playwright`
- 所有请求链路应自动携带 `X-Trace-ID`
- 拿到 `trace_id` 后，默认排查入口是 `novusai trace show <trace_id>`，不是人工全库翻日志
- AI 工具与页面操作审计统一写入 `AIActionLog`
- 当前主干监控以日志、trace_id、AI 健康、WebSocket presence 为主
- 若新增 Prometheus 指标，定义在所属模块旁并用 `try/except` 包裹

详见：

- [testing-validation.md](testing-validation.md)
- [trace-and-monitoring.md](trace-and-monitoring.md)
- [../skills/novusai-saas/references/monitoring-spec.md](../skills/novusai-saas/references/monitoring-spec.md)

## DevGenius 治理

- 所有开发优先基于已认领任务推进
- 文档、任务、里程碑优先通过 `devgenius-quanzhan` MCP 管理
- 写文档前先查重，禁止重复创建
- 实施完成后再同步状态，禁止假完成
- `.cursor/mcp.json` 可能为空，不要把它当成唯一事实来源

## 自动热重载

- 后端由 `uvicorn --reload` 自动热重载，代码保存后自动生效
- 前端由 Vite HMR 自动热更新，通常无需重启 dev server
- 新迁移文件写到 `migrations/versions/` 后，需要再保存任意 `app/` 内文件触发 reload
- 只有改 `.env`、安装依赖或极少数框架级启动配置时才需要重启
- AI 助手不要把“重启前后端”当默认建议

## 交付前自检

- 按任务类型补齐 i18n、权限、菜单、trace_id、测试、迁移和回归
- 不确定时直接按 [../skills/novusai-saas/references/delivery-checklist.md](../skills/novusai-saas/references/delivery-checklist.md) 逐项核对
