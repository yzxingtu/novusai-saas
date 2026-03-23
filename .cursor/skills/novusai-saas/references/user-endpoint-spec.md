# 用户端（User Endpoint）开发规范

> 用户端是面向 C 端业务用户的前端 + 后端体系，与 admin/tenant 端有显著架构差异。本文档覆盖 UserLayout、认证流程、RBAC、响应式设计等用户端专属规范。
>
> 现状说明：
> - 当前前端静态主路由为 `/`、`/ai-chat`、`/settings/*`，`/home` 仅保留为兼容 alias
> - 认证页使用共享 `/auth/*` 路由
> - 后端 `user_menus.py` 仍保留 legacy `dashboard` 资源码，用于兼容历史菜单资源；但规范路由与组件落点已对齐 `/`
> - 新增能力时，不要继续扩散旧命名；优先以 `router/routes/user/index.ts`、`views/user/*` 为前端落点真相

---

## 一、架构定位

| 维度 | admin/tenant 端 | user 端 |
|------|----------------|---------|
| 前端 URL | `/admin/*` / `/tenant/*` | `/*`（根路径） |
| 后端 API | `/api/admin/*` / `/api/tenant/*` | **`/api/user/*`** |
| Token Scope | `admin` / `tenant_admin` | `tenant_user` |
| 依赖注入 | `ActiveAdmin` / `ActiveTenantAdmin` | **`ActiveTenantUser`** |
| Layout | `BasicLayout`（侧边栏 + 顶栏） | **`UserLayout`**（Layout A - Top Nav） |
| 设计风格 | 效率型管理后台 | 产品化/消费级（Notion/Linear 风格） |
| 移动端 | 次要考虑 | **核心支持**（responsive-first） |
| 品牌化 | 平台统一 | 企业品牌突出（Logo/站点名/主色调） |

---

## 二、UserLayout — Layout A · Top Nav

> ADR-7 已确认方案。原型文件：`frontend/user-layout-preview.html`

### 桌面端（>=768px）

