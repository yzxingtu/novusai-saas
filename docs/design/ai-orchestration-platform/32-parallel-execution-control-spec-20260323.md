# AI 编排平台 4 AI 并行执行控制规范（2026-03-23）

## 一、文档目标

本文档用于把 [31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md](./31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md) 中的并行交付方案，进一步收敛成可直接执行的操作规范。

这份文档重点解决以下问题：

1. 4 个 AI 实际开工时必须使用什么隔离方式。
2. 同时开发时，代码工作区、分支、提交、handoff、冻结文件分别怎么管。
3. 哪些行为会直接破坏并行安全，应被明确禁止。
4. 并行开发结束后，应如何冻结、移交和进入串行集成。

本文档不是产品规划，而是执行控制规范。

与 [35-coordinator-launch-and-delivery-runbook-20260323.md](./35-coordinator-launch-and-delivery-runbook-20260323.md) 配合使用时，本文档负责约束，并行启动作战手册负责落地执行步骤。

---

## 二、核心结论

### 2.1 4 个 AI 必须运行在独立工作副本中，禁止共用同一个工作目录

这是并行控制的第一原则。

即使文件边界写得很清楚，如果 4 个 AI 仍在同一个工作目录里做事，仍然会出现：

- 未跟踪文件互相覆盖
- 中间态代码被误读
- 格式化工具误扫全仓
- 一个 AI 清理文件时误删另一个 AI 的产物

所以并行执行时，必须采用以下任一方案：

1. `git worktree`
2. 独立克隆副本
3. 具备强隔离的独立沙箱工作目录

其中首选方案是 `git worktree`。

### 2.2 共享文件冻结只是第二层保护，不是第一层保护

共享文件冻结是必要的，但它不能替代工作副本隔离。

也就是说：

- 先做工作副本隔离
- 再做共享文件冻结
- 最后做 handoff 串行集成

顺序不能反过来。

### 2.3 每个 AI 必须有明确的负责人编号、工作目录、分支名、handoff 文件

不能只说“你负责这一块”。

必须正式绑定：

- `AI 编号`
- `工作目录`
- `分支名`
- `负责目录`
- `handoff 文件`

否则后续追责和集成都会混乱。

### 2.4 并行阶段只允许“各自域内完工”，不允许“顺手改公共层”

所有 AI 必须坚持：

- 自己目录里做完整
- 公共层只提需求，不直接改

这会让短期看起来“重复一点”，但会显著降低合并成本。

### 2.5 迁移、全局注册、全局 locale、全局 metrics 必须由集成人串行处理

这些内容天然不适合 4 AI 并行改。

因此：

- Alembic 迁移只能统一生成一次
- 全局 `__init__.py` 注册只能串行处理
- `messages.json` / `menu.json` 只能串行合并
- `metrics.py` 只能串行补齐

### 2.6 并行开发不是“同时全做完”，而是“同时做局部闭环”

每个 AI 的目标不是把整个平台 independently 做完，而是：

- 在自己的边界内做出局部闭环
- 把需要共享接入的事项清楚移交

---

## 三、角色模型

建议正式定义 6 类角色。

| 角色 | 作用 |
|---|---|
| `coordinator` | 总协调者，负责分发任务、控制冻结、推进节奏 |
| `integrator` | 串行集成人，负责最后共享文件整合 |
| `AI-1` | 后端设计时域执行者 |
| `AI-2` | 后端运行时治理域执行者 |
| `AI-3` | 管理端前端执行者 |
| `AI-4` | 企业端前端执行者 |

### 3.1 `coordinator` 与 `integrator` 不应默认由同一个 AI 承担

如果资源允许，建议分开。

原因很简单：

- `coordinator` 更偏任务控制
- `integrator` 更偏共享文件合并与最终校验

如果资源不足，也可以同一人承担，但职责仍需区分清楚。

---

## 四、推荐的工作副本与分支方案

## 4.1 推荐目录命名

以当前主仓库 `E:/git_clone/novusai-saas-yudi` 为例，建议使用：

- `E:/git_clone/novusai-saas-yudi-ai1`
- `E:/git_clone/novusai-saas-yudi-ai2`
- `E:/git_clone/novusai-saas-yudi-ai3`
- `E:/git_clone/novusai-saas-yudi-ai4`
- `E:/git_clone/novusai-saas-yudi-integrator`

## 4.2 推荐分支命名

建议统一：

