# `.cursor` Skill / Rules 审计报告

审计时间：2026-03-20

审计范围：

- `.cursor/skills/*`
- `.cursor/rules/*`
- 根目录 `.cursorrules`
- 与上述规范直接相关的项目模块目录与参考文档

## 一、审计结论

本仓库在审计前的 `.cursor` 体系属于“基础可用，但规则层明显截断、技能入口覆盖不足”的状态：

1. `novusai-saas` 主 skill 已覆盖大多数核心模块，但 `.cursor/rules` 只抽取了前半段主题，导致插件、上传下载、通知/WebSocket、用户端、数据权限、trace/监控、测试等高风险模块没有独立规则落地。
2. 规则和技能内存在过时或失效引用，典型问题是仍然引用 `.windsurf/...`、`/SKILL workflow`，以及 `websocket-guide.md`、`database-migration-best-practices.md` 这类不存在的相对路径。
3. 技能层只有 4 个入口 skill，虽然主 skill 的 reference 很全，但插件开发、页面感知、测试验证、附件存储、用户端等高意图任务没有独立触发入口，命中粒度偏粗。
4. 仓库同时保留 `.cursorrules` 与 `.cursor/rules/*` 两套规范入口，若不显式声明主从关系，后续很容易漂移。

结论：

- **规则层在本次补充前不算完善。**
- **主 skill 基础质量合格，但 skill 入口覆盖不够细。**
- **本次补充后，关键缺口已补齐，进入“可持续维护”的状态。**

## 二、原始问题清单

### P0：规则层覆盖断层

主 skill `novusai-saas/SKILL.md` 已包含以下专题，但 `.cursor/rules` 没有对应落地或只有零散摘要：

- 上传与下载
- 异步任务、通知、邮件
- WebSocket 实时通信
- 用户端与域名隔离
- 插件系统
- RBAC 与数据权限
- 测试验证
- trace_id 与监控

影响：

- 后续开发极易只遵守“前半份规则”，在高风险模块重复踩坑
- Cursor/协作成员读到的规则集不完整

### P0：失效引用

发现的失效引用类型：

- `.cursor/rules/novusai-saas.md` 仍引用 `.windsurf/rules/ai-architecture.md`
- `.cursor/rules/novusai-saas.md` 仍引用 `.windsurf/workflows/references/*`
- `.cursor/rules/ai-architecture.md` 使用 `/SKILL workflow` 这种无落点描述
- `.cursor/skills/novusai-saas/SKILL.md` 链接 `websocket-guide.md`
- `.cursor/skills/novusai-saas/SKILL.md` 链接 `database-migration-best-practices.md`

影响：

- 文档跳转失败
- 规则引用失真，降低可执行性

### P1：skill 入口不足

审计前存在的 skill：

- `crud-codegen-workflow`
- `database-migration-best-practices`
- `novusai-saas`
- `websocket-guide`

缺少独立入口的高价值模块：

- 插件系统
- 测试验证
- 上传下载与附件存储
- 用户端开发
- AI 页面感知

影响：

- 这些任务只能依赖超大总 skill 命中
- 任务意图越具体，技能触发反而越不精准

### P1：旧入口与新入口并存但缺少声明

仓库同时存在：

- `.cursorrules`
- `.cursor/rules/*`

如果不声明“谁是总览、谁是正文”，后续维护会出现规则漂移。

### P1：规则内容与真实实现存在细粒度失真

第二轮按代码验真后，发现除了“缺文件”之外，还有几条规则本身写得不准确：

- **依赖注入名称失真**：`.cursorrules` 与 `.cursor/rules/novusai-saas.md` 使用了 `ActiveUser`，但真实代码是 `ActiveTenantUser`
- **日志规范写窄**：规则把日志入口写成只能用 `LogManager.get_logger(...)`，但真实代码和基础设施规范允许并推荐 `get_logger(__name__)` 与 `LoggerMixin`
- **上传规则过度绝对化**：规则把 `requestClient.upload` 写成全局禁令，但实际存在富文本编辑器这类基础设施封装，内部直连标准附件上传端点仍属于合法实现
- **Celery 规则过度绝对化**：规则把 `@celery_app.task` / `celery_app.task(...)` 写成全局禁令，但插件注册器等框架桥接层确实会动态注册 Celery task；真正应该禁止的是业务任务模块直接这样写
- **定时任务规则过死**：规则曾写成一律禁止 `beat_schedule`，但真实实现保留了系统级静态兜底任务，数据库配置优先覆盖
- **旧接口前缀残留**：部分 reference 仍残留 `/api/v1/*` 示例，但实际用户端与插件相关接口已迁移到 `/api/user/*`、`/admin/*`、`/tenant/*`

