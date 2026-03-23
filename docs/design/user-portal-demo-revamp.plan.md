---
name: 多域名公开首页与企业用户端重构单 AI 方案
overview: 基于用户最新澄清，重构平台公开首页、企业公开首页、企业登录后首页、后台首页之间的语义边界。本方案废弃旧的“双 AI 拆分 + 平台根路径归 admin dashboard”假设，改为单 AI 一次性收口。
todos:
  - id: clarify_entry_contract
    content: 明确平台公开首页、企业公开首页、企业登录后首页、平台后台、企业后台五类入口的路径语义
    status: completed
  - id: rebuild_root_routing
    content: 重构根路径与路由守卫，支持按域名和登录态展示不同首页，同时保持未登录可访问
    status: completed
  - id: rebuild_public_pages
    content: 重做平台公开首页与企业公开首页，区分官网介绍与企业品牌门户
    status: completed
  - id: rebuild_user_portal
    content: 重做企业登录后首页、智能体广场、AI 对话、帮助中心，明确 AI 页面必须登录
    status: completed
  - id: polish_dashboards
    content: 保留并继续优化平台后台 dashboard 与企业后台 dashboard 的视觉升级
    status: in_progress
  - id: integration_qa
    content: 基于真实入口契约完成联调与回归验证
    status: completed
isProject: true
---

# 多域名公开首页与企业用户端重构方案

审计日期：2026-03-22

## 0. 当前执行状态

本节用于同步方案与实际代码状态，避免后续执行者继续把本文当成“全部待做”的草案。

截至 2026-03-22，本方案的主干入口改造已经落地，且已完成关键浏览器验收；但 dashboard 视觉收尾与工作区总清理尚未在本文中闭环。

### 0.1 已落地

1. 平台域名根路径 `/` 已改为平台公开首页，不再跳 `/admin/login` 或 `/admin/dashboard`
2. 企业域名根路径 `/` 已改为用户端首页入口，未登录显示企业公开门户，登录后显示企业工作台
3. `/home` 已降级为兼容 alias，不再作为主导航入口
4. 用户端首页菜单 path 已统一为 `/`
5. 用户端登出后已回到企业公开首页 `/`
6. `/ai-chat`、`/agents`、`/help`、`/settings/*` 已收回到登录后访问
7. 平台公开首页与企业首页双态页面已经实现
8. 管理端企业列表的一键进入企业端链路已补修，避免企业端首屏误发 `admin/notifications/*` 导致 401 重新登录
9. 前端 `pnpm typecheck` 已通过，用户端首页/企业域名入口相关的遗留类型错误已收口

### 0.2 已验证

1. `http://localhost:5666/` 未登录打开平台公开首页
2. `http://ss.dakkii.cn:5666/` 未登录打开企业公开首页
3. 未登录访问 `http://ss.dakkii.cn:5666/ai-chat` 会跳转到 `http://ss.dakkii.cn:5666/auth/login?redirect=/ai-chat`
4. 企业用户登录后进入 `http://ss.dakkii.cn:5666/`，显示登录后工作台
5. `/home` 兼容仍可用
6. 从 `http://localhost:5666/admin/tenant/list` 使用“当前标签页进入 (Dev)”可成功进入企业端，不再触发错误的 `admin/notifications/unread-count` 请求
7. `frontend/apps/web-antd` 下执行 `pnpm typecheck` 已通过

### 0.3 仍未在本文内闭环

1. 平台后台 dashboard 与企业后台 dashboard 的最终视觉收尾仍属于单独收口项
2. 当前工作区存在大量与本方案无关的脏改动，尚未完成“哪些保留、哪些丢弃”的最终总清理
3. 本文后续章节仍保留完整实施说明，便于继续作为交接与审计文档使用

工作区收口矩阵见：

1. `docs/design/user-portal-demo-revamp-worktree-audit-20260322.md`

## 一、为什么重写方案

此前方案存在一个根本性误解：

1. 误把企业用户端登录后的首页 `/` 当成唯一首页语义
2. 误把 `http://localhost:5666/` 设计成“进入 admin 端”的根入口
3. 误把“平台首页”“企业公开首页”“企业登录后首页”混成了一类页面

用户现已明确真实目标，本方案以最新目标为唯一准绳，旧方案全部失效。

本文件是新的唯一执行依据。

---

## 二、用户已确认的真实目标

以下内容来自用户本轮明确确认，必须视为冻结契约。

### 2.1 平台域名首页

1. `http://localhost:5666/` 是平台端公开首页
2. 该首页允许未登录访问
3. 它不是 admin dashboard
4. 它的产品定位是平台官网介绍页

### 2.2 企业域名首页

