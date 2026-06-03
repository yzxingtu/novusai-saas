# Token 吊销与强制下线规范

本文档覆盖：Redis key 格式、Token 生命周期、revoke/is_token_revoked 使用方式、强制下线 API、前端 Socket.IO 事件、兼容性说明。

---

## 一、Redis Key 格式

| Key | 类型 | TTL | 用途 |
|-----|------|-----|------|
| `token_blacklist:{jti}` | String (value="1") | token 剩余有效时间 | 已吊销 token |
| `active_tokens:{user_type}:{user_id}` | Hash {access_jti: refresh_jti} | 7 天 | 用户活跃 token 追踪 |

---

## 二、Token 生命周期

```
登录 → HSET active_tokens → 使用 → 登出/强制下线 → revoke_token + HDEL
```

---

## 三、函数使用方式

```python
from app.core.security import revoke_token, is_token_revoked

# 吊销 token
revoke_token(jti, ttl)  # ttl = token 剩余有效秒数

# 检查是否已吊销（decode_token 内部自动调用）
if is_token_revoked(jti):
    raise ...  # 拒绝
```

---

## 四、强制下线 API 端点

| 端点 | 权限 |
|------|------|
| `POST /admin/users/{user_id}/force-logout` | admin_user:force_logout |
| `POST /admin/tenants/{tenant_id}/admins/{admin_id}/force-logout` | tenant_admin:force_logout |
| `POST /tenant/users/{user_id}/force-logout` | tenant_user:force_logout |

---

## 五、前端 Socket.IO force_logout 事件

- 三个命名空间（`/admin`, `/tenant`, `/user`）均监听 `force_logout` 事件
- 收到后：`Modal.warning` 提示 → 用户确认 → `multiAuthStore.logout(true)` 跳转登录页

---

## 六、兼容性说明

- 旧 token（无 jti）自动跳过黑名单检查
- 旧 token 会在 24h（access）/ 7d（refresh）内自然过期

---

## 七、禁令

- 禁止在 Controller 中直接操作 Redis 黑名单，必须通过 `app.core.security` 中的函数
