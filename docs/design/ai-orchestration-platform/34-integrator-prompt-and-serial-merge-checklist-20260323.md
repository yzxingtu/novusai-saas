# AI 编排平台集成人 Prompt 与串行合并检查清单（2026-03-23）

## 一、文档目标

本文档用于补齐 4 AI 并行交付方案中的最后一块正式控制层：

- 谁来做最终串行收口
- 串行收口允许改哪些共享文件
- 应按什么顺序合并
- 合并前、中、后分别检查什么
- 最终要交付哪些证据

本文档不是产品规划文档，而是面向 `integrator` 的正式执行清单。

---

## 二、为什么必须有独立 `integrator`

即使已经有：

- [31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md](./31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md)
- [32-parallel-execution-control-spec-20260323.md](./32-parallel-execution-control-spec-20260323.md)
- [33-cross-agent-contract-matrix-20260323.md](./33-cross-agent-contract-matrix-20260323.md)

仍然不能让 4 个执行 AI 自己去碰共享文件收口。

原因很简单：

1. 共享文件天然高冲突。
2. 迁移文件只能统一生成一次。
3. locale、菜单、权限、metrics 和路由注册必须统一口径。
4. 前后端字段冲突需要一个最终裁决者。

所以并行开发的最后一步，必须由独立 `integrator` 在独立工作副本中串行完成。

---

## 三、`integrator` 的正式角色定义

| 角色 | 责任 |
|---|---|
| `integrator` | 串行合并 4 个 AI 的产物，处理共享文件，生成统一迁移，运行最终校验，输出最终集成报告 |

### 3.1 `integrator` 的边界

`integrator` 负责：

- 合并 4 个 AI 的局部成果
- 修改冻结共享文件
- 按契约矩阵裁决字段与状态冲突
- 生成统一 Alembic 迁移
- 补齐 locale、菜单、权限、metrics、页面入口
- 跑最小验证矩阵

`integrator` 不负责：

- 再开新需求
- 趁机大重构
- 重新设计对象模型
- 覆盖 4 个 AI 的局部实现风格偏好

### 3.2 `integrator` 的工作原则

- 只在自己的独立工作副本中工作
- 以 handoff 和契约文档为第一输入，不靠猜
- 尽量最小修改完成收口，不做无关重构
- 所有偏离 handoff 的修正都必须留痕

---

## 四、串行集成前的必备输入物

进入串行集成前，必须具备以下输入：

1. `AI-1` 完整交付分支与 handoff
2. `AI-2` 完整交付分支与 handoff
3. `AI-3` 完整交付分支与 handoff
4. `AI-4` 完整交付分支与 handoff
5. `31` 主路线图
6. `32` 并行执行控制规范
7. `33` 跨 AI 契约矩阵
8. 本文档
9. `35` 主协调者冻结签收结果与移交说明
10. `31-parallel-delivery-kit-20260323/Integrator-serial-merge-prompt.md`
11. [38-integrator-final-merge-report-template-20260323.md](./38-integrator-final-merge-report-template-20260323.md)

如果缺任一项，不建议开始正式集成。

---

## 五、`integrator` 允许修改的共享文件

只有 `integrator` 可以在串行阶段修改以下共享文件：

### 5.1 后端共享文件

- `backend/app/models/__init__.py`
- `backend/app/api/admin/__init__.py`
- `backend/app/api/tenant/__init__.py`
- `backend/app/locales/en/messages.json`
- `backend/app/locales/zh_CN/messages.json`
- `backend/app/locales/en/menu.json`
- `backend/app/locales/zh_CN/menu.json`
- `backend/migrations/env.py`
- `backend/migrations/versions/*`
- `backend/app/core/metrics.py`

### 5.2 前端共享文件

- `frontend/apps/web-antd/src/api/admin/index.ts`
- `frontend/apps/web-antd/src/api/tenant/index.ts`
- `frontend/apps/web-antd/src/locales/index.ts`
- 管理端或企业端最终页面入口文件
- 管理端或企业端最终路由聚合文件
- 经 handoff 明确点名的共享导航或菜单接入文件

### 5.3 修改原则

- 只能做“收口所必需”的修改
- 尽量按 handoff 精确接入
- 若必须超出 handoff 修补，必须在最终报告中说明原因

---

## 六、串行合并标准顺序

## 6.1 阶段 0：预检查

集成开始前先检查：

1. 4 个 AI 是否都在独立工作副本中完成开发
2. 4 份 handoff 是否完整
3. 4 个 AI 是否误改冻结文件
4. 4 个 AI 是否都未自行生成迁移
5. 4 个 AI 是否都留下最小测试/校验证据

若任一项不通过，先退回修正，不要继续合并。

## 6.2 阶段 1：合并 `AI-1`

先合并后端设计时域：

- 模型、Schema、Repository、Service、Admin API
- 不立即改共享文件，先把业务文件并入 `integrator` 工作副本
- 对照 `AI-1` handoff 核对设计时对象和字段

## 6.3 阶段 2：合并 `AI-2`

再合并后端运行时治理域：

- 模型、Schema、Repository、Service、Admin/Tenant API
- 检查是否正确消费 `AI-1` 的设计时对象
- 对照 `33` 文档核对字段、状态、权限资源名、响应包装

