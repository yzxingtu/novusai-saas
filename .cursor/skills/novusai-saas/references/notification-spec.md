# 通知系统规范

## 一、架构概览

所有业务通知统一走 `NotificationService.send()`，通过渠道驱动层分发到多个渠道。

```
业务代码 → notify(db, template_code, recipients, data)
              │
              ├─ 查模板 → channels: ["ws", "inbox", "email"]
              ├─ 查用户偏好 → {channel_ws: true, channel_email: false}
              │
              └─ CHANNEL_REGISTRY 遍历
                   ├─ InboxChannel  → DB 写入
                   ├─ WSChannel     → Socket.IO emit
                   ├─ EmailChannel  → notification 队列 → send_notification_email
                   └─ WebhookChannel → (预留)
```

---

## 二、调用方式

**异步上下文**（Controller / Service）：
```python
from app.services.common.notification_service import notify

await notify(db, "ai.batch_complete", [("tenant_admin", user_id)], {"total": 500})
```

**同步上下文**（Celery 任务）：
```python
from app.services.common.notification_service import notify_sync

notify_sync("system.task_failure", [("admin", 1)], {"error": str(exc)})
```

**带富文本邮件**：
```python
await notify(db, "system.password_reset", [("tenant_admin", uid)],
    data={"user_name": "张三"},
    email_html=html_body, email_subject="密码重置")
```

---

## 三、模板编码规范

格式：`{category}.{event_name}`

| 分类 | 前缀 | 示例 |
|------|------|------|
| system | `system.` | `system.password_reset`, `system.maintenance` |
| ai | `ai.` | `ai.batch_complete`, `ai.quota_warning` |
| task | `task.` | `task.completed`, `task.failed` |
| biz | `biz.` | `biz.tenant_created`, `biz.plan_changed` |
| audit | `audit.` | `audit.suspicious_login` |

新增模板需在 `sio/notification_seeds.py` 的 `SEED_TEMPLATES` 中添加。

---

## 四、渠道 channels 配置

| 场景 | channels | 说明 |
|------|----------|------|
| 仅实时 | `["ws"]` | AI 对话完成等即时信息 |
| 实时+收件箱 | `["ws", "inbox"]` | 大多数业务通知（默认） |
| 收件箱+邮件 | `["inbox", "email"]` | 重要通知（任务失败、SSL 到期） |
| 仅邮件 | `["email"]` | 密码重置 |
| 全渠道 | `["ws", "inbox", "email"]` | 紧急安全通知 |

---

## 五、渠道启用优先级

```
能否发送 = notification_enabled (总开关)
          AND template.channels 包含该渠道
          AND user_preference 允许该渠道
          AND channel.is_enabled() (渠道自身开关)
```

---

## 六、扩展新渠道

1. 实现 `NotificationChannel` 子类（`channels/` 目录）
2. 在 `channels/__init__.py` 的 `_register_builtin_channels` 中注册
3. 更新需要该渠道的模板 channels 列表
4. `NotificationPreference` 自动支持 `channel_{code}` 偏好

---

## 七、队列规范

- 通知相关邮件走 `notification` 队列（`tasks/notification.py`）
- 手动/测试邮件走 `default` 队列（`tasks/email.py`）
- Worker 启动需监听 notification 队列：`celery -A app.celery_app worker -Q default,notification,...`

---

## 八、禁止事项

- ❌ 业务代码直接 `from app.tasks.email import send_email_task` 发邮件
- ❌ 通知逻辑中硬编码渠道（必须通过模板 channels 配置）
- ❌ 跳过 NotificationService 直接操作 Notification 表
- ✅ 手动发送邮件接口（`/admin/system/email-logs` 发送功能）保留直接调 `send_email_task`
