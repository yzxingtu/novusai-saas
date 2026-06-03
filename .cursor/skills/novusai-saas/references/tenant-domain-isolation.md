# 企业域名隔离规范

本文档覆盖：后端域名隔离中间件、前端域名检测与路由守卫隔离、请求客户端 Host header 修正、菜单空目录剪枝、以及常见死代码清理规范。

---

## 一、后端域名隔离架构

### 1.1 TenantMiddleware 工作流程

文件：`backend/app/middleware/tenant.py`

**完全基于 Host header 解析，无需 `tenant_code` 查询参数。**

```
请求 → 提取 Host header（去掉端口）
      ↓
   匹配子域名后缀？(如 .app.local / .app.novusai.com)
      ├── 是 → 按 Tenant.code 查询企业
      └── 否 → 按 TenantDomain.domain 查询自定义域名
               ↓
           注入 request.state.tenant_ctx = TenantContext(tenant_id, ...)
```

**控制器取企业 ID 方式**：
```python
tenant_ctx = get_tenant_context(request)
tenant_id_from_ctx = tenant_ctx.tenant_id if tenant_ctx and tenant_ctx.is_resolved else None
```

### 1.2 企业端认证端点（user/auth.py）

所有公开端点必须提取 `tenant_id_from_ctx`：

```python
@router.post("/login")
@public
async def login(db: DbSession, request: Request, ...):
    tenant_ctx = get_tenant_context(request)
    tenant_id_from_ctx = tenant_ctx.tenant_id if tenant_ctx and tenant_ctx.is_resolved else None
    result = await auth_service.login_tenant_user(
        ...,
        tenant_id_from_ctx=tenant_id_from_ctx,   # 域名优先
        tenant_code=data.tenant_code,             # 向后兼容备用
    )
```

**覆盖的端点**：`/login`（OAuth2 + JSON）、`/register`、`/forgot-password`、`/reset-password`

### 1.3 Impersonate 端点域名隔离

`/tenant/auth/impersonate` 完全基于 `impersonate_token` 自验证，天然域名隔离：

```python
result = await auth_service.verify_and_consume_impersonate_token(impersonate_token)
# 不需要传 tenant_code，token 内嵌了 tenant_id
```

---

## 二、前端域名隔离

### 2.1 请求客户端 Host header 修正

文件：`frontend/apps/web-antd/src/utils/request/instance.ts`

**Dev 模式下将 API URL 的 hostname 替换为当前页面 hostname，确保 API 请求携带正确 Host header。**

```typescript
const apiURL = (() => {
  if (import.meta.env.PROD) return rawApiURL;
  try {
    const parsed = new URL(rawApiURL);
    parsed.hostname = window.location.hostname;   // as.dakkii.cn:5666 → API 发到 as.dakkii.cn:8000
    return parsed.toString().replace(/\/+$/, '');
  } catch {
    return rawApiURL;
  }
})();
```

**原理**：访问 `as.dakkii.cn:5666` 时，API 请求的 `Host: as.dakkii.cn:8000`，后端 TenantMiddleware 通过 Host header 解析出企业。

### 2.2 域名类型检测（publicConfigStore.detectDomainType）

文件：`frontend/apps/web-antd/src/store/shared/public-config.ts`

**幂等检测：首次导航发 1 次 API 请求，后续读缓存。**

```typescript
async detectDomainType(): Promise<void> {
  if (this.isDomainDetected) return;                        // 已检测，直接返回
  try {
    const config = await getTenantPublicConfigApi();        // GET /api/public/tenant/config
    this.isDomainTenantDomain = true;                       // 200 → 企业域名
    if (!this.tenantConfig) {
      this.tenantConfig = config;
      this.tenantConfigLoaded = true;
      applyBrandConfig(config.brand);                       // 顺带填充配置缓存
    }
    this.isDomainDetected = true;
  } catch (error) {
    const err = error as { response?: { status?: number } };
    if (err?.response?.status === 404) {
      this.isDomainTenantDomain = false;                    // 404 → 平台域名
      this.isDomainDetected = true;
    }
    // 网络错误/500：isDomainDetected 保持 false，下次重试
  }
}
```

**状态语义**：

| `isDomainTenantDomain` | 含义 |
|------------------------|------|
| `true` | 企业域名（API 返回 200，找到企业） |
| `false` | 平台域名（API 返回 404，无企业） |
| `null` | 未检测完成（网络错误等，路由守卫不限制） |

### 2.3 路由守卫域名隔离规则

文件：`frontend/apps/web-antd/src/router/guard.ts`

**在守卫最前端（配置加载之前）执行：**

