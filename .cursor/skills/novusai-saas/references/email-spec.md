# 邮件发送规范

## 一、架构

```
Controller/Service → send_email_task.delay() → Celery Worker → EmailService → SMTP
                                                     ↓
                                              EmailLog（自动记录）
```

- **禁止在 Controller/Service 中直接调用 `EmailService.send()`**（会阻塞请求）
- **所有邮件必须通过 `send_email_task.delay()` 异步发送**
- 唯一例外：管理端测试邮件 API（同步调用，需要实时返回结果）

---

## 二、发送方式

```python
# ✅ 异步发送（推荐，所有业务场景）
from app.tasks.email import send_email_task

send_email_task.delay(
    to=["user@example.com"],
    subject="邮件主题",
    html_body="<h1>HTML 内容</h1>",
    text_body="纯文本回退",
    triggered_by="task_failure",  # manual/task_failure/password_reset/test/welcome/ssl_expiry
    tenant_id=tenant_id,          # 可选，关联企业
)
```

---

## 三、配置来源

| 配置项 | 存储位置 | 说明 |
|--------|----------|------|
| `email_enabled` | `system_config_values` (平台配置) | 全局开关，False 时静默跳过 |
| `email_smtp_host/port/encryption/username/password` | 同上 | SMTP 服务器参数 |
| `email_from_address/from_name` | 同上 | 发件人信息 |
| `tenant_email_notification` | 同上 (企业配置) | 企业级开关 |

---

## 四、触发来源枚举（triggered_by）

| 值 | 说明 | 模板 |
|----|------|------|
| `manual` | 管理端手动发送 | 用户自定义内容 |
| `test` | 测试邮件 | test_email.html |
| `task_failure` | 定时任务失败通知 | task_failure.html |
| `password_reset` | 密码重置 | password_reset.html |
| `welcome` | 企业创建欢迎邮件 | welcome.html |
| `ssl_expiry` | SSL 证书到期提醒 | ssl_expiry.html |

---

## 五、关键文件

| 文件 | 说明 |
|------|------|
| `services/common/email_service.py` | EmailService (async) + send_email_sync (Celery 专用) |
| `tasks/email.py` | send_email_task Celery 任务 |
| `models/system/email_log.py` | EmailLog 发送日志模型 |
| `api/admin/email_logs.py` | 管理端 API（日志列表 + 手动发送 + 测试） |
| `configs/definitions/platform/email.py` | 8 个平台配置项定义 |

---

## 六、规则

- 邮件发送失败**不影响主业务流程**（try/except 包裹，仅记录日志）
- 所有邮件自动记录到 `email_logs` 表（成功/失败/触发来源）
- `email_enabled=False` 时静默跳过，不报错
- 邮件内容禁止包含敏感信息（密码明文、Token 等）
- i18n：邮件相关错误消息使用 `email.error.*` key
