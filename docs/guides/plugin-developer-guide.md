# NovusAI 插件开发者指南

## 一、开发者注册

1. Fork 索引仓库 `novusai/plugin-marketplace`
2. 创建 `developers/{your-name}.json`：

```json
{
  "name": "your-name",
  "display_name": "Your Name",
  "email": "dev@example.com",
  "url": "https://github.com/your-name",
  "verified": false
}
```

3. 提交 PR → NovusAI 审核通过后 `verified: true`

## 二、插件开发

### 快速创建

```bash
novusai plugin create my-plugin --template=skill
```

脚手架默认输出到 `backend/plugins/my-plugin/`，后续 `build / validate / pack` 也统一针对这个目录执行。

三种模板：
- **minimal**: 最简插件（plugin.yaml + main.py）
- **skill**: 技能插件（含 resolver + executor 示例）
- **full-module**: 完整业务插件（含 DB/API/前端/i18n）

### 目录结构

```
backend/plugins/my-plugin/
├── plugin.yaml              # 清单文件（必须）
├── README.md                # 说明文档
├── backend/
│   ├── main.py              # 入口（PluginBase 子类，必须）
│   ├── skills/              # 技能解析器
│   ├── executors/            # 工具执行器
│   ├── api/                  # 自定义 API
│   └── migrations/versions/  # Alembic 迁移
├── frontend/
│   ├── src/                  # 前端源码与 dev.entry
│   ├── dist/                 # 前端发布产物与 plugin.manifest.json
│   ├── package.json          # 本地构建依赖（必须包含 vue）
│   └── vite.config.ts        # 前端构建配置
└── locales/
    ├── zh-CN.json            # 中文翻译
    └── en.json               # 英文翻译
```

### plugin.yaml 规范

```yaml
name: my-plugin                    # 小写 kebab-case，全局唯一
version: "1.0.0"                   # semver
display_name:
  zh-CN: "我的插件"
  en: "My Plugin"
scope: all_tenants                 # ResourceScopeEnum: global_shared|admin_only|all_tenants|admin_and_selected_tenants|selected_tenants
capabilities:                      # 需要的能力
  - db:own_tables
  - http:outbound
extensions:
  skills: [...]                    # 技能扩展
  hooks: [...]                     # 钩子扩展
  webhooks: [...]                  # Webhook 端点
  events: [...]                    # EventBus 订阅
  api: { admin_routes: [...], tenant_routes: [...], public_routes: [...] }  # API 路由
  frontend:
    pages: [...]                   # 页面与菜单声明
    dev: { entry: "src/index.ts" } # 开发态入口
    release: { manifest: "plugin.manifest.json" } # 发布态契约
```

补充约束：
- 插件 AI/技能在 manifest 中当前只以 `extensions.skills[*]` 为正式契约；不要再写 `extensions.capabilities[*]`、`extensions.skills[*].capabilities[]`、`skill_md_path` 这类当前 schema 不消费的字段。
- 如声明 `extensions.frontend.dashboard_widgets[*]`，插件前端入口必须导出对应组件，宿主 dashboard 只负责插槽挂载。
- 只要插件声明了 `extensions.frontend`，或声明了依赖前端入口的 `custom.type=captcha_provider`，都必须提供 `frontend/package.json`、`vite.config.ts`、`extensions.frontend.dev.entry` 与 `extensions.frontend.release.manifest`；`novusai plugin validate` 会按前端插件完整校验。
- `extensions.frontend.*.component` 里声明的组件名，必须由 `frontend` 入口文件显式导出，否则宿主能拿到 manifest 但无法真正挂载页面或小部件。
- 插件页面标题与菜单标题分别来自 `extensions.frontend.pages[*].title` 和 `pages[*].menu.title`；页面内部按钮、提示、表单文案才走 `registerLocale(locale, 'plugin.{manifest-name}', messages)`。
- `pages[*].title` 与 `pages[*].menu.title` 必须同时覆盖 `zh-CN` / `en`；`novusai plugin validate` 会直接拦截缺失语言。
- 前端 locale 必须注册根 canonical prefix `plugin.{manifest-name}`（例如 `plugin.my-plugin`）；`plugin.{manifest-name}.admin` 等子前缀只能作为补充命名空间，不能替代根前缀。
- `.vue` 文件禁止 `<style scoped>`；插件样式必须用根类名前缀隔离，避免和宿主样式系统冲突。
- `plugin-extensions` / runtime-only 前端扩展当前不是正式 manifest 契约；发布插件只应依赖 `pages + slots + captcha` 这条宿主已落地的声明链。

### 前端运行态稳定性