## 6.4 阶段 3：统一收口后端共享层

此阶段才允许修改后端共享文件：

1. 合并 `models/__init__.py`
2. 合并 `api/admin/__init__.py`
3. 合并 `api/tenant/__init__.py`
4. 合并 `messages.json`
5. 合并 `menu.json`
6. 补 `metrics.py`
7. 统一处理 `migrations/env.py`
8. 生成一份统一 Alembic 迁移

## 6.5 阶段 4：合并 `AI-3`

接入管理端前端页面：

- 先合并其私有目录和 API 文件
- 暂不急于动共享入口，先核对依赖字段是否和后端一致
- 对照 `AI-3` handoff 检查页面入口、权限和菜单依赖

## 6.6 阶段 5：合并 `AI-4`

接入企业端前端页面：

- 先合并其私有目录和 API 文件
- 核对 tenant 资源归属、状态枚举、接口字段
- 对照 `AI-4` handoff 检查运营控制台和推荐中心依赖

## 6.7 阶段 6：统一收口前端共享层

此阶段再统一修改前端共享文件：

1. API 聚合入口
2. locale 聚合入口
3. admin 最终页面入口或路由入口
4. tenant 最终页面入口或路由入口
5. 菜单、导航、页面排序接入

## 6.8 阶段 7：最终校验

收口完成后统一执行验证矩阵。

---

## 七、共享契约检查清单

`integrator` 必须至少检查以下口径：

### 7.1 对象所有权

- `AI-1` 是否拥有并定义 `solution/workflow/release/trigger/environment/change_set`
- `AI-2` 是否拥有并定义 `activation/run/node_run/approval/artifact/recommendation/feedback/market_review`
- `AI-3` / `AI-4` 是否没有擅自重定义业务字段

### 7.2 字段命名

- 主键是否统一为 `id`
- 外键是否统一为 `<object>_id`
- 是否统一使用 `tenant_id`
- 是否统一使用 `created_at` / `updated_at`
- 是否没有混入同义字段

### 7.3 状态与枚举

- 状态值是否是字符串枚举
- 是否统一使用 snake_case
- 是否与 `33` 中约定一致
- 若扩展了状态，handoff 是否说明

### 7.4 API 口径

- 后端是否统一用 `success()` / `created()` / `paginated()` / `deleted()`
- 是否统一遵守 JSON:API 分页与过滤
- 时间字段是否为 ISO 8601
- 前端是否没有假设裸返回

### 7.5 权限与菜单

- `permission_resource` 是否使用约定命名
- `parent_resource` 是否补齐
- `messages.json` 的 action 翻译是否补齐
- menu key 是否与前端页面 key 对应

---

## 八、统一迁移与可观测性检查清单

## 8.1 迁移

- 只生成一份统一迁移，禁止多份并发迁移
- 所有外键名称显式命名
- 所有新表都在 handoff 中登记过
- 迁移内容与最终模型一致
- 没有把本可应用层初始化的数据硬塞进迁移

## 8.2 metrics

- 只在串行阶段补 `backend/app/core/metrics.py`
- 指标名称、类型、标签口径统一
- 运行次数、失败数、审批等待、推荐生成等关键路径有基础指标
- 若某指标暂未实现，需在最终报告中说明缺口

---

## 九、验证矩阵

`integrator` 完成收口后，至少应跑：

### 9.1 后端

- `pytest` 最小服务层/接口层测试
- `alembic upgrade head` 或等价迁移验证
- 关键 API 冒烟

### 9.2 前端

- `pnpm typecheck`
- 管理端关键页面冒烟
- 企业端关键页面冒烟

### 9.3 联调

- 权限资源与菜单是否能正常显示
- admin / tenant 两端是否严格分端
- 前后端字段是否一致
- 推荐页是否按结构化结果渲染，不是聊天壳
- 审批 / 运行 / 激活是否至少具备最小闭环

---

## 十、最终交付物清单

串行集成完成后，`integrator` 至少应交付：

1. 最终集成分支
2. 已更新的共享文件
3. 统一 Alembic 迁移
4. 最小验证结果
5. 一份最终集成说明，至少包含：
   - 合并顺序
   - 处理过的冲突
   - 偏离 handoff 的修正
   - 仍遗留的问题
   - 建议下一阶段处理事项

建议直接复用：

- [38-integrator-final-merge-report-template-20260323.md](./38-integrator-final-merge-report-template-20260323.md)

---

## 十一、停止条件

遇到以下情况，应暂停集成并回退到协调阶段：

- 两个 AI 对同一对象主字段定义冲突且无法从 `33` 裁决
- 某 AI 大量误改冻结文件，已无法低成本分离
- handoff 关键内容缺失，无法确认接入方式
- 前后端契约冲突已经超出“集成修补”范围，变成重新设计

---

## 十二、结论

4 AI 并行开发的最后一步，不是“把代码 merge 一下”，而是一次正式的串行治理动作。

`integrator` 的职责，就是把：

- 并行拆分
- 共享契约
- 迁移收口
- 权限与入口接入
- 测试与验证

全部串成一个真正可落地的交付闭环。