影响：

- 开发者如果严格按旧规则改造，可能会“修错方向”
- 这类问题比缺文档更隐蔽，因为看起来“有规则”，但规则不真

### P1：reference 文档仍存在旧实现叙述与代码双真相

继续深挖 `.cursor/skills/**/references/*.md` 后，发现问题不再只是“缺模块”，还包括“文档还在讲旧系统”：

- **`codegen-spec.md` 仍写成旧版 6 步向导**：真实实现已切换为 `builder.vue` 三栏可视化构建器（Palette + WYSIWYG + Property Panel）
- **`user-endpoint-spec.md` 部分示例失真**：
  - 菜单 scope 示例写成 `PermissionScope.USER`，真实代码是 `PermissionScope.TENANT_USER`
  - `api/user/menu.ts` 示例漏了真实 `/api/user/*` 前缀
  - 文件结构仍以 `dashboard/` 为主视角，但当前前端主路由实际是 `/home`、`/ai-chat`、`/settings/*`
- **`frontend-spec.md` 的请求示例不再符合当前平台规范**：
  - 仍示范 `requestClient.upload('/api/upload', ...)`，会误导业务页面绕过附件系统
  - SSE 示例仍用 `console.log(...)` 和旧的泛化 `/api/chat` 端点，偏离当前“无 `console.log` + 真实 AI Chat SSE 端点”规范
- **`platform-infrastructure.md` 的 SSE 示例也残留 `console.log('Stream ended')`**，与项目 no-console 规则冲突
- **代码自身存在“前后端双真相”**，文档不能假装不存在：
  - 前端用户端静态主路由是 `/home`（`frontend/apps/web-antd/src/router/routes/user/index.ts`）
  - 后端 `user_menus.py` 仍保留 `menu:user.dashboard` legacy 资源码，但当前真实路由已对齐 `/home`
  - `frontend/apps/web-antd/src/constants/endpoints.ts` 在审计初始时曾残留 `/api/v1/admin`、`/api/v1/tenant`，现已修正为 `/api/admin`、`/api/tenant`

影响：

- 这类问题会让 `.cursor` 文档失去“单一事实来源”能力
- 仅靠补文档无法完全消除，需要同时记录哪些地方是代码本身尚未统一的遗留兼容层

### P1：复杂模块已有实现，但 `.cursor` 仍缺专题文档

按代码目录与现有 `.cursor` reference 对照后，确认以下复杂模块此前没有独立 reference：

- **AI Writing**：`/admin|/tenant/ai/writing/{feature}`、`system.ai_writing` 分配、`useEditorAI()`、SSE 增量返回
- **Codegen Visual Builder**：`builder.vue`、`useCodegenBuilderStore`、WYSIWYG、属性面板、DB 导入、版本恢复
- **Public Config / Branding / Captcha**：`/api/public/platform|tenant/config`、`usePublicConfigStore`、域名识别、品牌注入、Captcha registry
- **Preferences Governance**：`UserPreferenceService` 三层模型、全局预览、WS `preference:global_updated`、flat key <-> Vben 映射
- **Notification Preference Governance**：`NotificationPreferenceService` 分层继承、全局覆盖精确清除、`NotificationSettings.vue`、`notification_preference:global_updated`
- **AI Action Logs**：`write_ai_action_log()`、`resolve_action_level()`、admin/tenant 审计页、`duration_ms` / `pending_confirm` 统一语义

影响：

- 这些模块虽然“代码可用”，但缺少 `.cursor` 专题文档时，二次开发很容易直接绕过既有基础设施
- 问题通常不是写不出代码，而是容易写出“能跑但偏离平台机制”的代码

## 三、本次补充内容

### 1. 修复与同步

已修复：