1. `http://ss.dakkii.cn:5666/` 是企业域名首页
2. 该首页允许未登录访问
3. 未登录时，它是企业品牌门户
4. 登录后，企业用户默认仍进入 `/`
5. 但登录后的 `/` 与未登录的 `/` 不是同一个体验，需要按登录态区分

### 2.3 后台首页

1. 平台后台首页仍是 `/admin/dashboard`
2. 企业管理后台首页仍是 `/tenant/dashboard`
3. 这两个后台首页和公开首页不是同一类页面
4. 公开首页的存在，不应改变后台首页的职责

### 2.4 AI 使用权限

1. AI 使用必须登录
2. 不允许未登录直接使用 AI 对话
3. 不允许未登录直接进入可执行 AI 能力页

### 2.5 产品方向

1. 论坛不做
2. 平台公开首页偏官网介绍
3. 企业公开首页偏企业品牌门户
4. 企业登录后首页偏用户工作台 / AI 服务入口

---

## 三、最终入口语义总表

这是整个项目必须统一的最终语义表。

### 3.1 平台域名

以 `localhost`、`127.0.0.1` 和配置中的平台域名为平台域名。

| 路径 | 登录态 | 目标页面 | 是否公开 |
|---|---|---|---|
| `/` | 未登录 | 平台公开首页 | 是 |
| `/` | 已登录 admin | 仍可访问平台公开首页，不强制跳 dashboard | 是 |
| `/admin/login` | 未登录 | 平台登录页 | 是 |
| `/admin/dashboard` | 已登录 admin | 平台后台首页 | 否 |
| `/tenant/dashboard` | 已登录 tenant admin | 企业管理后台首页 | 否 |

关键原则：

1. 平台域名的 `/` 是公开官网，不是后台首页
2. `ADMIN_HOME_PATH` 仍应指向 `/admin/dashboard`
3. 不能再把平台域名的 `/` 自动重定向到 `/admin/login` 或 `/admin/dashboard`

### 3.2 企业域名

以企业绑定域名或系统识别出的 tenant domain 为企业域名。

| 路径 | 登录态 | 目标页面 | 是否公开 |
|---|---|---|---|
| `/` | 未登录 | 企业公开首页 | 是 |
| `/` | 已登录 user | 企业登录后首页 | 否，但路径仍是 `/` |
| `/auth/login` | 未登录 | 用户登录页 | 是 |
| `/ai-chat` | 已登录 user | AI 对话页 | 否 |
| `/agents` | 已登录 user | 智能体广场 | 否 |
| `/help` | 已登录 user | 帮助中心 | 否 |
| `/settings/profile` | 已登录 user | 个人资料 | 否 |

关键原则：

1. 企业域名的 `/` 同一个路径要支持两种体验
2. 未登录时是企业品牌门户
3. 登录后是企业用户首页
4. 两者不是同一个页面体验，但可以共用同一个路径

### 3.3 旧路径兼容

| 路径 | 兼容策略 |
|---|---|
| `/home` | 作为历史别名保留，最终归并到企业登录后首页 `/` |
| `/admin/dashboard` | 保留 |
| `/tenant/dashboard` | 保留 |

关键原则：

1. `/home` 不能再成为显式主入口
2. 但不能轻易删除，避免旧链接和旧缓存报错
3. 菜单、CTA、登录回跳都应以 `/` 为企业用户登录后首页

---

## 四、这次方案的核心难点

这次不是简单改几个路由。

真正难点有四个：

1. 平台域名 `/` 和企业域名 `/` 需要按域名区分
2. 企业域名 `/` 还要按登录态再区分未登录与已登录体验
3. 后台首页与公开首页必须彻底脱钩
4. 旧的 `/home`、`HOME_PATHS`、`guard`、端点 resolver 历史别名链、动态菜单 path 必须统一收口

因此，本次改造本质上是“公开首页体系 + 登录后首页体系 + 多端入口体系”的重构。

---

## 五、对旧 AI 改动的处理结论

此前多 AI 的讨论痕迹已部分散落在当前工作树里，但本次执行必须以本文和工作树审计文档为准，不能无脑回滚，也不能无脑继承历史假设。

### 5.1 可以复用的方向

以下内容方向上大体可复用，但必须按新契约复审：

1. [frontend/apps/web-antd/src/views/admin/dashboard/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/dashboard/index.vue)
2. [frontend/apps/web-antd/src/views/tenant/dashboard/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/tenant/dashboard/index.vue)
3. [frontend/apps/web-antd/src/views/user/ai-chat/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/ai-chat/index.vue)
4. [frontend/apps/web-antd/src/views/user/agents/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/agents/index.vue)
5. [frontend/apps/web-antd/src/views/user/help/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/help/index.vue)
6. [frontend/apps/web-antd/src/views/user/modules/](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/modules/)

原因：

1. 这些文件主要是页面和组件能力建设
2. 它们不一定和错误入口契约强绑定
3. 其中部分内容可以转化为“登录后企业首页”或“已登录用户功能页”

