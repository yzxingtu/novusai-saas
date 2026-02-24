---
description: NovusAI SaaS 全栈开发技能。当需要开发前端页面（Vue 3 + Vben Admin）或后端接口（FastAPI + SQLAlchemy + PostgreSQL）时，提供分层架构、CRUD 流程、多租户、权限、国际化等项目专属规范。
---

# NovusAI SaaS 全栈开发技能

> 本文件是精简索引。每节仅保留核心要点 + 指向详细 reference 文件的链接。
> 所有 reference 文件位于 `references/` 目录。

## 技术栈

| 端 | 技术 |
|---|------|
| 前端 | Vue 3.5 + TypeScript + Vben Admin 5.x + Ant Design Vue + Vite 6.x + Tailwind CSS |
| 后端 | Python 3.11+ + FastAPI + SQLAlchemy 2.x (Async) + PostgreSQL + Alembic |
| 认证 | JWT (access / refresh / impersonate) |
| 查询协议 | JSON:API（filter/sort/page） |

## 开发前准备

1. 确认任务归属的端：admin / tenant / user
2. 查阅对应 reference 文件了解规范
3. 确认相关模块是否已有类似实现，复用已有组件和模式

---

## 一、全局禁令

以下规则在任何情况下不可违反：

- **禁止硬编码字符串**：前端 `$t()` / `t()`，后端 `_()`
- **禁止 `console.log`**：使用 `console.warn` / `console.error`
- **禁止 `any` 类型**：使用 `unknown` 或具体类型
- **禁止魔法字符串**：后端用 `LabeledEnum`，前端用常量/枚举
- **禁止跨端导入**：admin 页面不导入 tenant/user 的 API/Store
- **禁止层级越权**：Controller 不写业务逻辑，Service 不直接操作 DB，Repository 不写业务判断
- **禁止裸返回**：后端必须用 `success()` / `created()` / `paginated()` 等统一响应
- **禁止手写重复 Schema**：前端用 `searchInput()` / `inputField()` 等辅助函数
- **禁止敏感信息入代码**：密钥、密码、Token 通过环境变量
- **禁止在主系统中写入插件代码**：插件组件/逻辑/locale 只能在 `backend/plugins/{name}/` 内，前端通过 UMD 动态加载

---

## 二、平台基础设施

多租户隔离、认证注入、异常体系、日志系统、SSE 流式、应用启动、上传存储、配置系统、前端业务组件。

**核心要点**：
- 四层租户隔离：`TenantModel` → `TenantRepository` → `TenantService` → `TenantController`
- 三端 Token：`ActiveAdmin` / `ActiveTenantAdmin` / `ActiveUser`
- 异常由 Service 抛出（`NotFoundException` / `BusinessException` 等），Controller 不捕获
- 日志分类器：`LogManager.get_logger("app"/"auth"/"storage"/"task"/"queue"/"db")`
- 上传必须通过 `AttachmentService`，前端用 `FilePicker` / `ImageUpload` / `smartUploadFile`

→ 完整规范：`references/platform-infrastructure.md`

---

## 三、后端开发（CRUD 7 步）

分层架构：请求 → Middleware → Controller → Service → Repository → Model/DB

1. **Model** — 继承 `TenantModel`/`BaseModel`，声明 `__filterable__`/`__sortable__`
2. **Schema** — 继承 `BaseCreateSchema`/`BaseUpdateSchema`/`BaseResponseSchema`
3. **Repository** — 继承 `TenantRepository`/`BaseRepository`
4. **Service** — 继承 `TenantService`/`BaseService`，可重写钩子
5. **Controller** — 继承 `TenantController`/`GlobalController`，声明 `@permission_resource` + `@action_*`
6. **注册路由** — 引入 `router`
7. **生成迁移** — `alembic revision --autogenerate -m "xxx"`（启动时自动 upgrade）

