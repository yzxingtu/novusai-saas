# Public Config、品牌与验证码规范

> 本文档覆盖平台/企业公开配置、品牌注入、域名识别与验证码扩展。
> 适用范围：`/api/public/platform/config`、`/api/public/tenant/config`、`usePublicConfigStore`、`CaptchaProvider`、用户端/企业端登录前页面。

---

## 一、公开配置入口

### 平台公开配置

- 路径：`/api/public/platform/config`
- 文件：`backend/app/api/public/platform.py`
- 用途：平台域名登录页、平台品牌、平台安全策略、平台域名列表

### 企业公开配置

- 路径：`/api/public/tenant/config`
- 文件：`backend/app/api/public/tenant.py`
- 用途：企业域名品牌、登录方式、验证码、注册开关、公开存储配置

规则：

- 登录前页面只允许读公开配置接口
- 不要在登录页调用需要鉴权的 `/admin/*` 或 `/tenant/*` 配置接口

---

## 二、前端统一入口：usePublicConfigStore

文件：`frontend/apps/web-antd/src/store/shared/public-config.ts`

职责：

- 公开配置加载与 Promise 去重
- 平台域名 / 企业域名识别
- 品牌配置写入 `@vben/preferences`
- `favicon` 与 meta description 注入
- 各端登录失败计数与验证码显示条件管理

核心方法：

- `detectDomainType()`
- `loadPlatformConfig()`
- `loadTenantConfig()`
- `reset*LoginState()`
- `increment*LoginFail()`

禁止事项：

- 禁止在页面里各自缓存平台/企业品牌状态
- 禁止手写第二套域名探测逻辑
- 禁止绕过 store 直接把品牌写进 `preferences`

---

## 三、域名识别规则

`detectDomainType()` 是唯一合法入口。

当前职责：

1. 判断当前 Host 属于平台域名还是企业域名
2. 企业域名场景自动尝试 `getTenantPublicConfigApi()`
3. 平台域名场景加载平台公开配置
4. 设置 `isDomainTenantDomain` / `isDomainDetected`

因此：

- 平台域名禁止当作用户端主域
- 企业域名禁止直接渲染 admin 端入口
- 业务代码不要把 `tenant_code` 当成前端主判定条件
- `loadTenantConfig()` 只能在 `detectDomainType()` 已确认 tenant/custom domain 后触发
- 平台域名下的 `/tenant/*` 管理路由是合法场景，但登录前不能无条件请求 `/api/public/tenant/config`
- tenant/custom domain 才允许把 tenant public config 作为品牌、验证码、注册开关的真相来源

---

## 四、品牌配置注入规则

品牌配置通过 `applyBrandConfig()` 应用到全局 UI：

- `app.name`
- `logo.source` / `logo.sourceDark`
- `copyright.companyName`
- `copyright.icp`
- `theme.colorPrimary`
- `favicon`
- `meta[name='description']`

注意：

- 品牌标识始终覆盖，因为它不是个人偏好
- 主色采用快照缓存判断，避免每次导航都覆盖用户自己的主题色

开发时不要：

- 在 layout 里写死 Logo
- 在 auth 页面写死站点名
- 直接修改 `document.title` / `link[rel=icon]` 作为品牌主逻辑

---

## 五、各端页面接入

### 用户端

- `router/guard.ts` 先做 `detectDomainType()`
- `views/user/authentication/login.vue` / `register.vue` 主动加载 tenant config
- `layouts/user.vue`、`layouts/user-auth.vue` 读取 `tenantBrand`

### 企业端

- 平台域名下的 tenant admin 登录前页面使用平台 public config
- tenant/custom domain 下的 tenant 登录前页面才读取 tenant public config 与企业验证码配置

### 平台端

- 平台登录页读取平台公开配置

规则：

- 登录前页面必须以公开配置为真相来源
- 登录后后台页面的品牌展示也应复用已应用的 `preferences`
- 不要因为前端路径是 `/tenant/*` 就假定当前 host 一定存在 tenant context

---

## 六、验证码架构

### 前端

统一组件：`frontend/apps/web-antd/src/components/business/captcha/CaptchaProvider.vue`

统一注册表：

- `registerCaptchaProvider()`
- `getCaptchaProvider()`
- `getRegisteredCaptchaTypes()`

这意味着验证码不是“永远只有 image”。

规则：

- 页面层统一使用 `CaptchaProvider`
- 不要在登录页直接依赖 `CaptchaImageForm`
- 新验证码类型通过 registry 注册，不要在页面里写 `if provider === 'xxx'`

### 后端

统一注册表：`backend/app/captcha/registry.py`

默认提供者：

- `image`

因此：

- 新增验证码提供者应走 captcha registry
- 不要在业务 API 内部硬编码某个 provider 的实现类

---

## 七、验证码显示条件

`usePublicConfigStore` 为三端分别维护失败计数：

- `platformLoginFailCount`
- `tenantLoginFailCount`
- `userLoginFailCount`

并分别维护强制验证码标记：

- `platformCaptchaRequired`
- `tenantCaptchaRequired`
- `userCaptchaRequired`

特别注意：

- 用户端验证码复用企业公开配置，但失败计数独立
- 判断逻辑优先级是“后端强制”高于“失败阈值”

---

## 八、企业公开配置的特殊点

`/api/public/tenant/config` 不只是品牌，还包含：

- 登录方式
- 验证码开关、provider、难度、阈值
- 注册与审批开关
- 个人资料编辑开关
- 隐私政策 / 服务条款 URL
- 存储公开配置

且有平台 fallback：

- 企业未设置 logo / favicon / title 时，回退平台默认值
- 企业存储若走平台托管，公开存储配置也来自平台

不要把它理解成“只返回 logo 的轻量接口”。

---

## 九、文件索引

| 文件 | 职责 |
|------|------|
| `backend/app/api/public/platform.py` | 平台公开配置 |
| `backend/app/api/public/tenant.py` | 企业公开配置与域名验证信息 |
| `frontend/apps/web-antd/src/api/public/config.ts` | 公开配置 API 与 raw -> frontend 映射 |
| `frontend/apps/web-antd/src/store/shared/public-config.ts` | 公开配置 store |
| `frontend/apps/web-antd/src/components/business/captcha/*` | 前端验证码组件与 registry |
| `backend/app/captcha/*` | 后端验证码 provider 协议、registry、service |

---

## 十、检查清单

- [ ] 登录前页面是否只使用公开配置接口
- [ ] 是否统一通过 `usePublicConfigStore` 加载与识别域名
- [ ] 是否保证 `loadTenantConfig()` 只在 tenant/custom domain 场景触发
- [ ] 是否通过品牌注入更新 Vben preferences，而不是页面局部硬编码
- [ ] 是否统一使用 `CaptchaProvider`
- [ ] 新验证码类型是否走前后端 registry，而不是页面条件分支
- [ ] 用户端验证码逻辑是否使用 tenant config + 独立 user fail count
