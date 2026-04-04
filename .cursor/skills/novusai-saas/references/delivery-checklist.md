# Delivery Checklist

在 NovusAI SaaS 中交付代码前，按任务类型至少过一遍以下清单。

## 后端

- [ ] Model 继承 `BaseModel` / `TenantModel`，并声明必要的 `__filterable__` / `__sortable__`
- [ ] 被 FK 引用的父实体声明 `__delete_deps__`
- [ ] 枚举比较使用 `.value`，不硬编码字符串
- [ ] Controller 不直接查库，不在 Controller 写业务判断
- [ ] Repository / Service / Controller 继承正确的基类
- [ ] Controller 已声明 `@permission_resource`，方法已声明 `@action_*`
- [ ] `@permission_resource` 已声明 `parent_resource`
- [ ] 新 action 的翻译追加到 `backend/app/locales/zh_CN/messages.json` 现有 `"action"` 节点内部
- [ ] 插件场景权限同步使用 `sync_plugin_permissions(plugin_name)`，不是全量 `sync_permissions()`
- [ ] 新增菜单页面后，菜单注册与前端页面组件都已补齐
- [ ] 响应统一使用 `success()` / `created()` / `paginated()` / `deleted()`
- [ ] 面向用户的后端文本已使用 `_()`
- [ ] 枚举已使用 `LabeledEnum`
- [ ] Alembic 迁移已生成
- [ ] 手写新 Model 已注册到 `models/__init__.py` 与 `migrations/env.py`
- [ ] 敏感信息不硬编码，改走环境变量或配置
- [ ] 时间写入遵循项目时间约定，避免混用 naive / aware datetime
- [ ] 手工 API dict / 导出载荷中的 datetime 没有直接 `.isoformat()` naive UTC；需要字符串时统一走 `serialize_datetime_for_api()`
- [ ] 新 Service 有对应测试，至少覆盖主要成功、失败与边界场景
- [ ] 公开敏感端点已有 `IPRateLimiter`
- [ ] AI 功能通过 `Agent -> Skill -> AIGateway` 链路接入
- [ ] 新增 AIModel / 能力字段后，过滤字段与相关查询已同步更新
- [ ] 迁移脚本中的外键使用显式名称，避免 downgrade 找不到约束
- [ ] Loguru 使用 `{}` 风格格式化
- [ ] 迁移或底层 SQL 未使用 `text(f\"...\")` 这种未参数化写法
- [ ] 没有 `except Exception: pass`
- [ ] 列表或导出查询有合理上限，避免无限量扫描
- [ ] 文件句柄、流和临时资源有正确关闭
- [ ] 依赖变更后已更新 `uv.lock`
- [ ] 循环引用类型按项目约定处理
- [ ] 新增注释、docstring、TODO/FIXME 满足项目语言规范
- [ ] 启用数据权限的实体显式声明 `__data_permission__ = True` 或具备可识别归属字段
- [ ] 强制下线、敏感写操作等端点的权限保护没有遗漏
- [ ] 新业务 Celery 任务使用 `@register_task`
- [ ] 新 CLI 子命令已接入统一入口 `app/cli.py`

## 前端

- [ ] 无业务 `any`
- [ ] 无 `console.log()`
- [ ] 无中文硬编码，全部走 `$t()`
- [ ] 业务上传统一使用 `smartUploadFile` 或业务封装组件
- [ ] 文件下载统一使用 `requestClient.download` + `downloadBlob`
- [ ] 搜索和表单 schema 使用辅助函数生成
- [ ] 业务预设写在 `data.ts`，不是 adapter
- [ ] 无跨端导入
- [ ] scope 字段统一走 `useScopeFields()` / `getScopeOptions()` / `ScopeSelect`
- [ ] 企业端资源可编辑判断基于 `tenant_id` / `owner_tenant_id`
- [ ] 中英文翻译键完整对齐
- [ ] Props 使用项目约定的类型化写法
- [ ] 新增页面后已检查无 `[MenuCheck]` 或 `[DynamicMenu] [CRITICAL]``
- [ ] 5xx 或统一错误弹窗路径仍能展示 trace_id
- [ ] `v-html` 绑定值已净化
- [ ] 事件监听没有退化成属性赋值式写法
- [ ] 请求错误只有一个前端展示 owner；若页面本地展示，已关闭 `showErrorMessage` / `showCodeMessage`
- [ ] 新接口没有继续引入 `200 + success=false + error/message/errors` 作为常规失败契约

## AI、WebSocket 与 trace_id

- [ ] 请求失败路径没有绕开统一错误处理
- [ ] trace_id 在日志、错误响应与前端展示链路上是一致的
- [ ] dev / prod 对错误详情和 trace_id 的展示差异符合当前规范
- [ ] 至少拿一个真实 `trace_id` 跑过 `novusai trace show <trace_id>`，确认 CLI 仍能查到上下文
- [ ] 若验证生产 / 预发语义，默认检查脱敏输出；只有确有必要时才走 `--unsafe` + `NOVUSAI_ALLOW_UNSAFE_TRACE=1`
- [ ] 页面感知改动已验证 `page_key`、确认流和超时路径
- [ ] AI 工具执行日志、页面操作日志或调用日志没有漏打
- [ ] 流式对话、异常中断和供应商报错路径已做回归
- [ ] 若改动涉及 `call_log_service` / `billing_context` / `tasks.ai.log_ai_call`，已确认 `AICallLog` 仍正常落库，且 Worker 已按新代码重启

## 回归与交付

- [ ] 代码改动已经按任务类型做过真实接口或页面回归
- [ ] 关键 reference 或专用 skill 已同步更新，没有把新约束只写在脑子里
- [ ] `.cursor` 里的 skill / rule / reference 导航仍然可达，没有断链
- [ ] 最终说明里能明确指出影响范围、验证结果和剩余风险