**关键注意**：
- `TenantController.get_service(db, tenant_id)` — 第二参数是 `int`
- `BaseController.get_service(db)` — 只需 `db`
- 分页用 `query.size` 不是 `query.page_size`
- 新 Model 必须注册到 `models/__init__.py` 和 `migrations/env.py`

→ 完整代码示例：`references/backend-crud.md`
→ 后端开发指南：`references/backend-spec.md`

---

## 四、前端开发（CRUD 4 步）

架构分层：`views → composables → store/api → utils`（禁止反向依赖）

1. **data.ts** — 列定义 `useColumns()`、搜索 `useGridFormSchema()`、表单 `useFormSchema()`
2. **list.vue** — `useCrudPage` 组装列表
3. **form.vue** — `useCrudDrawer` 组装表单
4. **路由 + i18n** — `router/routes/{endpoint}/` + `locales/langs/zh-CN/{endpoint}/`

**关键注意**：
- 搜索/表单必须用辅助函数（`searchInput` / `inputField` 等），禁止手写
- 业务预设（planSelect 等）定义在 `data.ts`，不放 adapter
- `requestClient` 导入路径：`#/utils/request`
- 权限指令：`v-access:code="['resource:action']"`

→ 完整代码示例：`references/frontend-crud.md`
→ 前端开发手册：`references/frontend-spec.md`

---

## 五、前后端协作约定

- **过滤**：`filter[status]=active` / `filter[name][ilike]=科技`
- **排序**：`sort=-created_at,name`
- **分页**：`page[number]=1&page[size]=20`
- **错误码**：4010→跳登录，4011→刷新 Token，4030→权限不足
- **CRUD 请求**：POST 创建 / PUT 更新 / DELETE 删除 / GET 列表

---

## 六、AI 模块

**核心架构原则：所有 AI 功能必须通过 Agent → Skill → AIGateway 链路完成，禁止直接调用 AIGateway。**

- 技能包（SkillPackage）是一级管理单元，技能必须归属于某个技能包
- 技能类型：`toolkit` / `knowledge_base` / `data_intelligence` / `builtin`
- 新增 AI 功能标准流程：定义类型 → 实现 Executor → 注册映射 → 创建 Skill → 绑定 Agent

→ 完整规范：`references/ai-module.md`

---

## 七、异步任务与定时任务

- 必须用 `@register_task` 装饰器，禁止 `@celery_app.task`
- Celery Worker 是同步进程，用 `sync_session_factory()` 获取 DB，`redis.from_url()` 获取 Redis
- 4 个队列：`default` / `high_priority` / `ai_gateway` / `scheduled`
- 定时任务通过 `periodic_tasks` 表管理，禁止硬编码 `beat_schedule`

→ 完整规范：`references/async-tasks.md`

---

## 八、删除依赖保护

任何 Model 被 FK 引用时，必须声明 `__delete_deps__`。五种策略：`BLOCK` / `CASCADE_SOFT` / `CASCADE_DELETE` / `NULLIFY` / `IGNORE`。`useCrudPage` 已集成 `DependencyBlockModal`（错误码 4221）。

→ 完整规范：`references/deletion-deps.md`

---

## 九、邮件发送

所有邮件必须通过 `send_email_task.delay()` 异步发送，禁止 Controller/Service 直接调用 `EmailService.send()`。

→ 完整规范：`references/email-spec.md`

---

## 十、通知系统

所有业务通知统一走 `NotificationService.send()` → 渠道驱动（WS / Inbox / Email）。模板编码格式：`{category}.{event_name}`。

→ 完整规范：`references/notification-spec.md`

---

## 十一、WebSocket 实时通信

三端 namespace 隔离：`/admin` / `/tenant` / `/user`。后端用 `sio.emit()`，Celery 用 `sio_bridge.*_sync()`。

→ 完整指南：`websocket-guide.md`

---

## 十二、时间存储与显示

- **后端**：统一 `utc_now()`（`app.core.base_model`），禁止 `datetime.now()` / `datetime.utcnow()`
- **序列化**：ISO 8601 + `+00:00` 后缀
- **前端**：`formatDate()` / `formatRelativeTime()` 自动转本地时间

