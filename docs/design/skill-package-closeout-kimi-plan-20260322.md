# SkillPackage 收尾执行方案（给 KIMI）

## 1. 这份文档的用途

这是一份给 KIMI 直接执行的任务方案，目标不是继续大范围重构，而是把当前 `SkillPackage` 信息架构收口这条线一次性收尾。

这份方案解决三个问题：

1. 告诉 KIMI 先读什么，避免它重新摸上下文。
2. 告诉 KIMI 现在真正该做什么，避免它跑偏到 dashboard、插件 UI、美化或无关迁移问题。
3. 告诉 KIMI 哪些地方不能碰，避免它误修历史迁移或把已经收口的语义重新改回去。

---

## 2. 当前状态摘要

当前仓库里，`SkillPackage` 这条线已经完成了大部分结构性收口，现状如下：

### 2.1 已经成立的架构真相

- `SkillPackage` 现在是：
  - 归组单元
  - 来源单元
  - 目录/展示单元
- Agent 运行时能力真相不是包级绑定，而是：

```text
Agent
  -> AgentSkillGrant
  -> Skill
  -> SkillResolver
  -> ToolDefinition / RAG 元数据 / 其它执行元数据
```

- 不允许重新引入：
  - `SkillPackage auto-bind`
  - `AgentSkillBinding` 作为当前运行时真相
  - “整包天然生效”语义

### 2.2 已经落地的能力

- 管理端 `SkillPackage` 列表/详情已经切到规范化摘要字段
- 企业端已经有只读 `SkillPackage` 目录页与详情页
- 企业端允许查看：
  - 包角色
  - 来源摘要
  - 包内技能
  - 解析后的工具列表
- 企业端不允许：
  - SkillPackage CRUD
  - valves 编辑
  - 导入导出 / 克隆
  - 包级运行绑定

### 2.3 刚修掉的回归

刚刚修复了一条直接属于这次收口改造的回归：

- 报错：`column skill_packages.bind_mode does not exist`
- 根因：ORM model 还把 `bind_mode` 当成数据库真实列，导致管理端列表查询生成了错误 SQL
- 已处理：
  - 从 `SkillPackage` model / schema / service / summary payload / frontend API type 的 live path 中移除了 `bind_mode`
  - 当前 `select(SkillPackage)` 生成的 SQL 已不再包含 `skill_packages.bind_mode`

### 2.4 当前最合适的下一步

当前最合适的下一步不是继续改 dashboard，也不是再发散到插件 widget，而是：

1. 做 `SkillPackage` 这条线的真实链路验收
2. 清理剩余 live docs / rules / skill 规范中的残留旧语义
3. 形成一份明确、稳定、可交接的最终规范

---

## 3. 本次任务的明确目标

KIMI 这次要完成的是：

1. 验证管理端与企业端 `SkillPackage` 链路已经可用
2. 验证 `bind_mode` 不再出现在 `SkillPackage` 的运行时数据模型和 API 契约里
3. 把 rules / skill / architecture 文档里与当前真相不一致的 live 文案收口
4. 保证改动不碰无关迁移问题，不把历史兼容语义重新写回 live path

做到这里，这条“剩余 SkillPackage 信息架构继续收口”的主线才算真正结束。

---

## 4. 明确不在本次范围内的事项

以下内容不要碰，除非它们直接阻塞本次 `SkillPackage` 验收：

### 4.1 不处理的迁移问题

- `Initial migration - relation "permissions" already exists`
- 启动时 Alembic 跑到历史初始迁移的重复建表问题
- 任何“历史环境污染 / 数据库已半初始化 / 旧版本 stamp 不一致”的问题

这些问题不是这条 `SkillPackage` 收口线的直接产物，不要在这次任务里扩散修复。

### 4.2 不处理的 UI 扩展线

- 插件 dashboard widget 区域是否“更有内容”
- weather plugin 前端 widget 是否补齐
- 管理端 / 企业端 dashboard 的插件插槽体验优化

这些是另一条线，和本次 `SkillPackage` 信息架构收尾不是同一任务。

### 4.3 不清理的历史痕迹

以下可以保留，不要为了“全文无旧词”去误改历史语义：

- Alembic migration 历史文件
- 历史审计报告
- 仅用于历史恢复/兼容的测试
- locale 中暂未使用的旧翻译 key
- 其它纯历史说明性文档

原则是：

- 改 live path
- 不追着历史快照文件“洗白”

---

## 5. KIMI 必读文件顺序

