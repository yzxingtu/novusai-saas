# AI 编排平台主协调者启动与交付作战手册（2026-03-23）

## 一、文档目标

本文档用于补齐 4 AI 并行交付方案中的“主协调者执行层”。

前面的文档已经定义了：

- 平台蓝图
- 4 AI 并行拆分方案
- 并行执行控制规范
- 跨 AI 契约矩阵
- 串行集成人规范

但真正开始执行时，还需要有人把这些规则变成动作。

这份文档回答的就是：

1. 主协调者开工前要准备什么。
2. 4 个 AI 和 `integrator` 的工作副本、分支、提示词、handoff 怎么发。
3. 并行期间每天怎么控节奏，怎么识别风险。
4. 什么时候允许冻结，什么时候必须退回修补。
5. 如何把并行产物正式移交给 `integrator`。

本文档不是产品设计，而是面向 `coordinator` 的正式作战手册。

---

## 二、`coordinator` 的职责定义

| 角色 | 责任 |
|---|---|
| `coordinator` | 组织 4 AI 并行启动、控制边界、校验冻结质量、管理 handoff、把合格交付正式移交给 `integrator` |

### 2.1 `coordinator` 负责什么

- 准备并行执行环境
- 指定角色、工作副本、分支与文档包
- 控制共享文件冻结
- 跟踪执行进度和阻塞
- 审核 handoff 是否达到移交标准
- 产出最终移交清单给 `integrator`

### 2.2 `coordinator` 不负责什么

- 不替 4 个 AI 写他们负责域的代码
- 不替 `integrator` 做共享文件收口
- 不在执行中途擅自改对象契约
- 不把“进度焦虑”变成越权改共享文件

### 2.3 `coordinator` 和 `integrator` 的区别

- `coordinator` 负责组织和控制
- `integrator` 负责最终串行收口

如果资源不足，允许同一人兼任，但必须按两个角色分阶段工作：

- 并行阶段按 `coordinator` 规则执行
- 串行收口阶段按 `integrator` 规则执行

---

## 三、启动前的正式输入物

主协调者开始工作前，至少应具备：

1. [31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md](./31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md)
2. [32-parallel-execution-control-spec-20260323.md](./32-parallel-execution-control-spec-20260323.md)
3. [33-cross-agent-contract-matrix-20260323.md](./33-cross-agent-contract-matrix-20260323.md)
4. [34-integrator-prompt-and-serial-merge-checklist-20260323.md](./34-integrator-prompt-and-serial-merge-checklist-20260323.md)
5. 本文档
6. [36-coordinator-freeze-signoff-and-integrator-transfer-template-20260323.md](./36-coordinator-freeze-signoff-and-integrator-transfer-template-20260323.md)
7. [37-worktree-setup-and-branch-bootstrap-runbook-20260323.md](./37-worktree-setup-and-branch-bootstrap-runbook-20260323.md)
8. `31-parallel-delivery-kit-20260323/` 下全部 prompt 与 handoff 模板

如果以上输入不完整，不建议直接启动并行。

---

## 四、并行启动前检查清单

`coordinator` 在正式发任务前，必须先完成以下 5 类准备。

## 4.1 角色分配

必须明确以下角色：

- `AI-1`
- `AI-2`
- `AI-3`
- `AI-4`
- `coordinator`
- `integrator`

必须落地成一张角色表，至少包含：

- 角色名
- 执行者
- 工作副本路径
- 分支名
- handoff 文件
- prompt 文件

## 4.2 工作副本与分支准备

建议目录：

- `E:/git_clone/novusai-saas-yudi-ai1`
- `E:/git_clone/novusai-saas-yudi-ai2`
- `E:/git_clone/novusai-saas-yudi-ai3`
- `E:/git_clone/novusai-saas-yudi-ai4`
- `E:/git_clone/novusai-saas-yudi-integrator`

建议分支：