---

## 十三、数据库迁移

系统启动时自动执行 `alembic upgrade head`，开发者只需生成迁移文件。新 Model 必须注册到 `models/__init__.py` 和 `migrations/env.py`。

### 迁移文件卫生规则

1. **禁止残留垃圾迁移** — 创建种子数据（seed）迁移前，先确认该数据确实被代码引用（如 `resolve('feature_code')`）。未被引用的占位数据不要写入迁移。
2. **禁止删除链中的迁移文件** — Alembic 依赖 `revision → down_revision` 链，删除中间文件会导致 `alembic history` / `upgrade` 报错。如果迁移已失效，将其转为 **no-op**（`upgrade`/`downgrade` 改为 `pass`），并在 docstring 中标注 `[NO-OP]` 及原因。
3. **纯数据迁移要评估生命周期** — 如果插入的种子数据后续可能被删除，优先使用应用层初始化（如 `on_startup` seed 函数）而非迁移文件。迁移文件一旦写入链就无法干净移除。
4. **autogenerate 后必须检查** — `alembic revision --autogenerate` 生成的文件可能是空的（`pass`），必须检查并补充实际逻辑，或删除空文件（未执行前可删）。
5. **合并分支及时处理** — 出现多 head 时立即 `alembic merge`，不要留多个 head 长期共存。
6. **命名规范** — 文件名格式：`YYYYMMDD_<revision_id>_<description>.py`。描述用英文 snake_case，清晰表达迁移目的。

→ 完整最佳实践：`database-migration-best-practices.md`

---

## 十四、DevGenius MCP 工作流

核心流程：认领任务 → 查文档 → 开发 → 写文档 → 更新状态

→ 详细工具用法：`references/devgenius-workflow.md`

---

## 检查清单

### 后端

- [ ] Model 继承 `BaseModel` / `TenantModel`，声明 `__filterable__` / `__sortable__`
- [ ] Repository 继承 `BaseRepository` / `TenantRepository`
- [ ] Service 继承 `BaseService` / `TenantService` / `GlobalService`
- [ ] Controller 声明 `@permission_resource`，方法声明 `@action_*`
- [ ] 统一响应方法（`success` / `created` / `paginated` / `deleted`）
- [ ] 面向用户文本使用 `_()`
- [ ] 枚举使用 `LabeledEnum`
- [ ] Alembic 迁移已生成
- [ ] 新 Model 已注册到 `models/__init__.py` 和 `migrations/env.py`
- [ ] 敏感信息通过环境变量
- [ ] 时间使用 `utc_now()`

### 前端

- [ ] 无 `any` 类型
- [ ] 无 `console.log()`
- [ ] 无中文硬编码（全部 `$t()`）
- [ ] 搜索/表单用辅助函数生成
- [ ] 业务预设在 `data.ts` 定义，不在 adapter
- [ ] 无跨端导入
- [ ] i18n JSON key 无重复、路径正确
- [ ] 中英文翻译齐全
- [ ] Props 用 `defineProps<T>()`

---

## 十五、插件开发

插件系统采用**零侵入架构**：plugin.yaml 声明式清单 + PluginBase 生命周期钩子 + PluginContext 沙箱 API + UMD 前端动态加载。

**核心原则：插件代码（后端逻辑、前端组件、国际化文件）只能存在于 `backend/plugins/{name}/` 内，严禁写入主系统代码中。**

### 核心文件

| 框架文件 | 职责 |
|----------|------|
| `app/plugins/base.py` | PluginBase 抽象基类（5 个生命周期钩子） |
| `app/plugins/manifest.py` | plugin.yaml Pydantic Schema（30+ 子 Schema） |
| `app/plugins/loader.py` | 插件发现 / 清单解析 / 主类加载 / README / i18n |
| `app/plugins/lifecycle.py` | install(10 步) / enable / disable / uninstall(14 步) |
| `app/plugins/context.py` | PluginContext 沙箱 + PluginDbProxy 表前缀隔离 |
| `app/plugins/registry.py` | ExtensionRegistry 单例（9 种扩展类型注册 + 反注册） |
| `app/plugins/exceptions.py` | 7 个异常类（4230-4236 错误码） |

