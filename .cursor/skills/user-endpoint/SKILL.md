---
name: user-endpoint
description: NovusAI 用户端开发技能。当需要开发或修复 `/api/user/*` 接口、UserLayout 页面、企业域名隔离、用户端认证与品牌加载流程时，参考此技能。
---

# 用户端开发技能

## 何时使用

- 开发或修复用户端页面 `views/user/*`
- 开发或修复 `/api/user/*` 接口
- 处理用户端认证、菜单、品牌配置、域名隔离
- 排查 `tenant_user` 权限或用户端跳转问题

## 核心原则

- 用户端 API 前缀固定为 `/api/user/*`
- 依赖注入使用 `ActiveTenantUser`
- 布局使用 `UserLayout`
- 当前 **tenant 域名下** 的前端静态主路由为 `/`、`/agents`、`/ai-chat`、`/help`、`/settings/*`，其中 `/home` 仅保留为兼容 alias；平台域名下的 `/` 是 public gateway，仅在 tenant 域名场景才跳到 `UserHome`；认证页在共享 `/auth/*`
- 用户端是移动端优先，不照搬 admin / tenant 后台布局
- 企业识别基于 Host header，不以 `tenant_code` 参数为主
- 品牌、域名识别、验证码统一走 `usePublicConfigStore` + `CaptchaProvider`
- `loadTenantConfig()` 只能在 `detectDomainType()` 已确认 tenant/custom domain 后触发；平台域名下的 `/tenant/*` 登录或后台页禁止预打 `/api/public/tenant/config`
- 平台域名允许 tenant admin 后台路由，但登录前品牌与验证码只能使用 platform public config，不要把 tenant admin 场景误当成 tenant/custom domain

## 标准流程

1. 先确认问题是否属于 user 端，而不是 tenant 端复用
2. 检查路由、Layout、菜单、Token scope 是否都是 `tenant_user`
3. 检查 `TenantMiddleware` 和前端 `detectDomainType()` 是否协同工作
4. 检查品牌配置是否只在 tenant/custom domain 场景来自 `loadTenantConfig()`，以及平台域 tenant admin 是否仍使用 platform public config
5. 验证平台域名与企业域名的访问隔离，不要把“平台域禁止 user 页面”误写成“平台域禁止 tenant admin”
6. 若菜单或首页异常，同时检查前端 `/` 主路由、`/agents` / `/help` 静态页面、`/home` alias 与后端 legacy `menu:user.dashboard` 命名是否发生漂移

## 关键禁令

- 禁止把用户端接口挂到 `/api/v1/*` 或 `/api/tenant/*`
- 禁止在用户端使用后台侧边栏布局
- 禁止依赖 `tenant_code` 作为唯一企业识别方式
- 禁止在企业域名访问 admin 页面
- 禁止在平台域名访问用户端页面
- 禁止在平台域名下因为路径前缀是 `/tenant/*` 就预打 `/api/public/tenant/config`

## 参考

- [../novusai-saas/references/user-endpoint-spec.md](../novusai-saas/references/user-endpoint-spec.md)
- [../novusai-saas/references/public-config-branding-captcha.md](../novusai-saas/references/public-config-branding-captcha.md)
- [../novusai-saas/references/tenant-domain-isolation.md](../novusai-saas/references/tenant-domain-isolation.md)
