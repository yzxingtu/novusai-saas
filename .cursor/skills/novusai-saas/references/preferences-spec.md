# 偏好设置规范

> 本文档覆盖 admin/tenant 端 UI 偏好系统，不含通知偏好。
> 适用范围：`/admin/preferences/*`、`/tenant/preferences/*`、`UserPreferenceService`、`useUserPreferenceStore`、`usePreferenceSync`、全局偏好页与实时预览。

---

## 一、分层模型

偏好系统是三层合并模型：

```
SYSTEM_DEFAULTS
  -> global preferences
  -> individual overrides
  -> effective preferences
```

后端统一由 `backend/app/services/common/user_preference_service.py` 实现。

作用域：

| 层级 | scope |
|------|------|
| 平台全局 | `platform_global` |
| 企业全局 | `tenant_global` |
| 平台管理员个人 | `admin` |
| 企业管理员个人 | `tenant_admin` |

---

## 二、后端 API

### Admin

- `/admin/preferences/global`
- `/admin/preferences/me`
- `/admin/preferences/defaults`

### Tenant

- `/tenant/preferences/global`
- `/tenant/preferences/me`
- `/tenant/preferences/defaults`

规则：

- 超级管理员才能改平台全局偏好
- 企业所有者才能改企业全局偏好
- 普通管理员只能改自己的 `me`

---

## 三、全局更新的特殊语义

全局偏好更新不是简单覆盖。

`update_global()` 会：

1. 过滤无效 key
2. 只识别真正变化的 key
3. 把变化的 key 从所有个人覆盖中精确清除
4. 返回“系统默认 + 全局值”合并后的结果

原因：

- 某个值已经升级为组织默认时，个人覆盖不应继续把旧值粘住

因此：

- 不要在别处再写一套“清理个人覆盖”的逻辑
- 全局页保存必须走正式 API，不要直接改表

---

## 四、系统默认与可管理 key

后端常量：

- `SYSTEM_DEFAULTS`
- `VALID_KEYS`
- `GLOBAL_ONLY_KEYS`

目前 `watermark_enable` / `watermark_content` 属于全局专属键，个人偏好不能覆盖。

规则：

- 前后端都必须尊重 `GLOBAL_ONLY_KEYS`
- 不要把 watermark 放到个人偏好同步里

---

## 五、前端状态与映射

统一入口：`frontend/apps/web-antd/src/store/shared/user-preference.ts`

职责：

- 从后端 flat key 映射到 `@vben/preferences`
- 管理当前生效偏好、全局偏好、加载状态
- 更新个人偏好、更新全局偏好、重置个人偏好

关键映射：

- 后端：flat key，如 `theme_mode`
- 前端：nested path，如 `theme.mode`

不要：

- 在业务页面里直接拼写 mapping 表
- 直接修改 localStorage 中的 `preferences` 相关 key 作为主保存方式

---

## 六、登录后同步

admin / tenant 登录成功后，会加载生效偏好并同步到 Vben UI。

流程：

1. 登录成功
2. `useUserPreferenceStore.loadPreferences(side)`
3. `_applyToVben()`
4. `usePreferenceSync().initSnapshot()`

规则：

- 登录后不要再额外写一遍“手动恢复主题/语言”
- 新增受管偏好项时，需同步更新映射表与表单组件

---

## 七、实时同步与 WS 事件

当平台或企业全局偏好更新后，后端会推送：

- 事件名：`preference:global_updated`
- Admin room：`admins`
- Tenant room：`tenant:{tenant_id}`

前端 `usePreferenceSync()` 会：

1. 更新本地 `preferences`
2. 把变更映射回 `@vben/preferences`
3. 刷新 server snapshot
4. 在短时间窗口内跳过反向“个人偏好同步”，避免刚收到全局变更又被写回个人覆盖

因此：

- 不要绕过 `usePreferenceSync()` 自己监听这个 WS 事件
- 不要把全局更新再当作个人偏好 diff 提交回后端

---

## 八、全局偏好页的实时预览

统一 composable：`frontend/apps/web-antd/src/composables/use-global-preference-page.ts`

行为：

- 页面打开时记录 Vben snapshot
- 表单改动实时应用到 Vben，形成 live preview
- 页面离开时若未保存，则回滚到 snapshot
- 通过 `globalPreviewActive` 阻断个人偏好自动同步

规则：

- 全局偏好页必须复用 `useGlobalPreferencePage`
- 不要自己再写一个“watch 表单 -> updatePreferences”的版本
- 离开页面必须能回滚未保存的预览

---

## 九、前端组件边界

### `PreferenceForm`

负责受管偏好字段的 UI 编辑。

### `NotificationSettings`

属于通知偏好，不要和 UI 偏好混为同一套存储逻辑。

### `CacheClearModal`

只负责清缓存，不是偏好系统主入口。

---

## 十、常见错误

| 错误 | 风险 |
|------|------|
| 直接改 localStorage 的 preferences key | 与后端生效偏好脱节 |
| 全局页不回滚 live preview | 用户离开页面后 UI 残留脏状态 |
| 忽略 `GLOBAL_ONLY_KEYS` | 个人偏好错误覆盖水印 |
| 收到 WS 全局更新后又立即回写个人偏好 | 把组织默认误写成个人覆盖 |
| 在业务页面自行维护 flat <-> nested 映射 | 多处漂移 |

---

## 十一、文件索引

| 文件 | 职责 |
|------|------|
| `backend/app/services/common/user_preference_service.py` | 分层合并、更新、清理个人覆盖 |
| `backend/app/api/admin/preferences.py` | 平台偏好 API |
| `backend/app/api/tenant/preferences.py` | 企业偏好 API |
| `frontend/apps/web-antd/src/store/shared/user-preference.ts` | 前端偏好 store 与映射 |
| `frontend/apps/web-antd/src/composables/use-preference-sync.ts` | Vben <-> backend 自动同步 |
| `frontend/apps/web-antd/src/composables/use-global-preference-page.ts` | 全局页实时预览与回滚 |
| `frontend/apps/web-antd/src/components/business/preference-form/PreferenceForm.vue` | 偏好表单 |

---

## 十二、检查清单

- [ ] 是否区分 UI 偏好与通知偏好
- [ ] 是否复用 `useUserPreferenceStore` / `usePreferenceSync`
- [ ] 是否遵守 `GLOBAL_ONLY_KEYS`
- [ ] 全局偏好页是否支持实时预览并在离开时回滚
- [ ] 是否避免直接读写 localStorage 作为权威来源