- `.cursor/rules/novusai-saas.md` 中的 `.windsurf/...` 失效引用
- `.cursor/rules/ai-architecture.md` 中的 `/SKILL workflow` 模糊引用
- `.cursor/skills/novusai-saas/SKILL.md` 中的坏链接
- `.cursorrules` 中的旧路径引用
- `ActiveUser` → `ActiveTenantUser` 的错误依赖注入命名
- 日志规范中对 `get_logger(__name__)` / `LoggerMixin` 的遗漏
- 上传规则对富文本编辑器等基础设施封装例外的遗漏
- Celery 规则对插件注册器等框架桥接层例外的遗漏
- 定时任务对 `beat_schedule` 的绝对化禁令
- WebSocket、backend/frontend spec、plugin 菜单注册、SSE 示例中的旧 `/api/v1/*` 路径
- `codegen-spec.md` 中仍把真实 Builder 写成 6 步向导的问题
- `user-endpoint-spec.md` 中 `PermissionScope.USER`、漏写 `/api/user/*` 前缀、仍以旧 `dashboard` 结构描述前端路由的问题
- `frontend-spec.md` 中直连上传、`console.log`、泛化 `/api/chat` SSE 示例的问题
- `platform-infrastructure.md` 中 SSE 示例仍使用 `console.log` 的问题
- `rbac-permission-spec.md` 中用户端菜单示例缺少 legacy 命名风险说明的问题
- `backend/app/ai/constants.py` 中 `MEMORY_ENABLED_SCENE` 注释与真实运行时允许场景不一致的问题
- `frontend/apps/web-antd/src/components/business/ai-chat-panel/use-ai-chat.ts` 中 `apiPrefix` 注释未包含 `/api/user` 的问题
- `frontend/apps/web-antd/src/constants/endpoints.ts` 中 admin/tenant API prefix 仍残留 `/api/v1/*` 的问题
- `novusai-saas/SKILL.md` 中对 codegen UI 仍写成向导、对公开配置/验证码/AI 写作/偏好设置缺少入口索引的问题
- `frontend/apps/web-antd/src/api/tenant/action-logs.ts` / `views/tenant/ai/action-logs/*` 中把后端 `duration_ms` / `pending_confirm` 写成 `execution_time_ms` / `pending` 的问题
- `.gitignore` 默认忽略 `.cursor/skills/*`，导致新增 skill 与 reference 默认无法纳入版本管理的问题

已补充：

- `.cursorrules` 明确为兼容旧版 Cursor 的总览入口
- `.cursor/rules/novusai-saas.md` 增加专题规则索引与缺失主题摘要
- `.gitignore` 现已显式放开 `.cursor/skills/**`，使技能与 reference 可进入版本管理

### 2. 新增规则文件

本次新增专题规则：

- `.cursor/rules/attachments-and-storage.md`
- `.cursor/rules/async-notification-websocket.md`
- `.cursor/rules/plugin-system.md`
- `.cursor/rules/rbac-and-data-permission.md`
- `.cursor/rules/user-endpoint-and-domain-isolation.md`
- `.cursor/rules/testing-validation.md`
- `.cursor/rules/trace-and-monitoring.md`

这些文件把原先只存在于主 skill reference 内的关键约束，落成了直接可读的 rules。

### 3. 新增 skill 入口

本次新增技能：

- `.cursor/skills/plugin-development/SKILL.md`
- `.cursor/skills/testing-validation/SKILL.md`
- `.cursor/skills/attachment-storage/SKILL.md`
- `.cursor/skills/user-endpoint/SKILL.md`
- `.cursor/skills/ai-page-awareness/SKILL.md`
- `.cursor/skills/ai-writing/SKILL.md`
- `.cursor/skills/session-memory/SKILL.md`
- `.cursor/skills/codegen-builder/SKILL.md`
- `.cursor/skills/preferences-governance/SKILL.md`

这些技能并不复制参考文档，而是把高频场景拆成独立入口，并回链到现有 reference。

### 4. 新增 reference 文档

本轮继续新增并补齐：

- `.cursor/skills/novusai-saas/references/ai-writing-spec.md`
- `.cursor/skills/novusai-saas/references/codegen-builder-spec.md`
- `.cursor/skills/novusai-saas/references/public-config-branding-captcha.md`
- `.cursor/skills/novusai-saas/references/preferences-spec.md`
- `.cursor/skills/novusai-saas/references/session-memory-spec.md`
- `.cursor/skills/novusai-saas/references/notification-preference-spec.md`
- `.cursor/skills/novusai-saas/references/ai-action-log-spec.md`

