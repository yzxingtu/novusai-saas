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
cd backend
novusai plugin create my-plugin --template=skill
```

三种模板：
- **minimal**: 最简插件（plugin.yaml + main.py）
- **skill**: 技能插件（含 resolver + executor 示例）
- **full-module**: 完整业务插件（含 DB/API/前端/i18n）

### 目录结构

```
my-plugin/
├── plugin.yaml              # 清单文件（必须）
├── README.md                # 说明文档
├── backend/
│   ├── main.py              # 入口（PluginBase 子类，必须）
│   ├── skills/              # 技能解析器
│   ├── executors/            # 工具执行器
│   ├── api/                  # 自定义 API
│   └── migrations/versions/  # Alembic 迁移
├── frontend/
│   └── dist/                 # 前端 UMD 包
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
scope: all_tenants                 # admin_only|all_tenants|assigned_tenants|admin_and_all|admin_and_assigned
capabilities:                      # 需要的能力
  - db:own_tables
  - http:outbound
extensions:
  skills: [...]                    # 技能扩展
  hooks: [...]                     # 钩子扩展
  webhooks: [...]                  # Webhook 端点
  events: [...]                    # EventBus 订阅
  api: { admin_routes: [...], tenant_routes: [...], public_routes: [...] }  # API 路由
```

### 命名规范

- **DB 表**: `px_{name}_*`（如 `px_my_plugin_customers`）
- **i18n Key**: `plugin.{name}.*`（如 `plugin.my-plugin.title`）
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

**entry_point 格式**: `模块路径.属性名`（相对于 `backend/` 目录）

```yaml
# plugin.yaml 示例
extensions:
  skills:
    - name: weather
      type: toolkit
      entry_point: "skills.weather_resolver"   # → backend/skills/weather_resolver.py
```

启动恢复时会调用 `entry_point + ".resolve"`，即 `skills.weather_resolver.resolve`。

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

### 技能包自动注册

插件启用时，系统自动：
1. 创建 `SkillPackage`（scope=global, source_plugin=插件名, is_system=True）
2. 为每个 skill extension 创建 `Skill` 记录
3. Agent 可通过绑定该 SkillPackage 使用插件技能

禁用时 Skill 标记为 `is_active=False`，卸载时删除记录。

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
novusai plugin validate my-plugin/

# 打包
novusai plugin pack my-plugin/
```

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
- 支持 14 天试用期
