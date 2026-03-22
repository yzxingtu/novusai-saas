---
name: 用户端重构工作区收口审计
overview: 审计 2026-03-22 当前工作区中哪些改动属于“多域名公开首页与企业用户端重构方案”，哪些只是配套修复，哪些属于其他专题，不应继续混在同一条交付线上。
isProject: true
---

# 用户端重构工作区收口审计

审计日期：2026-03-22

## 一、审计目的

当前工作区不是一条干净的单主题分支，里面同时混有：

1. 多域名公开首页与企业用户端重构
2. 管理端/企业端 dashboard 重构
3. AI Skill 架构与插件相关改动
4. 若干杂项前端与构建配置调整

本文件的目的不是立刻回滚，而是先把边界说清楚，避免后续继续把无关改动混到“首页与用户端重构”这条线上。

---

## 二、分类标准

本次按四类处理：

### 2.1 A 类：本方案核心改动，建议保留

定义：

1. 直接实现平台公开首页、企业公开首页、企业登录后首页、入口路由、权限边界、`/home` 兼容、用户登出回跳
2. 已被浏览器联调验证，属于本方案交付主体

### 2.2 B 类：本方案配套修复，建议保留

定义：

1. 不在最初方案主清单里，但为本方案可用性补的依赖修复
2. 例如注册链路、重新认证逻辑、企业端一键进入修复

### 2.3 C 类：已明确由其他工作流负责，暂不并入本方案

定义：

1. 与本方案有交集，但用户已明确交给其他 AI 或其他交付线
2. 本次不应继续在这条线上改动和收口

### 2.4 D 类：与本方案无直接关系，建议拆出单独审查

定义：

1. AI Skill 架构、插件、构建链、测试、迁移等其它专题
2. 不应与本方案一起作为同一批交付内容继续推进

---

## 三、A 类：本方案核心改动，建议保留

以下文件与“平台公开首页 + 企业公开首页 + 企业登录后首页 + 权限边界”直接相关，建议保留为本方案主线。

### 3.1 路由与入口契约

1. `frontend/apps/web-antd/src/router/routes/root.ts`
   说明：平台域名 `/` 改为公开首页，企业域名 `/` 转发到 `UserHome`
2. `frontend/apps/web-antd/src/router/routes/user/index.ts`
   说明：`/home` 保留 alias，`/agents`、`/ai-chat`、`/help`、`/settings/*` 收回到登录后访问
3. `frontend/apps/web-antd/src/router/guard.ts`
   说明：域名感知入口、公开页与登录页跳转、跨端会话兜底
4. `frontend/apps/web-antd/src/store/shared/multi-auth.ts`
   说明：登录回跳、用户登出回企业公开首页、跨端 home 归一化
5. `frontend/apps/web-antd/src/store/shared/multi-auth.ts`
   说明：历史 `store/{admin,tenant,user}/auth.ts` 已删除，三端认证状态与登出/回跳语义统一收口到 shared multi-auth
6. `frontend/apps/web-antd/src/utils/request/instance.ts`
   说明：公开根路径下的 401 重认证逻辑改造，避免未登录公开首页被错误强跳登录
7. `backend/app/rbac/menus/user_menus.py`
   说明：用户端首页菜单 path 已统一到 `/`

### 3.2 平台公开首页与企业用户端页面

1. `frontend/apps/web-antd/src/views/public/platform-home/index.vue`
   说明：平台公开首页
2. `frontend/apps/web-antd/src/views/user/home/index.vue`
   说明：企业域名 `/` 的双态首页，未登录品牌门户 + 已登录工作台
3. `frontend/apps/web-antd/src/views/user/agents/index.vue`
   说明：登录后智能体广场
4. `frontend/apps/web-antd/src/views/user/help/index.vue`
   说明：登录后帮助中心
5. `frontend/apps/web-antd/src/views/user/ai-chat/index.vue`
   说明：登录后 AI 工作区增强
6. `frontend/apps/web-antd/src/views/user/modules/PortalAgentCard.vue`
   说明：用户端卡片组件
7. `frontend/apps/web-antd/src/views/user/modules/portal-data.ts`
   说明：用户端工作台/广场数据适配层
8. `frontend/apps/web-antd/src/views/user/modules/help-center.ts`
   说明：帮助中心文案与结构构造器
9. `frontend/apps/web-antd/src/layouts/user.vue`
   说明：用户端布局细节调整，属于用户端体验收口

### 3.3 文案与方案文档

1. `frontend/apps/web-antd/src/locales/langs/en-US/public.json`
2. `frontend/apps/web-antd/src/locales/langs/zh-CN/public.json`
3. `frontend/apps/web-antd/src/locales/langs/en-US/user.json`
4. `frontend/apps/web-antd/src/locales/langs/zh-CN/user.json`
5. `docs/design/user-portal-demo-revamp.plan.md`

结论：

1. 上述文件构成本方案当前主交付面
2. 后续如果要整理成单独交付，应优先围绕这组文件收口

---

## 四、B 类：本方案配套修复，建议保留

这些文件虽然不属于方案最初的“主入口清单”，但已经证明是为本方案可用性补上的必要修复，建议一起保留。

### 4.1 企业端一键进入修复

1. `frontend/apps/web-antd/src/store/shared/notification.ts`
   说明：修复管理端企业列表一键进入企业端后，企业页误发 `admin/notifications/*` 导致 401 和重新登录的问题

### 4.2 注册链路配套修复

1. `frontend/apps/web-antd/src/api/user/auth.ts`
   说明：注册请求补充 `captchaType`