这些文档补上了前一轮仍缺失的复杂模块说明，并把旧实现叙述修正为当前代码真实形态。

本轮额外新增：

- `.cursor/skills/session-memory/SKILL.md`
- `.cursor/skills/novusai-saas/references/notification-preference-spec.md`
- `.cursor/skills/novusai-saas/references/ai-action-log-spec.md`

新增内容覆盖了此前仍缺失的会话记忆模块：

- 三层记忆开关（平台默认 / 管理端 Agent / 企业覆盖）
- `SessionMemoryService` 的 Redis CAS / 幂等 / TTL / conversation 级清理
- `memory-state` 查询/清空接口
- SSE `memory_updated` 与历史消息 metadata 恢复
- AI Writing / `stream_chat_ephemeral()` 不落会话记忆的边界

本轮继续补齐的复杂模块：

- 通知偏好分层治理：平台/企业全局默认、个人覆盖、精确清理受影响 category、统一 `NotificationSettings.vue`
- AI 操作审计日志：统一 helper 写入、Admin/Tenant 只读审计页、`duration_ms` / `pending_confirm` 真相收敛
- 企业端 AI 操作日志前端字段名已修正，避免前后端再次出现“双真相”

说明：

- 本次已同步调整 `.gitignore`，`.cursor/skills/**` 与其 reference 现可进入版本管理。
- 后续若要继续补技能或 reference，不再受“仅本地工作区可见”限制。

## 四、当前覆盖评估

### 规则层

当前 `.cursor/rules` 已覆盖：

- 全局开发规则
- AI 架构
- 菜单多语言
- 企业端能力边界
- 上传下载与存储
- Celery / 通知 / 邮件 / WebSocket
- 插件系统
- RBAC / 数据权限
- 用户端 / 域名隔离
- 测试验证
- trace_id / 监控
- AI 写作约束（并入 AI 架构规则）
- 会话记忆约束（并入 AI 架构规则）
- 公开配置 / 品牌 / 验证码约束（并入用户端规则）

结论：

- **关键缺失模块已补齐。**
- 对本项目当前模块结构来说，规则层已达到“完整可用”。 

### Skill 层

当前 `.cursor/skills` 已覆盖：

- 全栈总 skill
- CRUD / codegen
- 数据库迁移
- WebSocket
- 插件系统
- 测试验证
- 上传下载 / 附件存储
- 用户端
- AI 页面感知
- AI 写作
- 会话记忆
- Codegen Builder
- 偏好设置治理

结论：

- **技能入口已从“通用为主”提升为“通用 + 专题并存”。**
- 对常见开发任务已经足够细。

## 五、仍属于“建议增强”而非阻塞的问题

以下项目前不存在阻塞缺陷，但后续可以继续优化：

1. 若后续使用支持技能 UI 列表的运行环境，可考虑给 `.cursor/skills/*` 增加一致的展示层元数据。
2. 若后续插件、运维、通知类开发频率继续上升，可再把“监控运维”和“通知模板治理”拆成独立 skill。
3. 用户端 `home` 与后端 `dashboard` 菜单命名仍未统一，属于代码基线本身尚未统一的问题；后续应先定 canonical truth，再继续收敛文档与菜单资源。
4. 用户端 i18n 物理文件命名仍保留 `dashboard.json`，但路由与页面语义已转向 `home / ai-chat / settings`；这是另一处仍未完全统一的兼容层。
5. 如果团队仍有成员使用仅读取 `.cursorrules` 的旧版工具，建议后续定期检查 `.cursorrules` 与 `.cursor/rules/*` 是否同步。
6. `notification_preference:global_updated` 事件当前已在后端发出，但前端尚未形成与 `preference:global_updated` 同等级的统一实时同步机制；这属于代码层治理项，不再是 `.cursor` 文档缺口。

## 六、最终判断

审计前：

- `.cursor` skill 体系：**部分完善**
- `.cursor` rules 体系：**不完整**

审计并补充后：

- `.cursor` skill 体系：**完善，可按专题触发**
- `.cursor` rules 体系：**完整，且已覆盖当前系统关键模块**

补充说明：

- **文档层面的主要缺口已补齐。**
- **剩余风险已从“缺文档”收敛为“少数代码遗留兼容层与代码注释漂移尚未统一真相”。**
