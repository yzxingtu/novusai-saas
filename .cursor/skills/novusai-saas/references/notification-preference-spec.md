# 通知偏好治理规范

> 本文档覆盖 admin / tenant 端通知偏好的分层模型、接口、前端组件和扩展规则。通知投递链路本身见 [notification-spec.md](notification-spec.md)；这里聚焦“谁允许接收什么渠道”。

---

## 一、分层模型

通知偏好采用固定三层回退：

```text
individual override -> global preference -> hardcoded default
个人覆盖            -> 全局默认         -> 代码默认值
```

### user_type 映射

| 场景 | 全局 user_type | 个人 user_type | tenant_id |
|------|----------------|----------------|-----------|
| 平台管理端 | `platform_global` | `admin` | `0` |
| 企业管理端 | `tenant_global` | `tenant_admin` | 当前企业 ID |

### 固定分类与默认值

当前固定 5 类通知：

- `system`
- `ai`
- `task`
- `biz`
- `audit`

默认渠道值（缺记录时回退）：

```python
DEFAULT_PREF = {
    "channel_ws": True,
    "channel_inbox": True,
    "channel_email": False,
}
```

规则：

- 禁止在页面或业务服务里另写一套偏好回退逻辑
- 读取顺序必须统一通过 `NotificationPreferenceService`
- 新增分类时，必须同步更新 `CATEGORIES`、前端 i18n、UI 表格和种子模板使用方

---

## 二、数据模型

模型：`backend/app/models/common/notification_preference.py`

关键字段：

- `user_type`
- `tenant_id`
- `user_id`
- `category`
- `channel_ws`
- `channel_inbox`
- `channel_email`

唯一约束：

```python
UniqueConstraint(
    "user_type", "tenant_id", "user_id", "category",
    name="uq_notification_pref_v2",
)
```

规范：

- `user_id=NULL` 表示全局记录
- `tenant_id=0` 仅平台级使用
- 不要直接在 Controller/Service 手工 upsert `NotificationPreference`

---

## 三、后端接口

### 平台管理端

| 接口 | 说明 | 依赖 |
|------|------|------|
| `GET /admin/notification-preferences/global` | 获取平台全局偏好 | `SuperAdmin` |
| `PUT /admin/notification-preferences/global` | 更新平台全局偏好 | `SuperAdmin` |
| `GET /admin/notification-preferences` | 获取当前管理员偏好（含回退） | `ActiveAdmin` |
| `PUT /admin/notification-preferences` | 保存当前管理员个人偏好 | `ActiveAdmin` |
| `DELETE /admin/notification-preferences` | 重置为全局默认 | `ActiveAdmin` |

### 企业管理端

| 接口 | 说明 | 依赖 |
|------|------|------|
| `GET /tenant/notification-preferences/global` | 获取企业全局偏好 | `TenantOwner` |
| `PUT /tenant/notification-preferences/global` | 更新企业全局偏好 | `TenantOwner` |
| `GET /tenant/notification-preferences` | 获取当前企业管理员偏好（含回退） | `ActiveTenantAdmin` |
| `PUT /tenant/notification-preferences` | 保存当前企业管理员个人偏好 | `ActiveTenantAdmin` |
| `DELETE /tenant/notification-preferences` | 重置为全局默认 | `ActiveTenantAdmin` |

### 服务规则

统一通过 `NotificationPreferenceService`：

- `get_global_preferences()`
- `update_global_preferences()`
- `get_all_preferences()`
- `save_preferences()`
- `reset_individual_preferences()`

关键语义：

- 更新全局偏好后，只清除“发生变化的 category”对应的个人覆盖
- 个人偏好列表返回 `is_custom`，前端据此显示“跟随全局 / 已自定义”
- 全局更新后，后端会发出 `notification_preference:global_updated`

广播 room 规则：

- 平台端：`room="admins"`，`namespace="/admin"`
- 企业端：`room=f"tenant:{tenant_id}"`，`namespace="/tenant"`

---

## 四、前端集成

统一组件：`frontend/apps/web-antd/src/components/business/notification-panel/NotificationSettings.vue`

支持两种模式：

- `mode="personal"`：抽屉模式，显示 `is_custom`，支持“重置为全局”
- `mode="global"`：内联开关矩阵，供全局偏好页面嵌入

### API 前缀规则

```typescript
<NotificationSettings apiPrefix="/admin" mode="global" />
<NotificationSettings apiPrefix="/tenant" mode="personal" />
```

规则：

- 统一复用 `NotificationSettings.vue`
- 禁止在 admin / tenant 偏好页分别手写通知偏好表单
- 默认前缀推断只允许 `/admin` 或 `/tenant`，不要扩展到 user 端

### 交互语义

- 个人模式保存成功后关闭 Drawer
- 个人模式重置走 `DELETE /{base}/notification-preferences`
- 全局模式由宿主页面负责保存按钮与成功后的刷新策略

---

## 五、扩展规则

### 新增通知分类

必须同时修改：

1. `NotificationPreferenceService.CATEGORIES`
2. 前端 `NotificationSettings.vue` 的 `CATEGORIES`
3. 对应 i18n：`common.notification.category.{code}`
4. 模板种子与通知业务调用方

### 新增通知渠道

新增渠道不是只改通知驱动层，必须同时修改：

1. `NotificationPreference` 模型字段与迁移
2. `DEFAULT_PREF`
3. `NotificationPreferenceService` 读写逻辑
4. `NotificationSettings.vue` 表格列
5. [notification-spec.md](notification-spec.md) 中的渠道规则

---

## 六、禁止事项

- 禁止直接查询/更新 `notification_preferences` 表绕过服务层
- 禁止在业务通知发送代码中手工判断用户偏好
- 禁止页面散落 `requestClient.get('/admin/notification-preferences...')` 重复实现
- 禁止把通知偏好治理混入 `UserPreferenceService` 的 UI 偏好三层模型

---

## 七、Checklist

- [ ] 管理端/企业端都通过 `NotificationPreferenceService`
- [ ] 全局修改后会精确清除变更分类的个人覆盖
- [ ] 前端统一复用 `NotificationSettings.vue`
- [ ] 个人模式支持 reset to global
- [ ] 新增分类时同步更新后端常量、前端组件和 i18n
- [ ] 未把 user 端错误接入到该体系
