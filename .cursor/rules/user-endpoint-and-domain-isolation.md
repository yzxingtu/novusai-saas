# 用户端与域名隔离规则

## 用户端定位

用户端面向 C 端业务用户，与 admin / tenant 端不是同一套页面和 API 约定。

## API 与依赖注入

- 用户端 API 前缀固定为 `/api/user/*`
- JWT 中常见 `scope=tenant_user` 表示用户端身份，不是 `ResourceScopeEnum`
- 权限表端别使用 `PermissionScope.USER`
- 依赖注入使用 `ActiveTenantUser`
- 公开端点使用 `@public`
- 登录后端点使用 `@auth_only`

## 前端布局

- 用户端必须使用 `UserLayout`
- 顶部导航 + 居中内容区，无侧边栏
- 当前 tenant/custom domain 下的用户端静态主路由为 `/`、`/agents`、`/ai-chat`、`/help`、`/settings/*`
- `/home` 仅保留为兼容 alias
- 平台域名下的 `/` 是 public gateway，仅在 tenant/custom domain 场景才跳转到 `UserHome`
- 认证页位于共享 `/auth/*`
- 品牌配置、验证码与域名识别统一走 `usePublicConfigStore`
- 验证码统一走 `CaptchaProvider`，不要在登录/注册页直接写死 image captcha 组件

## 域名矩阵

- 后端 `TenantMiddleware` 完全基于 Host header 解析企业
- 前端路由守卫统一先跑 `detectDomainType()`
- 企业域名禁止访问 `/admin/*`
- 平台域名禁止访问用户端页面
- 平台域名允许 `/tenant/*` 管理后台路由，但登录前只能使用平台 public config，不能无条件请求 `/api/public/tenant/config`
- tenant/custom domain 才允许请求 tenant public config，并驱动用户端品牌、验证码、注册开关等公开能力
- 请求客户端在开发模式下必须修正 API hostname，确保 Host header 正确

## Public Config 规则

- `loadTenantConfig()` 只能在 `detectDomainType()` 已确认 tenant/custom domain 后触发
- 平台域名下的 `/tenant/*` 不允许因为“先按路径猜 tenant 端”而预打 `/api/public/tenant/config`
- 用户端品牌来自 tenant public config；tenant admin 在平台域名下的登录前品牌来自 platform public config
- 任何页面都不要绕过 `usePublicConfigStore` 自己维护第二套域名或品牌判断

## 认证与 impersonate

- 用户端登录、注册、忘记密码都应从 Host 解析出的企业上下文取 `tenant_id`
- `tenant_code` 只作为向后兼容备用，不应成为主判定来源
- 用户端验证码复用 tenant public config，但失败计数独立维护为 `userLoginFailCount`
- `/tenant/impersonate` 仅传 `token`，禁止拼无效 `tenant_code`
- 注册、忘记密码等公开端点必须挂接 IP 限流

## RBAC

- 用户端菜单定义在 `user_menus.py`
- 使用 `PermissionScope.USER`（DB `permissions.scope='user'`，与资源作用域无关）
- 用户端大多数业务接口走 `@auth_only` / `@public`，不照搬 admin 端细粒度 CRUD 权限模型

## 参考

- [../skills/novusai-saas/references/user-endpoint-spec.md](../skills/novusai-saas/references/user-endpoint-spec.md)
- [../skills/novusai-saas/references/public-config-branding-captcha.md](../skills/novusai-saas/references/public-config-branding-captcha.md)
- [../skills/novusai-saas/references/tenant-domain-isolation.md](../skills/novusai-saas/references/tenant-domain-isolation.md)
