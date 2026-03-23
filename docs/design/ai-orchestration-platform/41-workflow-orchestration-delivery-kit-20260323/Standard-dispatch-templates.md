# Workflow Orchestration 标准派工模板

## 1. 文档目的

这份文档用于给并行执行的 AI 下发下一轮任务。

目标不是“随便发一句继续做”，而是确保每次派工都同时说清楚：

1. 这个 AI 只能改哪些文件。
2. 这个 AI 绝对不能碰哪些文件。
3. 这一轮必须完成什么，不允许发散。
4. 完成后必须回什么内容，便于集成人继续推进。

这份模板默认适用于当前模块：

- `backend/plugins/workflow-orchestration/**`
- `docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/**`

并默认继承以下硬约束：

- 必须严格遵守本项目 `rules`、`skill`、代码规范、插件边界规范。
- 不得修改 `backend/app/**`。
- 不得向主系统前端源码落任何插件业务文件。
- 不得回退其他 AI 或用户已有修改。
- 遇到冻结文件需求时，不得越权直接改，必须写入 handoff 或等待 integrator。

---

## 2. 派工四要素

每次派工都必须包含以下 4 段。

### 2.1 写入范围

必须写成明确路径，最好精确到目录或文件。

例如：

- `backend/plugins/workflow-orchestration/backend/runtime/**`
- `backend/plugins/workflow-orchestration/frontend/src/views/admin/**`
- `docs/design/.../AI-2-handoff.md`

### 2.2 禁止范围

必须明确冻结文件和其他 AI 的 ownership 文件。

例如：

- `plugin.yaml`
- `frontend/src/index.ts`
- `frontend/src/api/index.ts`
- `frontend/src/locales/index.ts`
- 其他端页面
- `backend/app/**`

### 2.3 任务目标

必须是可执行的结果，不要写成空泛描述。

例如：

- 修复 `artifact_retention` 多租户存储上下文问题
- 收口 admin 前端对 `overview` 的 speculative 契约
- 更新 handoff 到当前仓库真相

### 2.4 交付要求

必须要求 AI 回以下内容：

1. 改了哪些文件
2. 做了什么验证
3. 还有哪些剩余风险
4. 是否需要 integrator 回填冻结文件

---

## 3. 通用派工模板

下面这份是任何 AI 都能直接套用的标准模板。

```text
你负责 [AI 编号] 下一步落地。

你不是一个人在代码库里，其他 worker 也在并行工作。
不要回退他人修改；遇到他人新增内容要兼容。

你的唯一写入范围：
- [路径 1]
- [路径 2]
- [路径 3]

禁止修改：
- [冻结文件 1]
- [冻结文件 2]
- [其他 AI ownership 文件]
- 任何 backend/app/**
- 主系统前端源码

任务目标：
1. [本轮目标 1]
2. [本轮目标 2]
3. [本轮目标 3]

执行要求：
1. 先读现有实现、现有 handoff、相关审计结论，再开始改。
2. 不要扩业务范围，只解决本轮指定问题。
3. 如需要修改冻结文件，不得越权修改，改为在 handoff 中写出精确回填片段。
4. 如发现跨 ownership 问题，只能记录到 handoff 或明确提出阻塞点。
5. 严格遵守本项目 rules、skill、代码规范、插件边界规范。

完成后必须返回：
1. findings / 修复点
2. 修改文件列表
3. 验证结果
4. 剩余问题
5. 是否需要 integrator 跟进
```

---

## 4. AI-1 专属模板

适用角色：

- 插件壳
- 模型
- 迁移
- AI-1 handoff 真相收口

