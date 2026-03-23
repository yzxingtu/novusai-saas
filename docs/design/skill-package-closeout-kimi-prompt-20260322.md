# 给 KIMI 的直接提示词

你现在接手的是 `SkillPackage` 信息架构收尾任务，不是新的大重构，也不是 dashboard / 插件 widget 改造任务。

先读这份执行方案：

- `E:/git_clone/novusai-saas-yudi/docs/design/skill-package-closeout-kimi-plan-20260322.md`

然后严格按方案执行。你的目标只有四个：

1. 验证管理端与企业端 `SkillPackage` 链路已经可用
2. 确认 `SkillPackage` 的 live path 不再把 `bind_mode` 当成运行时字段或数据库列
3. 清理 live rules / skill / architecture / guide 文档中与当前真相冲突的旧语义
4. 在不扩散到无关迁移和 dashboard 任务的前提下，把这条线一次性收尾

你必须先建立并保持下面这个架构真相：

```text
SkillPackage = 归组 / 来源 / 目录单元
运行时能力真相 = AgentSkillGrant -> Skill -> SkillResolver
```

换句话说：

- 不要把 `SkillPackage` 重新理解成运行时自动绑定单元
- 不要把 `AgentSkillBinding` 重新当成当前真相
- 不要把企业端 `SkillPackage` 目录改成可编辑入口
- 不要把 `bind_mode` 重新写回 `SkillPackage` 的 live model/schema/service/API type

这次任务明确不处理：

- Alembic 历史迁移重复建表
- 初始迁移脏库问题
- dashboard 插件内容改造
- weather plugin widget 接入
- 其它和 `SkillPackage` 信息架构收尾无关的 UI/迁移分支

你只允许修改两类内容：

1. 与本次 `SkillPackage` 收尾直接相关的后端 / 前端 / API 类型 / 页面逻辑
2. `.cursor/rules/*`、`.cursor/skills/*`、`docs/architecture/*`、`docs/guides/*` 中的 live 规范文案

你必须执行以下检查：

- 管理端：
  - `GET /admin/ai/skill-packages`
  - `GET /admin/ai/skill-packages/{id}`
  - `GET /admin/ai/skill-packages/{id}/skills`
  - `GET /admin/ai/skill-packages/{id}/resolved-tools`
  - 页面 `/admin/ai/skill-packages`
  - 页面 `/admin/ai/skill-packages/:id`
- 企业端：
  - `GET /tenant/ai/skill-packages`
  - `GET /tenant/ai/skill-packages/{id}`
  - `GET /tenant/ai/skill-packages/{id}/skills`
  - `GET /tenant/ai/skill-packages/{id}/resolved-tools`
  - 页面 `/tenant/ai/skill-packages`
  - 页面 `/tenant/ai/skill-packages/:id`

你必须确认：

- API 对外稳定使用这些规范化字段：
  - `package_role_key`
  - `source_summary`
  - `runtime_binding_mode`
  - `valves_field_count`
  - `configured_valves_count`
- `runtime_binding_mode` 呈现为 `direct_agent_skill_grant`
- 企业端保持只读目录，不出现 CRUD / clone / import-export / valves 编辑
- ORM 的 `select(SkillPackage)` 不再包含 `skill_packages.bind_mode`

你必须执行至少这些静态校验：

```powershell
backend\.venv\Scripts\python -m py_compile `
  backend/app/models/ai/skill_package.py `
  backend/app/schemas/ai/skill_package.py `
  backend/app/services/ai/skill_package_service.py `
  backend/app/api/shared/_skill_package_summary.py `
  backend/app/api/admin/skill_packages.py `
  backend/app/api/tenant/skill_packages.py
```

```powershell
pnpm exec vue-tsc --noEmit -p frontend/apps/web-antd/tsconfig.json
```

如果你需要扫描旧语义，只能按 live path 处理，不要去清洗历史文件：

```powershell
rg -n "bind_mode|AgentSkillBinding|auto-bind|SystemAgentService" . --glob '!backend/.venv/**' --glob '!**/node_modules/**' --glob '!**/dist/**'
```

你的最终回复必须包含：

1. 结论
2. 已完成的改动
3. 验证结果
4. 故意未处理的历史残留
5. 后续建议（最多 2 条）

请直接执行，不要先输出泛泛计划，也不要发散到其它任务线。