- `feat/orchestration-ai1-design-time`
- `feat/orchestration-ai2-runtime`
- `feat/orchestration-ai3-admin-ui`
- `feat/orchestration-ai4-tenant-ui`
- `feat/orchestration-integrator`

### 4.2.1 推荐启动动作

如果使用 `git worktree`，建议由 `coordinator` 统一准备，避免不同 AI 自己操作时口径不一致。

具体命令和校验步骤见：

- [37-worktree-setup-and-branch-bootstrap-runbook-20260323.md](./37-worktree-setup-and-branch-bootstrap-runbook-20260323.md)

建议至少固定以下信息：

- 基准提交 SHA
- 各工作副本目录
- 各分支名
- 创建时间

## 4.3 文档包与提示词分发

必须做到“角色拿到的是完整包，而不是一句口头说明”。

### 4.3.1 4 个执行 AI 需要收到

- 自己的专属 prompt
- `31`
- `32`
- `33`
- 自己的 handoff 模板

### 4.3.2 `integrator` 需要收到

- `Integrator-serial-merge-prompt.md`
- `34`
- `31`
- `32`
- `33`

### 4.3.3 `coordinator` 自己必须持有

- `Coordinator-launch-and-control-prompt.md`
- `35`
- 全部 4 份 prompt
- 全部 4 份 handoff
- `34`

## 4.4 时间与冻结点设置

启动前必须明确：

- 并行开始时间
- 中期检查点
- handoff 初稿截止时间
- 冻结截止时间
- 移交 `integrator` 时间

如果没有明确时间点，handoff 往往会拖到最后，质量会明显下降。

## 4.5 共享文件冻结公告

必须把冻结文件清单正式发给 4 个 AI，而不是默认他们“应该知道”。

冻结公告至少应包含：

- 冻结文件列表
- 违规处理方式
- 遇到共享改动需求时的标准动作：写 handoff，不直接改

---

## 五、标准分发包

主协调者建议为每个角色都准备“最小分发包”。

## 5.1 `AI-1` 分发包

- `AI-1-backend-design-time-domain-prompt.md`
- `AI-1-handoff.md`
- `31`
- `32`
- `33`

## 5.2 `AI-2` 分发包

- `AI-2-backend-runtime-governance-and-recommendation-prompt.md`
- `AI-2-handoff.md`
- `31`
- `32`
- `33`

## 5.3 `AI-3` 分发包

- `AI-3-admin-frontend-studio-and-market-prompt.md`
- `AI-3-handoff.md`
- `31`
- `32`
- `33`

## 5.4 `AI-4` 分发包

- `AI-4-tenant-frontend-operator-and-recommendation-prompt.md`
- `AI-4-handoff.md`
- `31`
- `32`
- `33`

## 5.5 `integrator` 分发包

- `Integrator-serial-merge-prompt.md`
- `34`
- `31`
- `32`
- `33`
- 4 份 handoff

---

## 六、并行阶段的节奏控制

`coordinator` 不应只是开工时发完 prompt 就消失。

建议至少采用“三段式节奏控制”。

## 6.1 启动确认

开工后尽快确认每个角色是否已经完成：

- 进入自己的独立工作副本
- 切到自己的专属分支
- 阅读自己的 prompt 与必读文档
- 知道自己的 handoff 文件路径

这一步不过关，后面几乎一定会出现越权修改或 handoff 缺项。

## 6.2 中期检查

建议在并行中段做一次正式检查，至少确认：

- 是否误改冻结文件
- 是否开始维护 handoff
- 是否出现对象字段冲突
- 是否出现跨端导入或跨域开发
- 是否有人准备偷偷生成迁移

### 6.2.1 中期检查不过关时的处理

如果发现问题：

- 先停止其扩张开发范围
- 要求先修边界问题
- 必要时重新发冻结说明

## 6.3 冻结前检查

正式冻结前，`coordinator` 要求每个 AI 给出：

- 当前最后提交 SHA
- 当前 handoff 状态
- 已完成测试/校验
- 未解决阻塞