```typescript
// 幂等检测（首次发 1 次请求）
await publicConfigStore.detectDomainType().catch(() => {});

// 规则 1：企业域名禁止访问平台管理端
if (publicConfigStore.isDomainTenantDomain === true && currentEndpoint === 'admin') {
  return { path: LOGIN_PATHS.tenant, replace: true };
}

// 规则 2：平台域名禁止访问企业端/用户端
if (
  publicConfigStore.isDomainTenantDomain === false &&
  (currentEndpoint === 'tenant' || currentEndpoint === 'user')
) {
  return { path: LOGIN_PATHS.admin, replace: true };
}
```

**隔离规则表**：

| 域名类型 | 访问 `/admin/*` | 访问 `/tenant/*` 或 `/*` |
|---------|----------------|------------------------|
| 企业域名（200） | → `/tenant/login` | ✅ 正常 |
| 平台域名（404） | ✅ 正常 | → `/admin/login` |
| 未检测（网络错误） | ✅ 不限制（安全默认） | ✅ 不限制 |

---

## 三、菜单空目录剪枝

文件：`backend/app/rbac/services/permission_service.py`，方法 `_build_menu_tree`

**插件禁用后，其父目录菜单（如"工作台"）会变成无子菜单的空目录，应自动剪枝。**

**修复**：
```python
# 跳过空目录菜单：无组件（纯目录）+ 无子菜单 + 无操作权限
# 典型场景：插件禁用后其父目录（如"工作台"）变为空壳
if not perm.component and not children and not menu_permissions:
    continue
```

**适用范围**：`_build_menu_tree` 被 admin / tenant / user 三端共享调用，此修复同时生效。

**触发场景**：
- `工作台` 目录：NovusDoc 插件禁用/未安装时，不再显示
- 任何插件的父目录菜单：插件禁用后，若子菜单全部 `is_enabled=False`，父目录自动隐藏

---

## 四、Impersonate URL 规范

### 4.1 正确格式（仅传 token）

```typescript
// ✅ 正确：仅传 impersonate token
const targetUrl = `${getTenantOrigin(domain)}/tenant/impersonate?token=${encodeURIComponent(result.impersonateToken)}`;
```

### 4.2 禁止事项

```typescript
// ❌ 错误：tenant_code 参数是死代码，impersonate.vue 从未读取此参数
const targetUrl = `${getTenantOrigin(domain)}/tenant/impersonate?token=...&tenant_code=${row.code}`;
```

### 4.3 getTenantOrigin 实现

文件：`frontend/apps/web-antd/src/views/admin/tenant/list/index.vue`

```typescript
function getTenantOrigin(domain: string): string {
  if (!import.meta.env.DEV) {
    return `https://${domain}`;
  }
  // Dev 模式：替换为企业域名 + 当前页面端口（5666）
  const port = window.location.port;
  return `http://${domain}${port ? `:${port}` : ''}`;
}
```

---

## 五、API 端点规范

### 5.1 用户端认证路由

**当前正确路径**：`/api/user/auth/*`（文件：`app/api/user/auth.py`）

旧路径 `/api/v1/auth/*` 已废弃并删除（路由注册已从 `main.py` 移除）。

### 5.2 TypeScript baseRequestClient 类型转型

`baseRequestClient`（无拦截器）在 TypeScript 类型上返回 `T`，但运行时返回 `AxiosResponse<T>`，需要通过 `.data` 访问响应体。

**正确写法**（禁止 `as any`）：

```typescript
const response = await baseRequestClient.post<RefreshTokenResultRaw>(url, body);
const responseData = (response as unknown as { data: HttpResponse<RefreshTokenResultRaw> }).data;
if (responseData.code !== 0) { throw new Error(responseData.message); }
const raw = responseData.data;
```

---

## 六、CORS 生产环境注意事项

当前主干 `backend/app/main.py` 为支持**动态子域名 + 自定义域名**，直接使用：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

| 场景 | 现状 |
|------|------|
| 开发环境 | 不需要手工把每个租户域名填入 `CORS_ORIGINS` |
| 生产环境 | 当前主干同样依赖运行时代码中的动态宽松 CORS，而不是静态白名单 |

若未来要收紧 CORS，必须连同 tenant / user 自定义域名能力一起设计，不要只改配置文档或只加静态白名单。

---

## 七、安全检查清单

- [ ] 后端企业认证端点正确提取 `tenant_id_from_ctx`（不依赖 URL 参数）
- [ ] `impersonate_token` URL 仅包含 `token` 参数，无 `tenant_code` 死参数
- [ ] 前端 `instance.ts` Dev 模式替换 hostname（确保 Host header 正确）
- [ ] `publicConfigStore.detectDomainType()` 已在路由守卫中调用
- [ ] 路由守卫包含两条域名隔离规则（企业域名 ↔ 平台域名互斥）
- [ ] `_build_menu_tree` 包含空目录剪枝逻辑
- [ ] `app/api/__init__.py` 无废弃 `v1` 导入
- [ ] `app/api/v1/` 目录已删除
- [ ] `baseRequestClient` 使用 `as unknown as` 代替 `as any`