### 插件目录结构

```
backend/plugins/{name}/
├── plugin.yaml              # 清单（必须）
├── README.md
├── backend/
│   ├── __init__.py          # 空文件（必须）
│   ├── main.py              # PluginBase 子类（必须）
│   ├── skills/              # Skill Resolver（按需）
│   ├── executors/           # Tool Executor（按需）
│   ├── api/                 # API handler（按需）
│   └── migrations/versions/ # Alembic 迁移（按需）
├── frontend/                # 前端 UMD 包（按需）
│   ├── package.json         # 构建依赖
│   ├── vite.config.ts       # UMD 构建配置
│   ├── src/                 # Vue SFC 源码
│   │   ├── index.ts         # 入口：export 组件 + setup()
│   │   └── *.vue            # 组件文件
│   └── dist/                # 构建产物（index.js + *.css）
└── locales/                 # zh-CN.json + en.json
```

### plugin.yaml 最小模板

```yaml
name: my-plugin                    # 小写 kebab-case（正则: ^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$）
version: "1.0.0"
display_name:
  zh-CN: "我的插件"
  en: "My Plugin"
scope: all_tenants                 # admin_only|all_tenants|assigned_tenants|admin_and_all|admin_and_assigned
capabilities:
  - db:own_tables                  # 按需声明: db:own_tables / http:outbound / storage:read / storage:write / ai:call / config:write / notifications:send
extensions:
  skills: []                       # 9 种扩展点: skills/adapters/storage_drivers/api/hooks/tasks/notifications/permissions/webhooks/events/frontend
```

### config_schema（插件配置表单）

在 `plugin.yaml` 中声明 `config_schema`，前端配置抽屉会自动渲染表单。格式为简化版 JSON Schema：

```yaml
config_schema:
  type: object
  properties:
    default_city:
      type: string           # string / integer / boolean
      title: "默认城市"       # 表单标签
      description: "..."     # 说明文字（可选）
      default: "Shanghai"    # 默认值
    temperature_unit:
      type: string
      title: "温度单位"
      enum: ["celsius", "fahrenheit"]  # 枚举 → 下拉框
      default: "celsius"
    forecast_days:
      type: integer
      title: "预报天数"
      minimum: 1             # 数字最小值
      maximum: 7             # 数字最大值
      default: 3
    auto_refresh:
      type: boolean
      title: "自动刷新"
      default: true
```

**支持的字段类型：**
- `string` → 文本输入框（有 `enum` 时渲染为下拉框）
- `integer` / `number` → 数字输入框（支持 `minimum`/`maximum`）
- `boolean` → 复选框

**读取配置：** 在 handler/executor 中通过 `ctx.get_config()` 或 `config` 参数获取。

### PluginBase 生命周期

```python
from app.plugins.base import PluginBase

class MyPlugin(PluginBase):
    async def on_install(self, ctx):   ...  # 首次安装 → 初始化种子数据
    async def on_enable(self, ctx):    ...  # 启用 → 启动后台任务
    async def on_disable(self, ctx):   ...  # 禁用 → 清理后台任务
    async def on_uninstall(self, ctx): ...  # 卸载前 → 清理自定义数据
    async def on_upgrade(self, ctx, old_version): ...  # 升级后 → 数据迁移
```

### PluginContext 核心 API