```text
你负责 AI-1 下一步落地。

你不是一个人在代码库里，其他 worker 也在并行工作。
不要回退他人修改；遇到他人新增内容要兼容。

你的唯一写入范围：
- backend/plugins/workflow-orchestration/backend/models/**
- backend/plugins/workflow-orchestration/backend/migrations/**
- docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/AI-1-handoff.md

禁止修改：
- backend/plugins/workflow-orchestration/plugin.yaml
- backend/plugins/workflow-orchestration/backend/main.py
- backend/plugins/workflow-orchestration/backend/services/**
- backend/plugins/workflow-orchestration/backend/api/**
- backend/plugins/workflow-orchestration/frontend/**
- 任何 backend/app/**
- 任何冻结共享文件

任务目标：
1. 收口模型与迁移 drift，重点是模型声明与真实迁移口径一致。
2. 更新 AI-1-handoff 到当前仓库真相。
3. 不扩业务，只修壳层一致性问题。

执行要求：
1. 先审相关模型、迁移、当前查询使用，再决定是补迁移还是收缩模型声明。
2. 不要擅自补不清晰语义的 FK；如果 FK 策略不明确，把未决点写入 handoff。
3. handoff 必须纳入新增迁移、删除过时 caveat、说明当前 manifest/frontend 仍未接入宿主的真实状态。
4. 严格遵守项目 rules、skill、代码规范。

完成后必须返回：
1. 修了哪些 drift
2. 修改文件列表
3. 验证结果
4. 尚未解决的问题
5. 是否需要 integrator 或 AI-2 配合
```

---

## 5. AI-2 专属模板

适用角色：

- runtime
- service
- tenant/admin runtime API
- task
- runtime tests

```text
你负责 AI-2 下一步落地。

你不是一个人在代码库里，其他 worker 也在并行工作。
不要回退他人修改；遇到他人新增内容要兼容。

你的唯一写入范围：
- backend/plugins/workflow-orchestration/backend/runtime/**
- backend/plugins/workflow-orchestration/backend/services/**
- backend/plugins/workflow-orchestration/backend/api/**
- backend/plugins/workflow-orchestration/backend/tasks/**
- backend/plugins/workflow-orchestration/backend/tests/runtime/**
- docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/AI-2-handoff.md

禁止修改：
- backend/plugins/workflow-orchestration/plugin.yaml
- backend/plugins/workflow-orchestration/backend/models/**
- backend/plugins/workflow-orchestration/backend/migrations/**
- backend/plugins/workflow-orchestration/frontend/**
- 任何 backend/app/**
- 任何冻结共享文件

任务目标：
1. 修 runtime / service / task 的 correctness 问题。
2. 补齐对应测试。
3. 更新 AI-2-handoff 的真实契约与剩余集成需求。

执行要求：
1. 优先修真实逻辑错误，不要先做文档美化。
2. 所有 API 契约收口必须基于当前后端真实返回，不要继续扩大 speculative 字段。
3. 如需共享字段变更，写清楚对 AI-3 / AI-4 的影响。
4. 不得碰 models / migrations / plugin.yaml。
5. 严格遵守项目 rules、skill、代码规范。

完成后必须返回：
1. 修复点与对应文件
2. 新增或更新的测试
3. 执行过的 pytest 或静态验证结果
4. 仍需 integrator 回填的 routes / tasks / frozen files
5. 对 AI-3 / AI-4 的正式契约口径
```

---

## 6. AI-3 专属模板

适用角色：

- admin 前端
- admin API wrapper
- admin types
- admin locale

```text
你负责 AI-3 下一步落地。

你不是一个人在代码库里，其他 worker 也在并行工作。
不要回退他人修改；遇到他人新增内容要兼容。

你的唯一写入范围：
- backend/plugins/workflow-orchestration/frontend/src/views/admin/**
- backend/plugins/workflow-orchestration/frontend/src/api/admin.ts
- backend/plugins/workflow-orchestration/frontend/src/types/admin.ts
- backend/plugins/workflow-orchestration/frontend/src/locales/admin/**
- docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/AI-3-handoff.md

禁止修改：
- backend/plugins/workflow-orchestration/plugin.yaml
- backend/plugins/workflow-orchestration/backend/**
- backend/plugins/workflow-orchestration/frontend/src/views/tenant/**
- backend/plugins/workflow-orchestration/frontend/src/index.ts
- backend/plugins/workflow-orchestration/frontend/src/api/index.ts
- backend/plugins/workflow-orchestration/frontend/src/locales/index.ts
- 任何主系统前端源码
- 任何冻结共享文件

任务目标：
1. 收口 admin 前端和当前后端真实契约。
2. 修复 admin 页面的 correctness 问题，不再依赖空泛假设。
3. 更新 AI-3-handoff 到当前真实状态。

执行要求：
1. 不要继续扩页面范围，优先修契约、请求参数、fallback、显式未接入状态。
2. 遇到后端尚未提供的字段，不要假装有数据，改成明确“未接入”。
3. 对未知枚举 / 分类 / 可选字段，必须有稳定 fallback。
4. 不得修改插件入口和冻结共享文件。
5. 严格遵守项目 rules、skill、代码规范。

完成后必须返回：
1. 修复点与对应页面/API 文件
2. 修改文件列表
3. 静态验证结果
4. 仍依赖 integrator 接线的项目
5. 仍依赖 AI-2 收口的后端契约
```