- **统一初始化入口**：所有页面、路由、slot 的注册必须通过宿主提供的 `usePluginFrontendInit`/`ensurePluginRoutes`/`refreshPluginSlots` 组合完成；插件不得在多处重复注入路由或直接操作 router，以免并行调用造成 `_pluginRoutesReady` 竞争。
- **原子刷新**：`/plugins/slots` 的刷新逻辑在数据确认有效前不会清空旧状态。插件提供的 `frontend_runtime`、component 与 release manifest 必须一次性可用，否则宿主会拒绝替换并保留旧插槽，避免菜单/页面临时空白。
- **显式 endpoint + `publicEndpoint`**：前端 loader 读取 `slots/pages[*].frontend_runtime`，配合传入的 `publicEndpoint` 构建 `/plugin-assets` 请求；不要依赖 `window.location` 自动推断 endpoint。插件必须为 admin/tenant 分发各自的 release manifest 与 assets，并确保 manifest 中的 `entry`/`assets`/`css` 路径都在 `/plugin-assets/{plugin}/` 内。
- **`setup()` 失败不得缓存**：`loadPluginComponents` 只有在 `setup()` 成功后才算真正加载成功；出现异常时宿主会清除模块缓存并允许下一次重试。插件在 `setup()` 中应捕获自身可控异常，保证抛出明确错误并且不会吞掉堆栈。
- **菜单≠页面**：`extensions.frontend.pages[*].menu` 只控制菜单 metadata（title/icon/parent/accessCodes），真正的路由/组件由 `pages[*].path`+`component` 形成。manifest 必须在 `pages[*]` 同时提供路由与菜单，并保证 `menu.accessCodes` 与 guard 所需的权限码一致，以实现“可见 → 可进 → 可执行”的三层门控。
- **只在必要时重载资产**：`refreshPluginSlots({ reloadAssets: true })` 只用于 enable/disable/uninstall/repair 之后重新装载插件 bundle；语言切换、菜单重建、端切换后的重新挂载应使用 `reloadAssets: false`，只刷新标题与 route 元数据，避免无意义地卸载/重载 JS/CSS。

### 命名规范

- **DB 表**: `px_{name}_*`（如 `px_my_plugin_customers`）
- **registerLocale Prefix**: 必须包含根前缀 `plugin.{manifest-name}`；可额外扩展 `plugin.{manifest-name}.admin` 等子命名空间
- **locale bundle keys**: 使用相对 key（如 `title`、`form.submit`），不要在消息对象里重复写完整 `plugin.{manifest-name}.*`
- **API 路径**: `/admin/plugins/{name}/api/*` 或 `/tenant/plugins/{name}/api/*`
- **前端菜单/页面路径**: 必须以 `/admin/plugins/` 或 `/tenant/plugins/` 开头

### PluginBase 生命周期

```python
from app.plugins.base import PluginBase

class MyPlugin(PluginBase):
    async def on_install(self, ctx):   pass  # 首次安装
    async def on_enable(self, ctx):    pass  # 启用
    async def on_disable(self, ctx):   pass  # 禁用
    async def on_uninstall(self, ctx): pass  # 卸载前
    async def on_upgrade(self, ctx, old_version): pass  # 升级后
```

### PluginContext API

```python
config = await ctx.get_config()                         # 读取配置（自动解密敏感字段）
tenant_config = await ctx.get_tenant_config(tenant_id) # 读取企业配置
await ctx.update_config(config)                         # 更新配置（需 config:write）
db = ctx.get_db()                                       # 获取 DB 代理（需 db:own_tables）
logger = ctx.get_logger()                               # 获取专属 Logger
storage = await ctx.get_storage()                       # 获取存储代理（限 plugins/{name}/）
resp = await ctx.http_request(method, url)              # 发送 HTTP（需 http:outbound）
text = await ctx.call_ai_feature(code, messages)        # 调用 AI（需 ai:call）
license_info = await ctx.get_own_license_status()       # 读取当前插件 license 状态
await ctx.send_notification(tid, uids, code)            # 发送通知（需 notifications:send）
await ctx.emit_event(name, data)                        # 触发自定义事件
```

### Handler 加载机制

插件的所有模块（skills、executors、api handlers 等）通过统一加载器 `app/plugins/module_loader.py` 加载。

**entry_point / handler 语义（按扩展类型区分）**

- `extensions.skills[*].entry_point`：resolver 模块路径（相对于 `backend/`），例如 `skills.weather_resolver`；运行时会调用该模块的 `resolve`。
- API route / webhook / task 的 `handler` 或 `entry_point`：函数级 dotted path（相对于 `backend/`），例如 `api.admin.run_job`。

```yaml
# plugin.yaml 示例
extensions:
  skills:
    - name: weather
      type: toolkit
      entry_point: "skills.weather_resolver"   # → backend/skills/weather_resolver.py
```

注意：skill 的 `entry_point` 不要写成 `skills.weather_resolver.resolve`，否则会出现双重拼接导致加载失败。