```python
await ctx.get_config()                        # 读取配置（自动解密 x-encrypted 字段）
db = ctx.get_db()                             # PluginDbProxy（仅 px_{name}_* 表）→ 需 db:own_tables
storage = await ctx.get_storage()             # 命名空间限定 plugins/{name}/ → 需 storage:read|write
result = await ctx.http_request("GET", url)   # 自动 30s 超时 → 需 http:outbound
text = await ctx.call_ai_feature("ai_writer", messages)  # 查 SystemAgentAssignment → 需 ai:call
logger = ctx.get_logger()                     # Logger 名称: plugin.{name}
```

### 命名规范

| 项目 | 格式 | 示例 |
|------|------|------|
| DB 表 | `px_{name_underscored}_*` | `px_novusdoc_documents` |
| Alembic 分支 | `plugin_{name_underscored}` | `plugin_novusdoc` |
| i18n Key | `plugin.{name}.*` | `plugin.novusdoc.title` |
| API 路径 | `/admin/plugins/{name}/api/*` | `/admin/plugins/novusdoc/api/docs` |
| AI feature_code | `plugin.{name}.{code}` | `plugin.novusdoc.ai_writer` |
| 前端全局变量 | `NovusPlugin_{name_underscored}` | `NovusPlugin_novusdoc` |

### CLI 工具

```bash
# 创建插件骨架（3 种模板）
python scripts/plugin_cli.py create my-plugin --template=minimal      # 纯后端
python scripts/plugin_cli.py create my-plugin --template=skill        # + Skill/Executor
python scripts/plugin_cli.py create my-plugin --template=full-module  # + 前端骨架 + API + 迁移

# 校验（yaml + main.py + 前端 dist + scoped CSS 扫描 + 安全扫描）
python scripts/plugin_cli.py validate plugins/my-plugin

# 打包（自动排除 node_modules/__pycache__/.git）
python scripts/plugin_cli.py pack plugins/my-plugin
```

### 插件前端双模式加载

插件前端采用 **双模式加载**架构：

| 模式 | 场景 | 加载方式 |
|------|------|----------|
| **dev 模式** | `pnpm dev` 开发调试 | Vite 直接编译插件 SFC（HMR 热更新） |
| **build 内置** | `pnpm build` 生产构建 | 有源码的插件编入主 bundle（code split） |
| **UMD 动态** | 生产环境运行时安装 | `<script>` 加载 `/plugin-assets/{name}/index.js` |

**加载优先级**：`BUILTIN_PLUGINS`（Vite 编译）→ UMD `<script>` → 跳过

**dev 模式开发体验**：
1. 把插件目录放到 `backend/plugins/`
2. 启动 `pnpm dev` → Vite 自动发现并编译插件 SFC
3. 修改 `.vue` 文件 → 浏览器自动刷新（不需要 `npm install` 或 `vite build`）

**发布前编译**（仅一次）：
```bash
cd backend/plugins/my-plugin/frontend
npm install && npx vite build    # → dist/index.js (UMD)
```

**样式规范**：
- ✅ 样式放 `styles.ts`，通过 `setup()` JS 注入到 `<head>`
- ✅ CSS 类名以插件缩写前缀（如 `.wx-`、`.mp-`）
- ❌ 禁止 `<style scoped>` — Popover/Modal portal 中失效
- ❌ 禁止 `<style>` 块 — UMD 构建时提取为 CSS 文件需额外加载

**插件 SFC 导入规则**：
- `import { ref, computed } from 'vue'` — dev 模式由主项目 node_modules 解析，UMD 模式 external → `window.Vue`
- `import { Popover } from 'ant-design-vue'` — 同上，UMD → `window.AntDesignVue`
- `import { IconifyIcon, $t, requestClient } from '@novus/plugin-shared'` — dev 模式由 Vite alias 解析为 `plugin-shared.ts` 的 ES export，UMD 模式 external → `window.NovusPluginShared`
- **禁止** `import { $t } from '#/locales'` — 这是宿主路径别名，插件不可用
- **禁止** `export default` — 插件 `index.ts` 只使用命名导出（`export function setup`、`export { MyWidget }`），Vite 虚拟模块通过 `export *` 转发

