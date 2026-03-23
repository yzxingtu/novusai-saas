# 用户端与域名隔离规则

## 用户端定位

用户端面向 C 端业务用户，与 admin / tenant 端不是同一套页面和 API 约定。

## API 与依赖注入

- 用户端 API 前缀固定为 `/api/user/*`
- JWT 中常见 **scope=`tenant_user`**（令牌声明）表示**用户端身份**，**不是** `ResourceScopeEnum`；权限表端别用 **`PermissionScope.USER`**（`user`），二者均与资源五类作用域无关
- 依赖注入使用 `ActiveTenantUser`
- 公开端点使用 `@public`
- 登录后端点使用 `@auth_only`

## 前端布局

- 用户端必须使用 `UserLayout`
- 顶部导航 + 居中内容区，无侧边栏
- 当前前端静态主路由为 `/`、`/ai-chat`、`/settings/*`，其中 `/home` 仅保留为兼容 alias；认证页位于共享 `/auth/*`
- 设计与交互以移动端优先
- 可点击区域最小 44x44px
- 品牌配置来源于企业配置，不要在用户端写死 Logo / 主色 / 站点名
- 公开配置与域名识别统一走 `usePublicConfigStore.detectDomainType()` / `loadTenantConfig()`
- 验证码统一走 `CaptchaProvider`，不要在登录/注册页直接写死 image captcha 组件

## 域名隔离

- 后端 `TenantMiddleware` 完全基于 Host header 解析企业
- 前端路由守卫通过 `detectDomainType()` 判定企业域名或平台域名
- 企业域名禁止访问 `/admin/*`
- 平台域名禁止访问 `/tenant/*` 和用户端页面
- 请求客户端在开发模式下必须修正 API hostname，确保 Host header 正确

## 认证与 impersonate

- 用户端登录、注册、忘记密码都应从 Host 解析的企业上下文取 `tenant_id`
- `tenant_code` 只作为向后兼容备用，不应成为主判定来源
- 用户端验证码使用企业公开配置，但失败计数是独立的 `userLoginFailCount`
- `/tenant/impersonate` 仅传 `token`，禁止拼无效 `tenant_code`
- 注册、忘记密码等公开端点必须挂接 IP 限流

## RBAC

- 用户端菜单定义在 `user_menus.py`
- 使用 `PermissionScope.USER`（DB `permissions.scope='user'`，与资源作用域无关）
- 用户端大多数业务接口走 `@auth_only` / `@public`，不照搬 admin 端细粒度 CRUD 权限模型

## 参考

- `../skills/novusai-saas/references/user-endpoint-spec.md`
- `../skills/novusai-saas/references/public-config-branding-captcha.md`
- `../skills/novusai-saas/references/tenant-domain-isolation.md`