KIMI 开始前，按下面顺序读，不要跳读：

1. `docs/architecture/skill-package-architecture.md`
2. `backend/app/api/shared/_skill_package_summary.py`
3. `backend/app/api/admin/skill_packages.py`
4. `backend/app/api/tenant/skill_packages.py`
5. `backend/app/models/ai/skill_package.py`
6. `backend/app/services/ai/skill_package_service.py`
7. `frontend/apps/web-antd/src/api/admin/skill-packages.ts`
8. `frontend/apps/web-antd/src/api/tenant/skill-packages.ts`
9. `frontend/apps/web-antd/src/views/admin/ai/skill-packages/index.vue`
10. `frontend/apps/web-antd/src/views/admin/ai/skill-packages/detail.vue`
11. `frontend/apps/web-antd/src/views/tenant/ai/skill-packages/index.vue`
12. `frontend/apps/web-antd/src/views/tenant/ai/skill-packages/detail.vue`
13. `.cursor/rules/ai-architecture.md`
14. `.cursor/rules/novusai-saas.md`
15. `.cursor/rules/tenant-architecture.md`
16. `.cursor/skills/novusai-saas/SKILL.md`
17. `.cursor/skills/novusai-saas/references/ai-module.md`
18. `.cursor/skills/novusai-saas/references/plugin-spec.md`
19. `.cursor/skills/plugin-development/SKILL.md`
20. `docs/guides/plugin-developer-guide.md`

---

## 6. 执行步骤

严格按顺序执行，不要先改代码再理解边界。

### Step 1. 先确认当前 live truth

要确认三件事：

1. `SkillPackage` 现在的职责是归组 / 来源 / 目录
2. 运行时真相是 `AgentSkillGrant -> Skill`
3. `runtime_binding_mode = direct_agent_skill_grant` 是现在 API 应该对外表达的真相

如果 KIMI 读完代码后得出的结论不是这三条，说明它理解偏了，必须先纠正理解再动手。

### Step 2. 做链路验收，不先扩散改代码

先验收以下 API / 页面链路：

#### 管理端

- `GET /admin/ai/skill-packages`
- `GET /admin/ai/skill-packages/{id}`
- `GET /admin/ai/skill-packages/{id}/skills`
- `GET /admin/ai/skill-packages/{id}/resolved-tools`
- 管理端页面：
  - `/admin/ai/skill-packages`
  - `/admin/ai/skill-packages/:id`

#### 企业端

- `GET /tenant/ai/skill-packages`
- `GET /tenant/ai/skill-packages/available`
- `GET /tenant/ai/skill-packages/{id}`
- `GET /tenant/ai/skill-packages/{id}/skills`
- `GET /tenant/ai/skill-packages/{id}/resolved-tools`
- 企业端页面：
  - `/tenant/ai/skill-packages`
  - `/tenant/ai/skill-packages/:id`

#### 验收时必须观察的点

- 页面能加载，不因字段缺失报错
- API 返回里有：
  - `package_role_key`
  - `source_summary`
  - `runtime_binding_mode`
  - `valves_field_count`
  - `configured_valves_count`
- `runtime_binding_mode` 应固定呈现 `direct_agent_skill_grant`
- SkillPackage 的 live response 不应再依赖 `bind_mode`
- 企业端页面必须保持只读，不允许冒出编辑、删除、clone、导入导出、valves 修改入口

如果验收时发现新问题，只处理与这条线直接相关的问题，不要扩散。

### Step 3. 扫描 live path 是否还有残留旧语义

重点扫描：

- `bind_mode`
- `SkillPackage auto-bind`
- `AgentSkillBinding`
- `SystemAgentService`

扫描命令建议：

```powershell
rg -n "bind_mode|AgentSkillBinding|auto-bind|SystemAgentService" . --glob '!backend/.venv/**' --glob '!**/node_modules/**' --glob '!**/dist/**'
```

但注意，不是搜到就全改。

只处理下面几类：

- live backend model / schema / service / controller / repository
- live frontend API type / page copy / page logic
- `.cursor/rules/*`
- `.cursor/skills/*`
- `docs/architecture/*`
- `docs/guides/*`

不要去重写：

- migration 历史
- 历史 audit 报告
- 兼容恢复类测试
- 与当前 SkillPackage 主线无关的 agent 旧概念文档

### Step 4. 如果发现 live docs / rules 还不够清晰，补最终规范

KIMI 这一步不是大改，而是做“最后一锤定音”的文案收口。

需要明确写清楚三件事：