**加载优先级**:
1. 子模块加载（推荐）: `skills/weather_resolver.py` 中的 `resolve` 函数
2. main.py fallback: `main.py` 模块的 getattr 链

**module_name 统一格式**: `plugins.{plugin_name}.backend.{dotted_path}`

### API Handler 参数注入规范（严格模式）

插件 API handler 推荐签名：

```python
async def my_handler(request, ctx):
    ...

async def my_db_handler(request, db, ctx):
    ...
```

- `request`：按签名注入 FastAPI Request
- `ctx`：按签名注入 PluginContext
- `db`：仅当插件已授予 `db:own_tables` 时才会注入 `PluginDbProxy`
- `db` 不再是原始 `AsyncSession`，禁止依赖 `db.session`

### API Handler 错误返回规范

API handler 返回错误时，**必须**在 dict 中包含 `error` 字段：

```python
# ✅ 正确 — dispatcher 自动转为 HTTP 422
async def handle_current(**kwargs):
    if not valid:
        return {"error": "Invalid parameter", "code": 4001, "status_code": 422}
    return {"temperature": 20}

# ✅ 也可以直接返回 JSONResponse
from fastapi.responses import JSONResponse
async def handle_current(**kwargs):
    if not valid:
        return JSONResponse(status_code=422, content={"code": 4001, "message": "Invalid"})
    return {"temperature": 20}

# ❌ 错误 — 不要在正常 dict 中包含 error 字段
return {"data": result, "error": None}  # error key 存在会被误判为错误
```

### SkillPackage / Skill 目录同步

插件启用或升级时，系统会同步：
1. 创建或更新 `SkillPackage`（目录、来源、归组单元，`source_plugin=插件名`）
2. 为每个 `extensions.skills[*]` 创建或更新 `Skill` 记录
3. `Skill` 的工具能力以 `entry_point` 指向的 resolver/executor 实现为准，不再通过额外的 `extensions.capabilities[*]` overlay 做二次声明

当前边界：
- `skill_md_path` 不是现行 manifest schema 字段；如需给插件技能附带说明文档，可把 `SKILL.md` 放在插件目录中，但不要再写入 `plugin.yaml`
- 如插件需要声明宿主运行能力，继续使用顶层 `capabilities`（如 `http:outbound`、`db:own_tables`），不要混入不存在的扩展层 capability schema

重要边界：
- 这里同步的是**目录投影**，不是“自动把整包绑定到 Agent 运行时”。
- Agent 运行时是否获得某个插件技能，真相仍是 `AgentSkillGrant` 驱动的直接 Skill 授权链路，而不是 SkillPackage auto-bind。
- 禁用时 Skill 会失活；卸载时相关目录投影和插件资产会被清理。

### 调试指南

**检查扩展注册状态**:
```python
from app.plugins.registry import ExtensionRegistry
registry = ExtensionRegistry.get_instance()
count = registry.get_registered_count("my-plugin")
# 期望 > 0，如果为 0 说明 handler 加载失败
```

**检查模块缓存**:
```python
import sys
plugin_modules = [k for k in sys.modules if k.startswith("plugins.my-plugin")]
# 查看已加载的模块列表
```

**常见问题**:
- `0 extensions` → 检查 `entry_point` 路径是否正确，文件是否存在
- `handler None` → 检查函数名拼写，确保模块无导入错误
- 服务重启 → 确保使用 `python -m app.main`（内置 `reload_dirs=["app"]`）或 `uvicorn app.main:app --reload --reload-dir app`

## 三、校验与打包

```bash
# 校验
novusai plugin validate backend/plugins/my-plugin

# 构建前端发布产物（会执行插件自己的 npm/pnpm/yarn build 脚本）
novusai plugin build backend/plugins/my-plugin

# 打包发布包（用于安装/分发）
novusai plugin pack backend/plugins/my-plugin --release

# 打包源码包（用于源码交付或二次开发）
novusai plugin pack backend/plugins/my-plugin --source
```

安全边界：
- `novusai plugin build` 会直接执行插件仓库中的第三方构建脚本。仅对可信源码运行；第三方插件先做安全扫描和人工审阅。
- 推荐发布前流程：`validate -> build -> pack --release`。

## 四、发布到市场

1. 创建 GitHub Release，上传 .zip
2. Fork `novusai/plugin-marketplace`
3. 添加到 `registry.json`
4. 创建 `plugins/{slug}.json`
5. 提交 PR → CI 自动检查 + 人工审核

## 五、付费插件

- 定价在 `plugin.yaml` 的 `pricing` 字段声明
- License Key 由 NovusAI 平台生成（Ed25519 签名）
- 用户激活后本地验证，无需联网
- 试用期与授权周期以当前平台 License 策略为准（不要在插件文档中硬编码固定天数）。