### 5.2 不能直接继承的方向

以下内容必须按新目标重做或彻底复审：

1. [frontend/apps/web-antd/src/router/routes/root.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/routes/root.ts)
2. [frontend/apps/web-antd/src/router/routes/index.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/routes/index.ts)
3. [frontend/apps/web-antd/src/router/guard.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/guard.ts)
4. [frontend/apps/web-antd/src/constants/endpoints.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/constants/endpoints.ts)
5. [frontend/apps/web-antd/src/api/shared/types.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/api/shared/types.ts)
6. [frontend/apps/web-antd/src/store/shared/multi-auth.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/store/shared/multi-auth.ts)
7. [backend/app/rbac/menus/user_menus.py](E:/git_clone/novusai-saas-yudi/backend/app/rbac/menus/user_menus.py)

原因：

1. 旧方案曾把平台根路径 `/` 视为 admin 端主入口
2. 旧方案曾把“企业用户登录后首页 = 整个根路径唯一语义”写进共享契约
3. 旧方案没有正确表达“平台公开首页”和“企业公开首页”的公开属性

### 5.3 本次重做的原则

1. 不要求把旧 AI 改动全部回滚
2. 允许复用已经做好的 UI 和组件
3. 但路由、守卫、首页语义、登录回跳必须以新契约为准重新收口

### 5.4 旧 AI 文件级处理清单

本节是给当前执行者的硬清单，避免继续讨论“哪些能留、哪些要丢”。

处理分成三类：

1. 直接保留
2. 保留文件，但必须重做内部逻辑
3. 丢弃当前实现，仅保留文件载体或思路参考

#### 5.4.1 直接保留

以下文件当前方向正确，可直接保留，再做少量 polish 即可：

1. [frontend/apps/web-antd/src/views/admin/dashboard/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/dashboard/index.vue)
   结论：保留
   原因：它是后台 dashboard 视觉升级，不影响根路径契约；当前方向符合“平台控制塔”。
2. [frontend/apps/web-antd/src/views/tenant/dashboard/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/tenant/dashboard/index.vue)
   结论：保留
   原因：它是企业后台 dashboard 视觉升级，不与公开首页语义冲突。
3. [frontend/apps/web-antd/src/views/user/ai-chat/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/ai-chat/index.vue)
   结论：大体保留
   原因：它主要是聊天页产品化增强，底层仍复用 `useAIChat`；只需确保路由权限改成“必须登录”。
4. [frontend/apps/web-antd/src/views/user/agents/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/agents/index.vue)
   结论：大体保留
   原因：它复用了现有 user agents 能力，产品方向正确；只需确保未登录不能直接访问。
5. [frontend/apps/web-antd/src/views/user/help/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/help/index.vue)
   结论：大体保留
   原因：帮助中心方向正确；只需改成登录后页，不要再让未登录通过 route 直接进入。
6. [frontend/apps/web-antd/src/views/user/modules/PortalAgentCard.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/modules/PortalAgentCard.vue)
   结论：保留
   原因：通用组件，不绑定错误入口契约。
7. [frontend/apps/web-antd/src/views/user/modules/portal-data.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/modules/portal-data.ts)
   结论：保留
   原因：它是登录后工作台和 agents 页的数据层，可被继续复用。
8. [frontend/apps/web-antd/src/views/user/modules/help-center.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/modules/help-center.ts)
   结论：保留
   原因：它是帮助中心静态内容构造器，可直接复用。

#### 5.4.2 保留文件，但必须重做内部逻辑

以下文件不能整份丢掉，因为里面已经沉淀了可用结构；但当前实现逻辑与新目标不完全一致，必须重做内部逻辑。

1. [frontend/apps/web-antd/src/views/user/home/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/home/index.vue)
   结论：保留文件，重做内部逻辑
   保留部分：
   - “已登录工作台”内容块
   - “未登录企业品牌门户”内容块
   - 基于品牌配置、workspace 数据、帮助资源的组织方式
   丢弃部分：
   - 把“平台公开首页”也塞进 `user/home` 的做法
   原因：
   - 企业域名 `/` 的双态设计是对的
   - 但平台公开首页应独立出来，不应继续混在用户首页组件内
2. [frontend/apps/web-antd/src/router/routes/user/index.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/routes/user/index.ts)
   结论：保留文件，重做 route meta
   保留部分：
   - `path: '/'`
   - `alias: ['/home']`
   - `agents`、`ai-chat`、`help`、`settings` 的子路由骨架
   丢弃部分：
   - 所有用户子页统一 `ignoreAccess: true` 的策略
   原因：
   - `/` 可以公开，但 `/ai-chat`、`/agents`、`/help`、`/settings/*` 必须登录