**宿主 `plugin-shared.ts` 双模式支持**：
- UMD 模式：`exposePluginShared()` 将 `$t`/`IconifyIcon`/`requestClient` 等挂载到 `window.NovusPluginShared`
- dev 模式：同一文件通过 `export { $t, IconifyIcon, requestClient, usePluginSlotsStore }` 提供 ES module 导出，Vite alias `@novus/plugin-shared` 指向此文件
- **新增共享 API 时必须同时添加 `window` 挂载和 ES export**，否则 dev 或 UMD 模式之一会 break

### 可用 HookPoint（28 个）

插件可通过 `plugin.yaml` 的 `hooks` 声明注册任意钩子。BEFORE_* 可修改参数/阻止操作，AFTER_* 可修改结果。

| 分组 | 钩子点 |
|------|--------|
| 执行 | `before_execute` / `after_execute` |
| 消息 | `before_message_save` / `after_message_save` |
| 工具 | `before_tool_call` / `after_tool_call` |
| LLM | `before_llm_call` / `after_llm_call` |
| 上下文 | `before_context_build` / `after_context_build` |
| 技能解析 | `before_skill_resolve` / `after_skill_resolve` |
| 技能 CRUD | `before/after_skill_create` / `update` / `delete` |
| 智能体 CRUD | `before/after_agent_create` / `update` / `delete` |
| 对话 | `before/after_agent_chat` / `before/after_conversation_create` |
| 模型调用 | `before_model_call` / `after_model_call` |
| 知识库 | `before_kb_search` / `after_kb_search` |
| 数据智能 | `before_sql_execute` / `after_sql_execute` |

### 可用 EventBus 事件（26 个）

插件可通过 `plugin.yaml` 的 `events` 声明订阅事件（异步通知，只读不可修改）。

- **智能体**: `AgentCreated` / `AgentPublished` / `AgentDisabled` / `AgentUpdated` / `AgentDeleted`
- **技能**: `SkillCreated` / `SkillUpdated` / `SkillDeleted`
- **对话**: `ConversationStarted` / `ConversationCreated` / `MessageAdded` / `MessageCreated` / `ConversationCompleted`
- **工具**: `ToolCallRequested` / `ToolCallCompleted` / `ToolCallFailed`
- **执行**: `ExecutionStarted` / `ExecutionCompleted` / `ExecutionFailed`
- **插件**: `PluginInstalled` / `PluginEnabled` / `PluginDisabled` / `PluginUninstalled`
- **知识库**: `KnowledgeBaseUpdated` / `DocumentUploaded`
- **模型**: `ModelCallCompleted`

### 插件技能类型规范

插件声明 `extensions.skills` 时，`type` 字段**必须使用系统内置类型**，不得自定义新类型。

**内置技能类型：**

| type | 说明 |
|------|------|
| `toolkit` | Python 工具包（最常用，调用外部 API、自定义逻辑） |
| `knowledge_base` | RAG 知识库检索 |
| `data_intelligence` | Text-to-SQL 数据库查询 |
| `builtin` | 系统内置工具 |
| `http` | 声明式 HTTP API 调用 |
| `email` | 邮件发送 |
| `code_execution` | 代码沙箱执行 |

**禁止自定义类型**（如 `weather_widget`、`my_custom_type`）：
- 系统 i18n 只维护内置类型的翻译，自定义类型会显示 fallback 文本而非正式翻译
- 系统 UI 的类型颜色/图标映射只覆盖内置类型，自定义类型统一显示默认样式
- Executor 文件名查找规则 `{type}_executor.py` 对自定义类型可能无法正确匹配

**正确做法：** 绝大多数插件技能应使用 `toolkit` 类型。通过 `display_name` 和 `description` 区分具体用途，而非发明新 type。

```yaml
# ✅ 正确
extensions:
  skills:
    - name: weather-query
      type: toolkit                    # 使用内置类型
      display_name:
        zh-CN: "天气查询"
      entry_point: "skills.resolver"

# ❌ 错误
extensions:
  skills:
    - name: weather-query
      type: weather_widget             # 禁止自定义类型
```