- `feat/orchestration-ai1-design-time`
- `feat/orchestration-ai2-runtime`
- `feat/orchestration-ai3-admin-ui`
- `feat/orchestration-ai4-tenant-ui`
- `feat/orchestration-integrator`

### 4.2.1 为什么要固定命名

因为后续：

- CI 追踪
- 合并顺序
- 产出归档
- 问题定位

都会更清楚。

---

## 五、并行前准备清单

进入并行开发前，`coordinator` 必须先完成以下动作：

1. 创建 4 个执行工作副本和 1 个集成工作副本。
2. 给每个工作副本切到自己的专属分支。
3. 把 [31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md](./31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md) 和 `31-parallel-delivery-kit-20260323/` 分发给对应 AI。
4. 明确冻结文件清单。
5. 明确每个 AI 的 handoff 文件路径。
6. 明确并行截止时间和 handoff 截止时间。

如果以上任一项未完成，不建议开始并行。

---

## 六、并行阶段的正式操作规范

## 6.1 AI 只能在自己的工作副本中执行

任何 AI 都不应进入：

- 别人的工作副本
- 集成人工作副本
- 主仓库直接开发

## 6.2 AI 只能提交自己负责域内的文件

允许：

- 自己命名空间下的新文件
- 自己目录下的局部模块文件
- 自己 handoff 文件

禁止：

- 改别人负责的命名空间
- 改冻结文件
- 顺手改全局层

## 6.3 AI 不得在并行阶段生成 Alembic 迁移

并行阶段如涉及数据表新增，只允许：

- 写模型
- 在 handoff 里列出迁移需求

禁止：

- 自己创建 `backend/migrations/versions/*.py`

## 6.4 AI 不得批量格式化全仓

允许：

- 局部文件格式化
- 局部测试

禁止：

- 对整个 `backend/app/**` 或 `frontend/**` 做全仓格式化
- 对共享目录运行自动改写工具

## 6.5 AI 必须持续维护 handoff

handoff 不应等到最后才补。

推荐规则：

- 每完成一个模块，就更新一次 handoff
- 共享接入需求一出现，就立刻记录

---

## 七、并行阶段的禁止操作

以下行为一律视为并行违规：

- 进入非自己工作副本开发
- 修改冻结文件
- 生成迁移文件
- 修改全局 locale 聚合入口
- 修改全局 API 聚合入口
- 重构别人负责的共享基础层
- 删除自己看不懂的未跟踪文件
- 为了通过测试而临时放宽规则或注释约束

如果遇到必须突破边界的情况，正确做法只有一个：

- 写入 handoff
- 标注阻塞
- 交给 `coordinator` 或 `integrator`

---

## 八、handoff 冻结规则

并行阶段结束时，每个 AI 必须做一次正式冻结。

冻结内容包括：

1. 停止新增需求和重构。
2. 只修自己域内阻塞性问题。
3. 完成 handoff 文档。
4. 标记哪些内容已测，哪些未测。

### 8.1 冻结后的修改原则

冻结后如仍需修改，只允许：

- 修 handoff 中已声明的 bug
- 修自己负责文件中的小问题

禁止：

- 再扩张范围
- 再改共享文件

---

## 九、串行集成前检查

在进入串行集成前，`coordinator` 应检查：

- 4 个 AI 是否都完成 handoff
- 4 个 AI 是否都未改冻结文件
- 4 个 AI 是否都没有生成迁移
- 4 个 AI 是否都记录了测试结果

如果这些检查不通过，不应进入正式集成。

---

## 十、与其他文档的关系

- 与 [31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md](./31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md) 一起构成并行执行主方案。
- 与 [35-coordinator-launch-and-delivery-runbook-20260323.md](./35-coordinator-launch-and-delivery-runbook-20260323.md) 一起构成主协调者执行包。
- 与 [33-cross-agent-contract-matrix-20260323.md](./33-cross-agent-contract-matrix-20260323.md) 一起约束跨 AI 的数据和接口口径。
- 与 [34-integrator-prompt-and-serial-merge-checklist-20260323.md](./34-integrator-prompt-and-serial-merge-checklist-20260323.md) 一起约束串行集成。

---

## 十一、结论

真正安全的 4 AI 并行，不是“4 个 AI 一起开工”这么简单，而是必须同时满足：

1. 独立工作副本
2. 冻结共享文件
3. 明确命名空间边界
4. 持续维护 handoff
5. 串行集成人统一收口

缺任何一个，都会让并行开发退化成高冲突协作。