3. [backend/app/rbac/menus/user_menus.py](E:/git_clone/novusai-saas-yudi/backend/app/rbac/menus/user_menus.py)
   结论：保留文件，按登录后菜单重做细节
   保留部分：
   - 首页菜单 path 改为 `/`
   - `agents`、`help` 目录菜单新增方向
   丢弃部分：
   - 任何把菜单理解为“公开首页入口”的隐含假设
   原因：
   - 这个文件只服务登录后用户菜单，不能代表公开首页
4. [frontend/apps/web-antd/src/constants/endpoints.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/constants/endpoints.ts)
   结论：保留文件，重做 root/public 相关语义
   保留部分：
   - 平台域名识别
   - `USER_HOME_ALIAS_PATH = '/home'`
   - 导航路径归一化的大方向
   丢弃部分：
   - 任何把平台根路径 `/` 视为 admin 后台首页跳板的使用方式
   - 任何把 admin 端的 `/` 一律归一化到 `/admin/dashboard` 的过强假设
   原因：
   - 平台根路径现在是公开官网，不是后台 home
5. [frontend/apps/web-antd/src/api/shared/types.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/api/shared/types.ts)
   结论：保留文件，保留代理入口
   保留部分：
   - 统一端点解析由共享 resolver 承接的收口思路
   丢弃部分：
   - 恢复共享端点 resolver 的已删除历史别名链（后续也不应恢复）
   - 若 resolver 仍按旧首页语义工作，则必须随 `endpoints.ts` 一起调整
6. [frontend/apps/web-antd/src/store/shared/multi-auth.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/store/shared/multi-auth.ts)
   结论：保留文件，重做当前路由/登出跳转语义
   保留部分：
   - 多端 token 隔离
   - `normalizeEndpointNavigationPath()` 的统一收口思路
   丢弃部分：
   - 用户登出后总是回登录页的默认策略
   原因：
   - 用户端登出后应回企业公开首页 `/`，而不是强制回 `/auth/login`
7. [frontend/apps/web-antd/src/store/shared/multi-auth.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/store/shared/multi-auth.ts)
   结论：统一认证入口继续保留，不再恢复端别专属 auth store
   当前承接：
   - 登录成功回跳与 `homePath` 归一化
   - 用户登出回企业公开首页 `/`
   - 管理端/企业管理员分别回各自后台首页
   已删除旧实现：
   - admin 端专属 auth store
   - tenant 端专属 auth store
   - user 端专属 auth store
   原因：
   - 认证状态、Token 隔离、跳转语义已统一收口，继续维护三套 auth store 只会制造重复实现
8. [frontend/apps/web-antd/src/router/guard.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/guard.ts)
   结论：保留文件，重做访问控制判定
   保留部分：
   - 品牌配置加载
   - 域名检测
   - 动态菜单/权限生成骨架
   - 插件路由兜底逻辑
   丢弃部分：
   - “只要 `ignoreAccess: true` 就放行”的用户页访问策略
   原因：
   - 公开页与登录后页必须分层，不能让 `/agents`、`/help`、`/ai-chat` 因为 `ignoreAccess` 而裸奔

#### 5.4.3 丢弃当前实现，仅保留文件载体或思路参考

以下文件不能沿用当前实现，必须按新契约重写。

1. [frontend/apps/web-antd/src/router/routes/root.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/routes/root.ts)
   结论：丢弃当前实现，仅保留文件载体
   当前错误：
   - 平台域名 `/` 未登录跳 `/admin/login`
   - 平台域名 `/` 已登录跳 `/admin/dashboard`
   为什么必须丢弃：
   - 平台根路径 `/` 现在是公开官网，不是后台跳板
2. [frontend/apps/web-antd/src/router/routes/index.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/routes/index.ts)
   结论：保留文件，但丢弃“root route 只是 redirect gateway”的理解
   说明：
   - 当前把 `rootRoutes` 放在 `userRoutes` 前面这个顺序是对的，可以保留
   - 但 `rootRoutes` 的职责必须重写成公开首页入口，而不是跳板

#### 5.4.4 当前执行顺序上的硬要求

为了避免再次混乱，本次执行必须按下面顺序处理：

1. 先重写 `root.ts`
2. 再重写 `guard.ts` 和 `user/index.ts`
3. 再调整 `multi-auth.ts`、`user/auth.ts`、`endpoints.ts`
4. 再处理 `user/home/index.vue`
5. 最后才是 `agents`、`help`、`ai-chat`、`dashboard` 的联调

否则很容易出现：

1. 页面看起来做对了，但入口错了
2. 未登录用户仍能直接进入 AI 页面
3. 登出后回错地址
4. 平台根路径又被改回后台跳板

---

## 六、必须严格遵守的项目规范

### 6.1 前端规范