2. `frontend/apps/web-antd/src/views/user/authentication/register.vue`
   说明：注册页把验证码 provider 传给后端

结论：

1. 这几项建议与本方案一起保留
2. 它们已经成为公开门户可演示、可注册、可进入工作台的组成部分

---

## 五、C 类：与本方案相邻，但当前不应继续并入

这些改动与方案方向相邻，但用户已明确有独立处理安排，不建议继续混到这条线上。

### 5.1 两个 dashboard 页面

1. `frontend/apps/web-antd/src/views/admin/dashboard/index.vue`
2. `frontend/apps/web-antd/src/views/tenant/dashboard/index.vue`
3. `frontend/apps/web-antd/src/views/admin/dashboard/use-admin-dashboard.ts`
4. `frontend/apps/web-antd/src/views/tenant/dashboard/use-tenant-dashboard.ts`

原因：

1. 用户已明确表示这两个页面有其他 AI 在重构
2. 本方案只需要保证它们与公开首页语义解耦，不需要在本次继续修改

结论：

1. 这批文件不要再并入“首页与用户端重构”的继续开发范围
2. 后续只做联调验收，不在这条线上继续改

---

## 六、D 类：与本方案无直接关系，建议拆出单独审查

以下内容不应继续混入本方案交付，建议后续独立审查、独立提交、独立回归。

### 6.1 AI Skill 架构与后端专题

典型目录：

1. `backend/app/ai/`
2. `backend/app/api/admin/agents.py`
3. `backend/app/api/admin/skill_packages.py`
4. `backend/app/api/admin/skills.py`
5. `backend/app/api/tenant/_agent_skills.py`
6. `backend/app/api/tenant/skill_packages.py`
7. `backend/app/models/ai/`
8. `backend/app/repositories/ai/`
9. `backend/app/services/ai/`
10. `backend/migrations/versions/20260325_0001_skill_architecture_foundation.py`
11. `backend/migrations/versions/20260325_0002_cleanup_legacy_skill_runtime_data.py`
12. `backend/tests/services/test_skill_service.py`
13. `backend/tests/test_plugin_skill_runtime_contract_overlay.py`
14. `backend/tests/test_plugin_skill_source_of_truth.py`

结论：

1. 这些是 AI Skill / Plugin Runtime 专题
2. 与公开首页和用户端入口重构不是同一交付

### 6.2 前端 AI 管理与插件专题

典型目录：

1. `frontend/apps/web-antd/src/views/admin/ai/`
2. `frontend/apps/web-antd/src/views/tenant/ai/`
3. `frontend/apps/web-antd/src/api/admin/skill-packages.ts`
4. `frontend/apps/web-antd/src/api/admin/skills.ts`
5. `frontend/apps/web-antd/src/api/tenant/skill-packages.ts`
6. `frontend/apps/web-antd/src/components/business/plugin-slots/`
7. `frontend/apps/web-antd/src/store/admin/plugin-install-progress.ts`
8. `frontend/apps/web-antd/src/utils/plugin-loader.ts`
9. `frontend/apps/web-antd/src/utils/plugin-shared.ts`
10. `frontend/apps/web-antd/build/vite-plugin-novus-plugins.ts`

结论：

1. 这些是 AI 管理、插件安装、插件运行时专题
2. 不建议与本方案一起继续开发或验收

### 6.3 构建链、样式基建、playground 与内部包调整

典型目录：

1. `frontend/apps/web-antd/vite.config.mts`
2. `frontend/apps/web-antd/postcss.config.ts`
3. `frontend/apps/web-antd/tailwind.config.ts`
4. `frontend/internal/tailwind-config/`
5. `frontend/playground/`
6. `frontend/packages/`
7. `frontend/internal/node-utils/`

结论：

1. 这些属于构建基建和 monorepo 配套调整
2. 与本方案目标没有直接绑定

### 6.4 其它专题文档

典型文件：

1. `docs/ai-skill-rearchitecture-handoff-20260322.md`
2. `docs/ai-skill-rearchitecture-plan.md`
3. `docs/design/ai-page-capability-unification-handoff-20260322.md`
4. `docs/design/icon-system-normalization-handoff-20260322.md`
5. `docs/design/icon-system-normalization-plan-20260322.md`

结论：

1. 属于其他专题交接，不应与本方案文档一起打包

---

## 七、建议的实际收口方式

如果下一步要把工作区变干净，建议按下面顺序执行，而不是直接粗暴回滚。

### 7.1 第一批：先锁定本方案范围

建议保留：

1. A 类全部文件
2. B 类全部文件

### 7.2 第二批：冻结其它人负责的内容

建议暂不处理：

1. C 类 dashboard 相关文件

原因：

1. 当前最容易引发冲突
2. 用户已明确有独立处理安排

### 7.3 第三批：把无关专题拆走

建议拆出单独审查的内容：

1. D 类全部文件

原因：

1. 这些文件数量大、影响面广
2. 与当前首页和用户端方案没有交付级强耦合
3. 混在一起只会让回归和问题归因失真

---

## 八、当前结论

当前最合理的判断不是“全部做完了”，也不是“全部都要推倒重来”，而是：

1. 平台公开首页、企业公开首页、企业登录后首页、权限边界、`/home` 兼容、用户登出回首页，这条主线已经落地
2. 企业端一键进入修复也已补齐
3. dashboard 视觉收尾与大量 AI Skill/插件/构建专题改动不应继续混在同一条线上
4. 下一步如果要真正收口，应该围绕 A 类和 B 类做单独交付整理，而不是继续在当前混合工作区上无边界推进
