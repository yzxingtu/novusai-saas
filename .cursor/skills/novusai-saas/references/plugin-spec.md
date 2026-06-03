# 插件系统开发规范（2026-03-22 整改后）

## 1. 目录结构

```text
backend/plugins/{plugin-name}/
├── plugin.yaml
├── README.md
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   ├── skills/
│   ├── executors/
│   └── migrations/versions/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── index.ts
│   │   └── *.vue
│   └── dist/
│       └── plugin.manifest.json
└── locales/
    ├── zh-CN.json
    └── en.json
```

## 2. 核心原则

- 插件源码只能在插件目录内，宿主前端不得承载插件业务源码。
- `plugin.yaml` 是声明层单一事实来源。
- 数据库中的 `plugins.manifest` 是投影，不是开发主来源。
- 当前只支持 `admin` / `tenant` 前端端别，不支持 `user` 端插件。

## 3. License 与运行时

- License 类型只允许：
  - `trial`
  - `fixed_term`
  - `perpetual`
- 运行时授权 gate 必须覆盖：
  - 启用
  - 启动恢复
  - API / webhook 分发
  - `/plugin-assets`
  - 前端 slots / 页面
- 授权控制的是“宿主是否允许运行插件能力”，不是“源码是否绝对不可见”。

## 4. manifest 关键字段

### 4.1 顶层字段

```yaml
name: my-plugin
version: "1.0.0"
display_name:
  zh-CN: "我的插件"
  en: "My Plugin"
description:
  zh-CN: "插件描述"
  en: "Plugin description"
author: "NovusAI"
scope: admin_only
capabilities: []
dependencies:
  python:
    - "httpx>=0.27,<1"
  plugins:
    - plugin: storage-base
      version: ">=1.2.0"
pricing:
  type: free
```

顶层 `scope` 必须使用资源作用域语义，如：
- `admin_only`
- `all_tenants`
- `admin_and_selected_tenants`
- `selected_tenants`

顶层 `icon` 规则：

- 只允许 `icon.png` 或空字符串
- 根目录存在 `icon.png` 时可由加载器自动补齐
- 未提供 `icon.png` 时，宿主管理端固定回退 `lucide:plug`
- 禁止写成任意 Iconify 前缀、URL、SVG 路径或其它文件名

### 4.2 依赖声明

规则：

- Python 依赖运行在共享宿主环境：
  - `install / upgrade / repair / dependencies/install` 可以处理安装
  - `enable` 会在预检通过后按需补装缺失依赖
  - `startup restore` 只校验，不自动 `pip install`
- 插件间依赖只允许 `dependencies.plugins`：
  - 推荐对象写法：`{ plugin, version }`
  - 无版本约束时允许字符串简写
- 新 manifest/schema 直接拒绝：
  - `compatibility.requires`
  - `dependencies.system`
- 运行时仅对历史数据库里的旧 `manifest` 投影保留兼容读取，用于迁移和回放；不得继续写入 `plugin.yaml` 或脚手架模板。
- 共享环境下必须先做 Python requirement 冲突预检，避免插件静默覆盖宿主或其他插件依赖。

### 4.3 前端声明

```yaml
extensions:
  frontend:
    pages:
      - name: my_admin_home
        path: /admin/plugins/my-plugin
        component: MyPluginPage
        scope: admin
        icon: lucide:puzzle
        title:
          zh-CN: "我的插件"
          en: "My Plugin"
        menu:
          parent: system_mgmt
          sort_order: 90
          icon: lucide:puzzle
          title:
            zh-CN: "我的插件"
            en: "My Plugin"
    header_widgets: []
    floating_panels: []
    dashboard_widgets: []
    settings_tabs: []
    notification_ui: []
    dev:
      entry: src/index.ts
    release:
      manifest: plugin.manifest.json
```

规则：
- 页面路由、组件名、标题只在 `pages[*]` 声明一次。
- `pages[*].menu` 表示该页面派生为菜单入口。
- `pages[*].scope` 只允许 `admin` 或 `tenant`。
- `pages[*].icon` 与 `pages[*].menu.icon` 默认只写 `lucide:*`，并且必须命中宿主本地已注册图标。
- 如声明 `dashboard_widgets`，插件前端入口必须导出对应组件；宿主 dashboard 只负责插槽挂载，不承载插件业务源码。
- `pages[*].path` 必须与 scope 前缀一致：
  - `admin` -> `/admin/plugins/...`
  - `tenant` -> `/tenant/plugins/...`

禁止再使用：
- `frontend.menus`
- `frontend.standalone_pages`
- `frontend.admin.entry`
- `frontend.tenant.entry`
- `frontend.npm_dependencies`

## 5. 前端运行契约

### 5.1 开发态

- 宿主通过 `/__plugin_dev__/{plugin}/entry` 加载源码入口。
- Vite dev loader 从 `plugin.yaml -> extensions.frontend.dev.entry` 解析真实源码入口，默认 `src/index.ts`。
- 用于本地开发与 HMR，不走 `/plugin-assets/{plugin}/index.js` 伪生产路径。