1. `SkillPackage` 是归组 / 来源 / 目录单元
2. Agent 的运行时能力真相是直接 Skill 授权，不是包级自动绑定
3. 插件 manifest 到 `Skill/Capability` 的映射必须显式声明，不允许继续靠一个 weather 样板暗示语义

建议重点核对这些文件：

- `.cursor/rules/ai-architecture.md`
- `.cursor/rules/novusai-saas.md`
- `.cursor/rules/tenant-architecture.md`
- `.cursor/skills/novusai-saas/SKILL.md`
- `.cursor/skills/novusai-saas/references/ai-module.md`
- `.cursor/skills/novusai-saas/references/plugin-spec.md`
- `.cursor/skills/plugin-development/SKILL.md`
- `docs/guides/plugin-developer-guide.md`
- `docs/architecture/skill-package-architecture.md`

### Step 5. 必做静态校验

至少执行：

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

如果前端类型检查失败，只修和本次 `SkillPackage` 收尾直接相关的问题。

### Step 6. 如果服务已运行，补做一条运行时确认

建议至少确认一次 ORM 查询不再包含 `bind_mode` 列：

```powershell
@'
from sqlalchemy import select
from app.models.ai.skill_package import SkillPackage
print(sorted(SkillPackage.__table__.columns.keys()))
print(select(SkillPackage))
'@ | .\.venv\Scripts\python -
```

期望：

- 列集合里没有 `bind_mode`
- 生成的 `SELECT skill_packages ...` SQL 中没有 `skill_packages.bind_mode`

---

## 7. 明确的完成标准

只有同时满足下面全部条件，本次任务才算完成：

1. 管理端 `SkillPackage` 列表/详情链路可用
2. 企业端 `SkillPackage` 目录/详情链路可用
3. `SkillPackage` live model/schema/service/frontend API type 中不再把 `bind_mode` 当运行时字段
4. API 对外稳定使用规范化字段：
   - `package_role_key`
   - `source_summary`
   - `runtime_binding_mode`
   - `valves_field_count`
   - `configured_valves_count`
5. 企业端仍然是只读目录，不被误改成运行时绑定入口
6. rules / skill / architecture / guide 文档中，live 规范与当前真相一致
7. 没有顺手去修无关 migration / dashboard / plugin widget 线

---

## 8. 交付时必须给出的结果

KIMI 完成后，必须给出这 4 类信息：

### 8.1 改了哪些文件

按“后端 / 前端 / 规则文档”三组列出，不要只说“做了若干修改”。

### 8.2 做了哪些验证

至少写清：

- 哪些 `py_compile` 跑过
- `vue-tsc` 是否通过
- 哪些接口 / 页面实际验过
- ORM 的 `select(SkillPackage)` 是否确认不再含 `bind_mode`

### 8.3 还有哪些残留但故意没动

例如：

- migration 历史里还会出现 `bind_mode`
- locale 里可能还留着旧翻译 key
- 某些历史 audit 文档仍然提到 `AgentSkillBinding`

这类残留要解释“为什么没动”，防止被误判成漏做。

### 8.4 风险与后续建议

如果还有下一步，建议只允许落在下面两条之一：

1. 插件 manifest 到 Skill/Capability 的标准映射继续扩充到更多插件样板
2. dashboard 插件内容接入改造走独立任务线处理

不要在本次交付里重新发散出新的大范围重构。

---

## 9. 给 KIMI 的硬性约束

### 必须遵守

- 优先基于现有实现收尾，不要推翻重做
- 不要把 `bind_mode` 重新引回 `SkillPackage` live path
- 不要把企业端 SkillPackage 目录改成可编辑
- 不要把 SkillPackage 重新写成运行时绑定真相
- 不要顺手处理无关迁移问题
- 不要为了“搜到旧词”就重写 migration / 历史报告

### 可以处理

- 与本次收尾直接相关的 API / 页面 / 类型 / 文档小修
- 验收中发现的直接回归
- rules / skill 规范中的 live 文案补强

---

## 10. 建议 KIMI 最终输出格式

建议 KIMI 用下面结构回复，便于人工快速验收：

```text
1. 结论
2. 已完成的改动
3. 验证结果
4. 故意未处理的历史残留
5. 后续建议（最多 2 条）
```

---

## 11. 本次任务的唯一正确主线

请 KIMI 始终记住下面这句话，不要偏：

> SkillPackage 是归组 / 来源 / 目录单元；Agent 的运行时能力真相是直接 Skill 授权。