1. 禁止硬编码文案，必须走 `$t()` / `t()`
2. 禁止业务代码使用 `any`
3. 用户端菜单必须继续走动态菜单，不允许在 layout 内手写固定菜单体系替代
4. 页面必须兼顾桌面端与移动端
5. 不允许直接新造一套与现有 store/router/access 完全脱节的入口体系

### 6.2 后端规范

1. `user_menus.py` 只负责登录后用户菜单，不负责公开首页
2. Controller 不写业务逻辑
3. Service 不直接写 Repository 细节
4. 统一返回规范响应

### 6.3 AI 规范

1. AI 功能继续走 Agent -> Skill -> AIGateway 链路
2. AI 对话页继续复用现有 `useAIChat`
3. 任何“未登录可体验 AI”的设计本次都禁止

---

## 七、单 AI 的完整执行范围

本次不再拆两个 AI，本次由一个 AI 统一负责。

这个 AI 需要同时完成四类工作：

1. 入口路由重构
2. 公开首页重构
3. 登录后用户端页面收口
4. dashboard 视觉优化收尾

### 7.1 允许修改的核心文件

1. [frontend/apps/web-antd/src/router/routes/index.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/routes/index.ts)
2. [frontend/apps/web-antd/src/router/routes/root.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/routes/root.ts)
3. [frontend/apps/web-antd/src/router/routes/user/index.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/routes/user/index.ts)
4. [frontend/apps/web-antd/src/router/guard.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/guard.ts)
5. [frontend/apps/web-antd/src/constants/endpoints.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/constants/endpoints.ts)
6. [frontend/apps/web-antd/src/api/shared/types.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/api/shared/types.ts)
7. [frontend/apps/web-antd/src/store/shared/multi-auth.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/store/shared/multi-auth.ts)
8. [frontend/apps/web-antd/src/api/admin/auth.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/api/admin/auth.ts)
9. [frontend/apps/web-antd/src/api/tenant/auth.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/api/tenant/auth.ts)
10. [frontend/apps/web-antd/src/api/user/auth.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/api/user/auth.ts)
11. [backend/app/rbac/menus/user_menus.py](E:/git_clone/novusai-saas-yudi/backend/app/rbac/menus/user_menus.py)
12. [frontend/apps/web-antd/src/views/user/home/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/home/index.vue)
13. [frontend/apps/web-antd/src/views/user/ai-chat/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/ai-chat/index.vue)
14. [frontend/apps/web-antd/src/views/user/agents/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/agents/index.vue)
15. [frontend/apps/web-antd/src/views/user/help/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/help/index.vue)
16. [frontend/apps/web-antd/src/views/admin/dashboard/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/admin/dashboard/index.vue)
17. [frontend/apps/web-antd/src/views/tenant/dashboard/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/tenant/dashboard/index.vue)
18. 与本次页面相关的 i18n 文件和必要的新组件文件

---

## 八、推荐的最终技术实现

### 8.1 根路径必须拆成“平台公开入口”和“企业用户入口”

推荐做法：

1. 保留 [frontend/apps/web-antd/src/router/routes/root.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/routes/root.ts)
2. 但不要再把它实现成“平台域名 `/` 自动跳登录/跳 dashboard”
3. 根路径 route 必须改为真正的公开入口路由

推荐语义：

1. 平台域名访问 `/` 时，根路径直接渲染平台公开首页
2. 企业域名访问 `/` 时，根路径应进入用户端首页路由
3. 用户端首页路由内部再按登录态区分公开品牌门户与登录后工作台

### 8.2 为什么企业域名 `/` 应继续归用户端路由

因为用户已经明确：

1. 企业用户登录后默认进入 `/`
2. 企业公开首页与登录后首页不是同一个体验
3. 但路径都希望是 `/`

最稳妥的实现方式不是把企业公开首页和企业登录后首页拆成两个不同路径，而是：

1. 让企业域名 `/` 始终匹配 user 端首页 route
2. 在 [frontend/apps/web-antd/src/views/user/home/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/home/index.vue) 内按登录态切换视图

即：

1. 未登录 -> 企业品牌门户
2. 已登录 -> 企业用户工作台 / AI 服务入口

### 8.3 平台公开首页不等于 admin home

必须明确：

1. 平台公开首页路径是 `/`
2. `ADMIN_HOME_PATH` 仍是 `/admin/dashboard`
3. 平台公开首页不进入 admin menu 体系
4. 平台公开首页不要求登录

换言之：

1. `platform public root != ADMIN_HOME_PATH`
2. `user logged-in home == USER_HOME_PATH == /`

这两个概念不能再混淆。

### 8.4 用户端页面权限边界

建议引入明确的页面级权限语义，而不要只依赖 `ignoreAccess`。

推荐约束：