### 5.2 生产态

- `/plugins/slots` 返回的每个前端 slot 都应附带同一份 `frontend_runtime` 投影：
  - `dev_entry`
  - `release_manifest`
- 宿主先读取 `/plugin-assets/{plugin}/{frontend_runtime.release_manifest}`；
  未提供时默认回退 `plugin.manifest.json`。
- 再按照 manifest 的 `entry` / `css` / `assets` 加载产物。

`frontend/dist/plugin.manifest.json` 示例：

```json
{
  "format": "novus.plugin.release.v1",
  "entry": "plugin.js",
  "global_var": "NovusPlugin_my_plugin",
  "css": ["assets/plugin.css"],
  "assets": []
}
```

规则：
- 生产环境前端插件缺失 release manifest 或缺失 manifest 指向的文件时，安装/启用/启动恢复都必须拒绝。
- `dist/index.js` 可以存在，但不再是唯一契约。

## 6. `/plugin-assets` 访问规则

- `/plugin-assets` 只承载运行时 release 资产，不再承担管理态元数据图标展示职责。
- 管理态图片图标必须走 `/plugin-icons/{plugin}/{file}`：
  - 仅管理端可访问
  - 不要求插件处于 enabled
  - 不受 license 运行闸门阻断
- 插件元数据图标资产只允许根目录 `icon.png`，`/plugin-icons` 不暴露任意其它根目录文件。
- `/plugin-assets` 中的 `plugin.manifest.json`、JS、CSS、运行时图片等静态资源全部受控。
- 受控插件资产必须携带运行时鉴权：
  - `Authorization: Bearer ...`
  - 或同源鉴权 Cookie（宿主前端同步 access token 到插件资产专用 Cookie）
- 访问判定同时受以下约束：
  - enabled
  - scope
  - tenant assignment
  - license
- 缓存语义必须为 `private`（并配合 `Vary: Authorization, Cookie`），禁止返回 `public` 缓存。

## 7. 启动与升级

- `discover` 只发现新插件与标记 `sync_required` / `upgrade_required`。
- `discover` 还应清理已消失的历史漂移/旧 scope 造成的 stale error，避免正式插件长期卡在过期错误状态。
- `sync-manifest` 只允许同步同版本 manifest 漂移。
- 版本变化必须走正式 `upgrade`。
- 启动恢复不再处理前端 npm 依赖，也不再自动补装 Python 依赖；仅执行依赖校验与恢复注册。
- 启动恢复对单插件迁移失败采用 fail-close：
  - 当前插件标记 `ERROR`
  - 当前插件不注册扩展
  - 不影响其它插件继续恢复

## 8. CLI

使用：

```bash
novusai plugin create my-plugin --template=minimal
novusai plugin create my-plugin --template=skill
novusai plugin create my-plugin --template=full-module
novusai plugin build backend/plugins/my-plugin
novusai plugin validate backend/plugins/my-plugin
novusai plugin pack backend/plugins/my-plugin --release
novusai plugin pack backend/plugins/my-plugin --source
```

规则：
- `create --template minimal` 默认生成 `icon: ""`，保证最小模板能直接通过 manifest 校验
- `build` 负责生成/刷新 `frontend/dist/plugin.manifest.json`
- `validate` 校验新 manifest schema、dev contract、release contract、以及旧字段遗留
- `pack --release` 排除 `frontend/src`、前端测试、`frontend/package.json` / `vite.config.*` / lockfile、`backend/tests`
- `pack --source` 保留源码链路

## 9. 生命周期

实现 `PluginBase` 时至少关注：
- `on_install`
- `on_enable`
- `on_disable`
- `on_uninstall`
- `on_upgrade`

禁止在生命周期里绕过平台边界：
- 不得手工热同步 manifest 覆盖授权能力
- 不得在运行时自动 npm install
- 不得绕过 `PluginDbProxy` 操作未授权表

## 9-A. Skill / Capability 标准映射

- `extensions.capabilities[*]` 是插件能力声明层，负责描述工具名、输入输出 schema、授权模式等。
- `extensions.skills[*]` 是 Skill 投影层，负责把一个或多个 capability 归组到具体 Skill。
- `extensions.skills[*].capabilities[]` 必须显式引用 `extensions.capabilities[*].key`，禁止只依赖单个样例插件形成隐式约定。
- 插件启用/升级时同步的是：
  - `SkillPackage`：目录、来源、归组单元
  - `Skill`：可解析执行的能力单元
- 插件启用**不等于**自动把 SkillPackage 绑定到 Agent 运行时；Agent 运行时是否获得能力，仍由直接 Skill 授权链路决定。

## 10. 历史插件处置

- 正式插件必须迁到新模型。
- 历史/备份插件至少要迁到当前 schema，并保持可作为 validate 基线。
- `novusdoc-pro` 当前仓库无正式源码，按归档样例处理，不再作为现行实现依据。
