# 图标规范（2026-03-22）

## 1. 目标

- 生产环境禁止依赖任何在线图标 API，尤其是 `api.iconify.design`。
- 平台功能图标统一收敛到 `lucide`。
- 自定义品牌/产品图标必须仓库内自托管。
- 插件元数据图标只接受 `png` 文件，不再接受任意 Iconify 前缀。

## 2. 平台图标来源

### 2.1 功能图标

- 允许：
  - `lucide:*`
  - 仓库内自托管 `svg:*`
- 禁止：
  - `mdi:*`
  - `ep:*`
  - `ant-design:*`
  - `simple-icons:*`
  - 任何依赖远端拉取集合的第三方 Iconify 前缀

规则：

- 管理端、企业端、用户端、共享组件、adapter、布局组件中的功能性图标统一使用 `lucide:*`。
- 若 Lucide 无法表达且确属品牌/产品资产，改为落库内 SVG，自定义前缀统一走 `svg:*`。
- `IconifyIcon` 仍是统一渲染组件，但图标数据源必须是本地已注册集合。

### 2.2 自定义 SVG 图标

- 自定义 SVG 放在 `frontend/packages/icons/src/svg/icons/`。
- 通过 `frontend/packages/icons/src/svg/index.ts` 注册，统一以 `svg:*` 使用。
- 优先用于：
  - 品牌 logo
  - 键盘/设备类特殊图形
  - Lucide 中不存在但平台长期稳定需要的固定图形

## 3. Lucide 子集与全量目录

- 子集生成命令：`pnpm --dir frontend run icons:generate`
- 生成产物：
  - `frontend/packages/icons/src/iconify/lucide-subset.generated.ts`
  - `frontend/packages/icons/src/iconify/lucide-catalog.generated.ts`
- 原则：
  - `lucide-subset.generated.ts` 只保留仓库实际使用图标子集，用于启动期默认注册。
  - `lucide-catalog.generated.ts` 是本地完整目录，仅在图标选择器、插件槽位等确有需要时懒加载。
  - 禁止手改 generated 文件，必须改扫描源或生成脚本后重新执行命令。

## 4. Icon Picker 规则

- 平台图标选择器默认只浏览本地 Lucide 集合。
- 搜索必须基于本地注册目录，不得调用线上 collection/search 接口。
- 手输图标值时必须做规范化与合法性校验：
  - 合法 Lucide 值可保存。
  - 非法或未知值不得作为平台功能图标持久化。

## 5. 插件图标规则

### 5.1 插件元数据图标

- `plugin.yaml` 顶层 `icon` 只允许：
  - `icon.png`
  - 空字符串
- 如果插件根目录存在 `icon.png`，加载器可以自动补齐。
- 如果插件未提供 `icon.png`，管理端统一回退到固定图标：`lucide:plug`。
- 管理端预览安装包时，可接受临时 `data:image/png` 预览值；落库后仍只认 `icon.png`。

### 5.2 插件页面/菜单图标

- `extensions.frontend.pages[*].icon`
- `extensions.frontend.pages[*].menu.icon`

以上字段只允许使用平台已注册的本地图标，默认应写 `lucide:*`。

## 6. 第三方 Iconify 集合

默认策略：不用。

如业务确实必须引入第三方集合，必须同时满足以下条件：

1. Lucide 和现有 `svg:*` 均无法满足。
2. 图标集合静态 vendoring 到仓库内，禁止运行时联网下载。
3. 在 `frontend/packages/icons/src/iconify/` 下提供本地注册文件。
4. 更新本规范、相关 rules/skill、以及生成或注册脚本。
5. 补充类型校验/单测，确认生产包中没有在线图标请求。

禁止事项：

- 禁止在浏览器运行时请求 `https://api.iconify.design/*`
- 禁止在业务组件内临时拼接第三方前缀并依赖在线解析
- 禁止把插件元数据图标写成 `mdi:*`、`simple-icons:*`、URL 或任意远端资源

## 7. 检查清单

提交前至少确认：

1. 新增平台功能图标是否优先用了 `lucide:*`
2. 若不是 Lucide，是否确实落成了本地 `svg:*`
3. 是否不存在新的在线 Iconify 请求
4. 是否执行了 `pnpm --dir frontend run icons:generate`
5. 插件元数据图标是否遵守 `icon.png` / `lucide:plug` 规则