1. `/` 在企业域名下允许未登录访问
2. `/ai-chat` 必须登录
3. `/agents` 必须登录
4. `/help` 必须登录
5. `/settings/*` 必须登录
6. `/home` 作为 alias 时也应按“登录后首页”语义处理

如果现有 guard 体系缺少“公开页”和“登录后页”的显式标记，建议在 route meta 中新增清晰标记，例如：

1. `publicAccess: true`
2. `requiresUserAuth: true`

但最终实现方式可由开发 AI 根据现有 guard 结构决定。

### 8.5 `/home` 的最终策略

本次不建议删除 `/home`。

最终策略建议如下：

1. `/home` 保留为历史兼容 alias
2. 菜单不再展示 `/home`
3. 登录成功默认回 `/`
4. 用户菜单首页 path 使用 `/`
5. 旧链接访问 `/home` 时，最终体验应与登录后首页一致

---

## 九、页面产品设计目标

### 9.1 平台公开首页

产品定位：

1. 官网介绍页
2. 介绍系统能力与平台价值
3. 不承担后台工作台职责

推荐内容结构：

1. Hero 区：平台定位、主标题、副标题、主 CTA
2. 能力总览：多租户、品牌化、AI、权限、插件、运营
3. 产品架构：平台端、企业管理端、企业用户端三端关系
4. 演示价值：可演示 AI、品牌门户、后台管理、插件能力
5. 登录入口：平台登录、企业登录、演示说明
6. 页脚：版本、文档、联系信息或演示说明

设计要求：

1. 不要做成普通后台卡片页
2. 更接近官网 / 品牌介绍页
3. 可以适当展示系统能力，但不要直接暴露后台数据面板

### 9.2 企业公开首页

产品定位：

1. 企业品牌门户
2. 面向未登录访客
3. 核心目的是展示企业形象与服务入口

推荐内容结构：

1. 企业品牌头图与 slogan
2. 企业业务介绍 / 服务介绍
3. 产品价值与亮点
4. 常见问题或服务流程说明
5. 登录 CTA
6. 若需要，可有“登录后可使用 AI 助理/智能体”说明，但不能直接开放 AI

设计要求：

1. 更像企业品牌站，而不是后台首页
2. 不要让未登录用户误以为可以直接开始 AI 对话
3. 必须强调登录入口

### 9.3 企业登录后首页

产品定位：

1. 企业用户工作台
2. 用户登录后默认进入 `/`
3. 是用户后续进入 AI 功能的主入口

推荐内容结构：

1. 欢迎区与个人快捷入口
2. 智能体推荐
3. 最近会话
4. 常用快捷入口：智能体、AI 对话、帮助中心、设置
5. 使用提示或 onboarding
6. 空状态与引导

设计要求：

1. 与未登录企业品牌门户明确区分
2. 明显比当前“品牌介绍页”更像工作台
3. AI CTA 可以出现，但必须是登录后才可触发的真实功能入口

### 9.4 智能体广场

产品定位：

1. 登录后用户可用智能体列表页
2. 不做论坛
3. 不重造后端

实现原则：

1. 优先复用现有 user agents API
2. 支持卡片展示、标签、适用场景、快捷发起对话
3. 不允许未登录访问

### 9.5 AI 对话页

产品定位：

1. 登录后执行 AI 对话的主工作页
2. 只对已登录用户开放

实现原则：

1. 继续复用现有 `useAIChat`
2. 优先增强空状态、推荐问题、上下文说明、入口引导
3. 不修改底层 AI 调用链路

### 9.6 帮助中心

产品定位：

1. 登录后帮助中心
2. 承接用户对系统使用方式的理解

实现原则：

1. 以 FAQ、使用流程、常见问题为主
2. 不要新增复杂后端
3. 不允许未登录直接进入

### 9.7 两个 dashboard

平台后台 dashboard：

1. 定位为平台控制塔
2. 保留管理数据概览属性
3. 视觉上更有平台中台感

企业管理后台 dashboard：

1. 定位为企业运营驾驶舱
2. 强调企业运营、AI 使用、内容与成员等信息
3. 与平台后台视觉语义明显区分

---

## 十、详细实施拆分

### 10.1 Phase A：先收口入口契约

必须先完成：

1. 重写 [frontend/apps/web-antd/src/router/routes/root.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/routes/root.ts)
2. 重写 [frontend/apps/web-antd/src/router/guard.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/router/guard.ts)
3. 校正 [frontend/apps/web-antd/src/constants/endpoints.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/constants/endpoints.ts)
4. 校正 [frontend/apps/web-antd/src/store/shared/multi-auth.ts](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/store/shared/multi-auth.ts)

这一阶段的核心结果：

1. 平台域名 `/` 可匿名访问平台公开首页
2. 企业域名 `/` 可匿名访问企业公开首页
3. 企业用户登录后仍进入 `/`
4. `/ai-chat`、`/agents`、`/help` 未登录时会去用户登录页
5. `/admin/dashboard`、`/tenant/dashboard` 行为不回归