```
┌─────────────────────────────────────────────────────────────┐
│  Logo + Brand  │  Home  AI Chat  Settings  │  🔔  👤  │  ← 56px 导航栏
├─────────────────────────────────────────────────────────────┤
│                                                             │
│              居中内容区 (max-width: 1100px)                   │
│              padding: 24px                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

- 56px 水平导航栏：Logo + Brand（企业配置）+ 导航链接（RBAC 动态菜单）+ 通知铃铛 + 用户头像下拉
- 居中内容区 max-width: 1100px，padding: 24px
- 用户头像下拉菜单：个人中心 / 修改密码 / 退出登录
- **无侧边栏**，导航在顶部水平排列

### 移动端（<768px）

- 导航链接隐藏，显示 hamburger 按钮（☰）
- 点击展开 slide-down drawer，列出所有导航项
- 统计卡片：桌面 4 列 → 移动 2 列 → 极小屏单列
- 2 列布局 → 移动端单列堆叠
- 可点击区域最小 **44x44px**

### 文件位置

```
frontend/apps/web-antd/src/
├── layouts/
│   ├── user.vue           ← UserLayout（Layout A - Top Nav）
│   └── user-auth.vue      ← 用户端认证布局（左品牌区 + 右表单区）
├── router/routes/
│   ├── core.ts            ← `/auth/*` 共享认证路由
│   └── user/index.ts      ← 用户端静态主路由（/、/ai-chat、/settings/*；/home 为 alias）
├── views/user/
│   ├── home/
│   │   └── index.vue
│   ├── ai-chat/
│   │   └── index.vue
│   ├── authentication/
│   │   ├── login.vue
│   │   ├── register.vue
│   │   └── forget-password.vue
│   ├── profile/
│   │   ├── index.vue
│   │   └── change-password.vue
│   └── settings/
│       └── index.vue
```

### 实现要点

```vue
<!-- user.vue 核心结构 -->
<template>
  <div class="min-h-screen bg-background">
    <!-- 顶部导航栏 -->
    <header class="sticky top-0 z-50 h-14 border-b bg-card/95 backdrop-blur">
      <div class="mx-auto flex h-full max-w-[1100px] items-center px-4 md:px-6">
        <!-- Logo + Brand -->
        <div class="flex items-center gap-2">
          <img :src="tenantConfig.logo" class="h-8 w-8" />
          <span class="text-lg font-semibold text-foreground">{{ tenantConfig.siteName }}</span>
        </div>
        <!-- 桌面端导航链接 -->
        <nav class="ml-8 hidden items-center gap-1 md:flex">
          <RouterLink v-for="menu in menus" :to="menu.path"
            class="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
            active-class="bg-primary/10 text-primary">
            {{ menu.title }}
          </RouterLink>
        </nav>
        <div class="ml-auto flex items-center gap-3">
          <!-- 通知 + 头像 + 移动端 hamburger -->
        </div>
      </div>
    </header>
    <!-- 内容区 -->
    <main class="mx-auto max-w-[1100px] px-4 py-6 md:px-6">
      <RouterView />
    </main>
  </div>
</template>
```

- 使用 Tailwind CSS + Vben 设计 Token
- 导航项从 RBAC 菜单 API 动态渲染（`GET /api/user/permissions/menus`）
- 高亮当前路由对应的导航项
- 品牌配置从 `publicConfigStore.tenantConfig` 读取

---

## 三、域名 → 企业 → 品牌加载流程

```
用户访问 https://abc.app.novusai.com/auth/login
    │
    ├─ 1. Router Guard 执行 detectDomainType()，确认当前域名属于 tenant user 端
    ├─ 2. 调用 loadTenantConfig() → GET /api/public/tenant/config
    │     └─ 后端 TenantMiddleware 从 Host 提取 tenant_code
    │     └─ 返回品牌/验证码/登录方式/安全策略
    ├─ 3. 前端应用品牌配置（logo/主题色/站点名）并同步到 Vben preferences
    ├─ 4. 登录 → POST /api/user/auth/login/json
    │     └─ 后端验证用户 + approval_status 检查
    └─ 5. 获取菜单 → GET /api/user/permissions/menus
```

### 前端关键代码

```typescript
// router/guard.ts — 新增 user 端分支
if (currentEndpoint === 'user') {
  await publicConfigStore.loadTenantConfig();
}
```

```typescript
// store/shared/public-config.ts — 新增 user 端状态
userLoginFailCount: 0,
userCaptchaRequired: false,
get shouldShowUserCaptcha() {
  return this.userCaptchaRequired || this.userLoginFailCount >= (this.tenantConfig?.captchaThreshold ?? 3);
}
```

---

## 四、用户端 RBAC

### 用户端权限端别（非资源作用域）

- JWT 常带 **scope=`tenant_user`**（令牌声明）。
- 权限表菜单/操作使用 **`PermissionScope.USER`**（`permissions.scope='user'`）。
- 以上均 **不是** `ResourceScopeEnum`（资源五类），禁止与技能包/插件资源 `scope` 混用。

### 后端菜单定义

```python
# backend/app/rbac/menus/user_menus.py
# 说明：保留 legacy dashboard 资源码，但 canonical route/component 已对齐当前前端根路由
USER_DIRECTORY_MENUS: list[PermissionMeta] = [
    PermissionMeta(
        code="menu:user.dashboard",
        name="menu.user.dashboard",
        type=PermissionType.MENU,
        scope=PermissionScope.USER,
        resource="menu",
        action="user.dashboard",
        icon="lucide:home",
        path="/",
        component="user/home/Index",
        sort_order=0,
    ),
]
```

### 后端 Controller 示例

```python
# 用户端 Controller（@auth_only / @public）
from app.core.deps import DbSession, ActiveTenantUser

class UserAuthController:
    """用户端认证控制器 — 不需要 @permission_resource"""

    @self.router.get("/me")
    @auth_only
    async def get_me(db: DbSession, user: ActiveTenantUser):
        return success(data=TenantUserResponse.model_validate(user))

    @self.router.post("/register")
    @public
    async def register(data: TenantUserRegisterRequest, db: DbSession, request: Request):
        tenant_ctx = get_tenant_context(request)
        # ...
```

### Permission 中间件扩展

```python
# permission.py — _load_permissions() 新增分支
elif token_scope == TOKEN_SCOPE_TENANT_USER:
    user = await get_current_tenant_user(db, token_data)
    user_permissions = await PermissionService.get_tenant_user_permissions(db, user)
```

### 前端 RBAC 对接

```typescript
// router/access.ts — user 端分支
if (endpoint === 'user') {
  const { menus, permissions } = await getUserMenusWithPermissionsApi();
  return { menus: transformMenus(menus, 'user'), permissions };
}
```

```typescript
// api/user/menu.ts
export function getUserMenusWithPermissionsApi() {
  return requestClient.get('/api/user/permissions/menus');
}
```

---

## 五、Token & API 路由

### Token 选择逻辑

```typescript
// utils/request.ts — Token 按 URL 前缀自动选择
/admin/*   → admin Token
/tenant/*  → tenant Token
/api/user/* → user Token    // ⚠️ 注意：是 /api/user/* 不是 /api/v1/*
```

### API URL 规范

所有用户端 API 使用 `/api/user/` 前缀（ADR-2）：

```typescript
// api/user/auth.ts
export function userLoginApi(data) {
  return requestClient.post('/api/user/auth/login/json', data);
}
export function userRegisterApi(data) {
  return requestClient.post('/api/user/auth/register', data);
}
export function getUserProfileApi() {
  return requestClient.get('/api/user/auth/me');
}
export function updateUserProfileApi(data) {
  return requestClient.put('/api/user/auth/profile', data);
}
export function forgotPasswordApi(data) {
  return requestClient.post('/api/user/auth/forgot-password', data);
}
export function resetPasswordApi(data) {
  return requestClient.post('/api/user/auth/reset-password', data);
}
```

---

## 六、响应式设计规范

### 断点

| 断点 | 宽度 | 说明 |
|------|------|------|
| `sm` | 640px | 小屏手机横屏 |
| `md` | 768px | **关键断点**：导航切换（桌面/移动端） |
| `lg` | 1024px | 平板/小笔记本 |
| `xl` | 1280px | 标准桌面 |
| `2xl` | 1536px | 大屏桌面 |

### 响应式模式

```vue
<!-- 统计卡片：4列 → 2列 → 1列 -->
<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">

<!-- 2列布局 → 单列 -->
<div class="grid grid-cols-1 gap-6 md:grid-cols-2">

<!-- 导航：桌面显示，移动端隐藏 -->
<nav class="hidden md:flex">

<!-- Hamburger：移动端显示，桌面隐藏 -->
<button class="flex md:hidden">
```

### 移动端必须遵守

- 可点击区域最小 **44x44px**
- 表单使用合适的 input type（`email` / `tel` / `number`）
- 禁止 hover-only 交互，移动端无 hover
- 固定底部按钮需留 safe-area-inset

---

## 七、认证页面规范

### Auth Layout (`user-auth.vue`)

- 左右分栏：左侧品牌区（渐变背景/插画）+ 右侧表单区
- 移动端：隐藏左侧品牌区，表单全宽
- Logo/站点名/标语从 `publicConfigStore.tenantConfig` 读取

### 登录页

- `onMounted` 调用 `publicConfigStore.loadTenantConfig()` 加载品牌
- 验证码条件显示：基于 `shouldShowUserCaptcha` getter
- 「忘记密码」链接 → `/forgot-password`
- 「立即注册」链接 → `/register`（根据企业配置判断是否显示）

### 注册页

- 字段：username / email / password / confirm_password / nickname（可选）
- 验证码（根据企业配置）
- approval_status 逻辑：approved → 自动登录；pending → 显示等待审批提示

### 忘记密码页

- 步骤 1：输入邮箱 → 发送验证码（60s 倒计时）
- 步骤 2：输入验证码 + 新密码 + 确认密码
- 密码强度指示器
- 成功后跳转登录页

---

## 八、用户端 i18n 文件结构

```
frontend/apps/web-antd/src/locales/langs/
├── zh-CN/
│   └── user/
│       ├── auth.json         # 登录/注册/忘记密码翻译
│       ├── dashboard.json    # 历史首页/AI 对话文案文件（仍承载 home/aiChat 语义）
│       ├── index.json        # 用户端翻译索引
│       ├── order.json        # 订单相关翻译
│       └── profile.json      # 个人中心翻译
├── en-US/
│   └── user/
│       ├── auth.json
│       ├── dashboard.json
│       ├── index.json
│       ├── order.json
│       └── profile.json
```

当前代码处于过渡态：

- 路由层使用 `user.home.*` / `user.aiChat.*` / `user.settings.*` / `user.profile.*` / `user.auth.*`
- 物理文件层仍保留 `dashboard.json` 这类 legacy 命名

规范要求：

- 新增页面或新文案时，**按当前页面语义命名 key**，不要继续扩散 `user.dashboard.*`
- 若后续做 i18n 收敛，应把物理文件命名与路由 key 语义统一，而不是继续叠加兼容层

---

## 九、Checklist

### 后端

- [ ] API 路径使用 `/api/user/*`（不是 `/api/v1/*`）
- [ ] 公开端点用 `@public`，登录后端点用 `@auth_only`
- [ ] 使用 `ActiveTenantUser` 依赖注入（不是 `ActiveTenantAdmin`）
- [ ] TenantMiddleware 生效路径含 `/api/user/`
- [ ] 注册/忘记密码端点有 IPRateLimiter 保护
- [ ] 登录时检查 `approval_status == "approved"`
- [ ] 注册时通过 `user_default_role_id` 配置分配默认角色

### 前端

- [ ] 用户端页面使用 `UserLayout`（不是 `BasicLayout`）
- [ ] 认证页面使用 `user-auth.vue` 布局
- [ ] Router Guard user 端加载 `loadTenantConfig()`
- [ ] Token 选择：`/api/user/*` → user Token
- [ ] 所有页面响应式适配（>=375px 宽度）
- [ ] 可点击区域最小 44x44px
- [ ] 导航从 RBAC 菜单 API 动态渲染
- [ ] i18n 文件在 `user/` 子目录，zh-CN + en-US 对齐