### 关键禁令

- **禁止自定义技能类型** — 必须使用上述 7 种内置 type，通过 `display_name` 区分用途
- **禁止在主系统代码中写入插件组件/逻辑/国际化** — 插件所有代码必须在 `backend/plugins/{name}/` 内
- **禁止硬编码插件组件映射** — 不允许在宿主代码中 `import` 或 `import.meta.glob` 插件组件
- **禁止在主系统 `locales/` 中放插件翻译** — 插件 i18n 通过 `setup()` 的 `registerLocale()` 动态注册
- **禁止操作非 `px_{name}_*` 前缀的表** — PluginDbProxy 会拦截并抛出 `PluginSecurityError`
- **禁止不声明 capability 就调用受限 API** — `_require()` 检查失败抛 `PluginSecurityError`
- **禁止 `eval/exec/subprocess`** — 安全扫描 `security_scan.py` 会警告
- **禁止直接 import 其他插件内部模块** — 通过 EventBus 或公开 API 通信
- **Executor 文件名必须匹配** — `{skill_type}_executor.py`（type 中 `-` 替换为 `_`）
- **Alembic 迁移必须声明 branch_labels** — `branch_labels = ('plugin_{name_underscored}',)`

### 关键文件索引

| 宿主文件 | 职责 |
|----------|------|
| `frontend/.../utils/plugin-shared.ts` | 暴露 `window.Vue` / `NovusPluginShared` 共享依赖 |
| `frontend/.../utils/plugin-loader.ts` | UMD `<script>` 加载 + CSS 加载 + `setup()` 调用 |
| `frontend/.../composables/use-plugin-frontend-init.ts` | 获取已启用插件 → 动态加载 UMD → 注册到 slots store |
| `frontend/.../stores/plugin-slots.ts` | Pinia 插槽 Store（5 种插槽类型） |
| `frontend/.../layouts/basic.vue` | `#header-right-89` 渲染 `headerWidgets` |
| `backend/app/main.py` | `/plugin-assets/{name}/` 静态资源路由 |
| `backend/app/middleware/access_control.py` | `/plugin-assets` 在豁免路径列表中 |

→ 完整规范 + 代码示例：`references/plugin-spec.md`
→ 插件开发者指南：`docs/guides/plugin-developer-guide.md`
→ 示例插件：`backend/plugins/weather-widget/`

---

## 参考文件索引

| 文件 | 内容 |
|------|------|
| `references/platform-infrastructure.md` | 多租户/认证/异常/日志/SSE/启动/存储/配置/组件 |
| `references/backend-crud.md` | 后端 CRUD 7 步完整代码 + 响应/异常/权限/枚举/日志 |
| `references/frontend-crud.md` | 前端 CRUD 4 步完整代码 + 权限/搜索/i18n/图标/请求/命名 |
| `references/frontend-spec.md` | 前端开发手册完整版（含拖拽排序、列表 UI 设计、CSS 动画等） |
| `references/backend-spec.md` | 后端开发指南完整版（含存储、日志、枚举、Service 钩子等） |
| `references/async-tasks.md` | 异步任务与定时任务开发规范（Celery/Redis/队列/定时任务） |
| `references/devgenius-workflow.md` | DevGenius MCP 工作流详解（工具速查、流程图、文档管理） |
| `references/ai-module.md` | AI 模块开发规范（引擎/网关/工具/RAG/数据智能/事件/安全） |
| `references/email-spec.md` | 邮件发送规范（架构/触发来源/配置/规则） |
| `references/deletion-deps.md` | 删除依赖保护规范（5 种策略/声明语法/前端弹窗/回收站） |
| `references/notification-spec.md` | 通知系统规范（渠道驱动/模板编码/队列/扩展） |
| `references/plugin-spec.md` | **插件系统开发规范（manifest/生命周期/Context/扩展点/迁移/安全）** |