### 10.2 Phase B：再收口用户菜单和历史兼容

必须完成：

1. [backend/app/rbac/menus/user_menus.py](E:/git_clone/novusai-saas-yudi/backend/app/rbac/menus/user_menus.py) 中首页菜单 path 应为 `/`
2. `/home` 仅保留兼容 alias
3. 菜单不再把 `/home` 当作主路径
4. 登录成功回跳、菜单点击、页面内 CTA 都统一到 `/`

### 10.3 Phase C：重做首页与核心页面

必须完成：

1. 平台公开首页
2. 企业公开首页
3. 企业登录后首页
4. 智能体广场
5. AI 对话页
6. 帮助中心

建议实现顺序：

1. 先把 [frontend/apps/web-antd/src/views/user/home/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/home/index.vue) 改造成“未登录企业品牌门户 + 已登录企业工作台”双态页面
2. 再补平台公开首页
3. 再收尾 `agents`、`ai-chat`、`help`

### 10.4 Phase D：收尾 dashboard

这部分可以复用当前已有 UI 改造成果，但必须做一次复审，确保：

1. 平台后台 dashboard 仍然是后台，而不是官网页
2. 企业后台 dashboard 仍然是后台，而不是企业品牌页

---

## 十一、建议的文件级实施策略

### 11.1 路由层

建议实现：

1. `root.ts` 负责平台域名 `/`
2. `user/index.ts` 继续负责企业域名的用户端路由
3. 通过域名感知与命名路由跳转，让平台 `/` 和企业 `/` 各归其主

推荐行为：

1. 平台域名访问 `/` -> 平台公开首页 route
2. 企业域名访问 `/` -> `UserHome`

### 11.2 用户首页页内分态

[frontend/apps/web-antd/src/views/user/home/index.vue](E:/git_clone/novusai-saas-yudi/frontend/apps/web-antd/src/views/user/home/index.vue) 需要明确拆成两套内容块：

1. `isLoggedIn === false` 时，展示企业品牌门户
2. `isLoggedIn === true` 时，展示企业用户工作台

推荐不要把两套内容写成简单的少量 if/else 文案切换，而应明确分成两个大区块或两个子组件。

### 11.3 权限控制

当前最大的风险是用户端很多 route 使用了 `ignoreAccess: true`。

本次必须复核以下页面是否会被未登录直接访问：

1. `/ai-chat`
2. `/agents`
3. `/help`
4. `/settings/profile`
5. `/settings/password`

若当前 guard 不能精确表达“公开但不登录”和“必须登录”两类语义，则需要补 route meta 或 guard 规则。

### 11.4 公开首页与后台首页的 CTA

必须统一：

1. 平台公开首页 CTA 指向平台登录或后台入口
2. 企业公开首页 CTA 指向用户登录
3. 已登录企业首页 CTA 指向 `/agents`、`/ai-chat`、`/help`
4. 不允许未登录 CTA 直接进入 AI 对话执行页

---

## 十二、验收标准

### 12.1 入口验收

1. `http://localhost:5666/` 未登录可打开
2. `http://localhost:5666/` 显示的是平台公开首页，不是 dashboard
3. `http://ss.dakkii.cn:5666/` 未登录可打开
4. `http://ss.dakkii.cn:5666/` 未登录显示企业品牌门户
5. 企业用户登录后进入 `http://ss.dakkii.cn:5666/`
6. 企业用户登录后 `/` 显示的是企业工作台，而不是未登录品牌门户
7. `/admin/dashboard` 和 `/tenant/dashboard` 不受破坏

### 12.2 权限验收

1. 未登录访问 `/ai-chat` 会去用户登录页
2. 未登录访问 `/agents` 会去用户登录页
3. 未登录访问 `/help` 会去用户登录页
4. 未登录访问 `/settings/profile` 会去用户登录页
5. 未登录不能直接使用 AI

### 12.3 菜单与回跳验收

1. 用户菜单首页 path 指向 `/`
2. 登录后首页菜单点击进入企业首页，不会跳企业后台
3. 用户登录成功默认回 `/`
4. 用户登出后可回到企业公开首页 `/`
5. `/home` 旧链接仍可兼容，但不再是主导航路径

### 12.4 页面设计验收

1. 平台公开首页明显是官网页
2. 企业公开首页明显是品牌页
3. 企业登录后首页明显是工作台
4. platform dashboard 与 tenant dashboard 仍明显是后台页
5. 移动端可正常浏览首页和主要功能入口

---

## 十三、开发风险与防错项

### 13.1 最大风险

1. 继续沿用“平台 `/` = admin dashboard 入口”的旧思路
2. 把企业公开首页和企业登录后首页强行拆成两个路径
3. 忘记处理未登录的 AI 权限页
4. 只改 UI，不改 guard 和登录回跳