---

## 7. AI-4 专属模板

适用角色：

- tenant 前端
- tenant API wrapper
- tenant types
- tenant locale

```text
你负责 AI-4 下一步落地。

你不是一个人在代码库里，其他 worker 也在并行工作。
不要回退他人修改；遇到他人新增内容要兼容。

你的唯一写入范围：
- backend/plugins/workflow-orchestration/frontend/src/views/tenant/**
- backend/plugins/workflow-orchestration/frontend/src/api/tenant.ts
- backend/plugins/workflow-orchestration/frontend/src/types/tenant.ts
- backend/plugins/workflow-orchestration/frontend/src/locales/tenant/**
- docs/design/ai-orchestration-platform/41-workflow-orchestration-delivery-kit-20260323/AI-4-handoff.md

禁止修改：
- backend/plugins/workflow-orchestration/plugin.yaml
- backend/plugins/workflow-orchestration/backend/**
- backend/plugins/workflow-orchestration/frontend/src/views/admin/**
- backend/plugins/workflow-orchestration/frontend/src/index.ts
- backend/plugins/workflow-orchestration/frontend/src/api/index.ts
- backend/plugins/workflow-orchestration/frontend/src/locales/index.ts
- 任何主系统前端源码
- 任何冻结共享文件

任务目标：
1. 收口 tenant 前端和当前后端真实契约。
2. 修复下载、动作 gating、动态 i18n fallback 等 correctness 问题。
3. 更新 AI-4-handoff 到当前真实状态。

执行要求：
1. 优先修用户真正会踩到的契约问题，不要继续扩布局。
2. 下载链路必须有稳定 fallback，不允许死按钮。
3. 动态枚举翻译必须在人类可读 fallback 和 i18n key 泄漏之间选前者。
4. 当 `can*` 缺失时，要按安全规则回退，而不是把危险动作默认点亮。
5. 不得修改插件入口和冻结共享文件。
6. 严格遵守项目 rules、skill、代码规范。

完成后必须返回：
1. 修复点与对应页面/API 文件
2. 修改文件列表
3. 静态验证结果
4. 仍依赖 integrator 接线的项目
5. 仍依赖 AI-2 收口的后端契约
```

---

## 8. Integrator 补充说明

如果你不是在给 AI-1 到 AI-4 派工，而是在给 integrator 派工，那么要额外强调：

1. integrator 负责冻结共享文件。
2. integrator 不能重写别人的业务实现，只能做接线、合并、冲突裁决和最终验证。
3. integrator 必须以 handoff 的精确回填片段为准，不要自行猜测导出名、页面名、locale prefix。

integrator 典型负责文件：

- `backend/plugins/workflow-orchestration/plugin.yaml`
- `backend/plugins/workflow-orchestration/frontend/src/index.ts`
- `backend/plugins/workflow-orchestration/frontend/src/api/index.ts`
- `backend/plugins/workflow-orchestration/frontend/src/locales/index.ts`
- `backend/plugins/workflow-orchestration/frontend/package.json`
- `backend/plugins/workflow-orchestration/frontend/vite.config.ts`

---

## 9. 推荐使用方式

推荐你每次派工都按这个顺序发送：

1. 先贴本轮审计结论摘要
2. 再贴对应 AI 的专属模板
3. 最后补一句当前轮次优先级

例如：

```text
本轮优先级：
先修 correctness，再做接线，不要扩新能力。

你负责 AI-2 下一步落地。
...
```

这样能显著减少以下问题：

- AI 越权改共享文件
- AI 只写 handoff 不修代码
- AI 继续扩页面而不收口契约
- AI 修了代码但不回验证结果

---

## 10. 一句话判断标准

如果一条派工消息里没有同时写清楚：

- 写入范围
- 禁止范围
- 本轮目标
- 交付要求

那这条派工消息就是不合格的。