没有这些信息，不允许进入冻结验收。

---

## 七、handoff 质量门禁

不是“有 handoff 文件”就算完成，而是必须过门禁。

## 7.1 handoff 最低合格线

### 7.1.1 后端 AI

至少要写清：

- 文件清单
- 共享文件接入项
- 迁移登记
- 对外字段/状态契约
- 权限/菜单需求
- 测试结果
- 风险与临时假设

### 7.1.2 前端 AI

至少要写清：

- 页面与 API 对应关系
- 共享入口接入项
- 依赖的后端字段与状态
- i18n 文件
- 截图和联调证据
- 校验结果
- 风险与临时假设

## 7.2 不合格 handoff 的判定

出现以下任一情况，`coordinator` 应视为不合格：

- 只有“待填写”而没有实质内容
- 没有最后提交 SHA
- 没有共享文件接入项
- 没有字段或状态契约说明
- 没有测试/校验证据
- 没有风险与阻塞说明

---

## 八、冻结与签收流程

建议采用正式签收，而不是口头说“差不多了”。

## 8.1 每个 AI 的冻结输出

每个 AI 冻结时必须提交：

1. 最后提交 SHA
2. 完整 handoff
3. 已执行验证结果
4. 未解决问题列表

## 8.2 `coordinator` 的签收动作

对每个 AI，主协调者至少确认：

- 是否符合文件边界
- 是否未改冻结文件
- 是否未生成迁移
- handoff 是否完整
- 是否可移交给 `integrator`

### 8.2.1 签收状态建议

可统一使用以下状态：

- `prepared`
- `in_progress`
- `handoff_incomplete`
- `frozen_rejected`
- `frozen_accepted`
- `ready_for_integrator`
- `blocked`

---

## 九、正式移交给 `integrator` 的标准动作

当 4 个 AI 都达到 `frozen_accepted` 后，`coordinator` 才能发起正式移交。

建议直接复用：

- [36-coordinator-freeze-signoff-and-integrator-transfer-template-20260323.md](./36-coordinator-freeze-signoff-and-integrator-transfer-template-20260323.md)

## 9.1 移交包内容

移交给 `integrator` 的包至少包含：

1. 4 个 AI 的分支名
2. 4 个 AI 的最后提交 SHA
3. 4 份 handoff
4. 冻结签收结果
5. 已知冲突清单
6. 建议合并顺序
7. 明确禁止 `integrator` 自行猜测的风险点

## 9.2 移交说明必须包含的重点

- 哪些 handoff 质量较高，可直接照接
- 哪些 handoff 仍有假设，集成时要重点核查
- 哪些对象有潜在字段冲突
- 哪些前端页面尚未完成真实接口联调
- 哪些指标、菜单或权限是“必须补”的共享项

---

## 十、主协调者最终输出物

`coordinator` 在并行阶段结束后，至少应输出：

1. 角色与工作副本映射表
2. 分支与冻结提交表
3. 4 份合格 handoff
4. 冻结签收清单
5. 移交 `integrator` 说明

---

## 十一、常见失败模式

主协调者最容易犯的错误不是“不努力”，而是“控制动作不够正式”。

常见失败模式包括：

- 只分配职责，不分配工作副本和分支
- 只发 prompt，不检查是否真的开在独立副本里
- 只看代码，不看 handoff
- handoff 没写完也让其冻结通过
- 还没收齐 4 份冻结签收，就提前让 `integrator` 开工
- 中途因为着急，默许某个 AI 改共享文件

这些都会把并行协作重新打回高冲突模式。

---

## 十二、结论

并行交付真正的难点，不在“找 4 个 AI 同时做事”，而在有人把：

- 角色
- 副本
- 分支
- 提示词
- handoff
- 冻结
- 移交

全部按制度串起来。

`coordinator` 的价值，就是让这套并行方案不是“理论可行”，而是“执行可控”。