### 13.2 需要特别注意的冲突点

1. `USER_HOME_PATH = '/'` 仍然成立，但它表示“企业登录后用户首页”
2. 平台公开首页也是 `/`，但不是 `ADMIN_HOME_PATH`
3. 因此根路径语义必须同时看域名和登录态，不能只看路径常量

### 13.3 对现有工作区的建议

1. 不要直接清空当前工作区改动
2. 先基于本方案甄别哪些改动要保留
3. 旧 AI 已改的 UI 页面可以吸收
4. 旧 AI 已改的共享契约文件必须按本方案重新校正

---

## 十四、给单 AI 的直接执行口令

如果要把本方案交给一个 AI 直接重做，可以直接发下面这段提示词。

```text
你现在是本项目唯一的执行 AI。本次不是在旧方案上继续补丁，而是基于最新用户澄清，重做“平台公开首页 / 企业公开首页 / 企业登录后首页 / 后台首页”的入口契约与页面实现。

先阅读以下两个文件：
1. E:\git_clone\novusai-saas-yudi\docs\design\user-portal-demo-revamp.plan.md
2. E:\git_clone\novusai-saas-yudi\docs\design\user-portal-demo-revamp-worktree-audit-20260322.md

严格遵守 novusai-saas 项目规范。

你必须以以下冻结契约为准：

一、根路径与首页语义
1. http://localhost:5666/ 是平台公开首页，允许未登录访问，偏官网介绍，不是 admin dashboard
2. http://ss.dakkii.cn:5666/ 是企业域名首页，允许未登录访问
3. 企业域名未登录访问 / 时，显示企业品牌门户
4. 企业用户登录后默认也进入 /，但显示的是登录后企业用户首页
5. 企业公开首页和企业登录后首页不是同一个体验，但路径都可以是 /
6. 平台后台首页仍是 /admin/dashboard
7. 企业管理后台首页仍是 /tenant/dashboard
8. 论坛不做

二、权限规则
1. AI 使用必须登录
2. /ai-chat 必须登录
3. /agents 必须登录
4. /help 必须登录
5. /settings/* 必须登录
6. /home 只保留历史兼容，不能再当主入口

三、实施要求
1. 先重做根路径和 guard 契约
2. 再重做平台公开首页、企业公开首页、企业登录后首页
3. 再收尾 agents、ai-chat、help、dashboard
4. 允许复用当前工作树里已经做出的 UI 成果，但不要继续沿用错误入口假设
5. 不要把 localhost 的 / 再改成 admin 登录跳板或 dashboard 跳板
6. 不要让未登录用户直接进入 AI 执行页
7. 不要把企业首页菜单指向企业后台

四、你需要特别检查和修正的文件
1. frontend/apps/web-antd/src/router/routes/root.ts
2. frontend/apps/web-antd/src/router/routes/index.ts
3. frontend/apps/web-antd/src/router/routes/user/index.ts
4. frontend/apps/web-antd/src/router/guard.ts
5. frontend/apps/web-antd/src/constants/endpoints.ts
6. frontend/apps/web-antd/src/api/shared/types.ts
7. frontend/apps/web-antd/src/store/shared/multi-auth.ts
8. frontend/apps/web-antd/src/api/admin/auth.ts
9. frontend/apps/web-antd/src/api/tenant/auth.ts
10. frontend/apps/web-antd/src/api/user/auth.ts
11. backend/app/rbac/menus/user_menus.py
12. frontend/apps/web-antd/src/views/user/home/index.vue
13. frontend/apps/web-antd/src/views/user/ai-chat/index.vue
14. frontend/apps/web-antd/src/views/user/agents/index.vue
15. frontend/apps/web-antd/src/views/user/help/index.vue
16. frontend/apps/web-antd/src/views/admin/dashboard/index.vue
17. frontend/apps/web-antd/src/views/tenant/dashboard/index.vue

五、最终交付必须说明
1. 哪些旧改动保留了
2. 哪些旧改动被重做了
3. 最终入口契约是什么
4. 各页面是否公开或登录后访问
5. 做了哪些验证
6. 还有哪些风险
```

---

## 十五、总建议结论

本次最优路线不是论坛，也不是继续沿用旧的“双 AI 分工 + 平台根路径归后台”的方案。

正确路线是：

1. 把平台域名 `/` 明确为公开官网首页
2. 把企业域名 `/` 明确为“未登录品牌门户 / 已登录用户首页”的同路径双态入口
3. 把 `/admin/dashboard`、`/tenant/dashboard` 保持为后台首页
4. 把 AI 功能页全部收回到登录后
5. 用一个 AI 统一收口，不再拆分契约所有权

这才符合用户真实目的，也最能减少返工。
