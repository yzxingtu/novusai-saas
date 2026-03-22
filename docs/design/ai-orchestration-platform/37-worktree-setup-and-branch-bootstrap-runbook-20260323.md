# 4 AI + 1 Integrator 的 `git worktree` 初始化与分支引导手册（2026-03-23）

## 一、文档目标

本文档用于把并行执行控制中的“独立工作副本”要求，落成可直接执行的命令手册。

适用对象：

- `coordinator`
- 负责准备环境的工程负责人

默认环境：

- Windows PowerShell
- 主仓库路径：`E:/git_clone/novusai-saas-yudi`

---

## 二、核心原则

- 4 个执行 AI 和 1 个 `integrator` 必须使用独立工作副本
- 首选 `git worktree`
- 所有工作副本都从同一个基准提交拉出
- 在并行阶段，不要直接在主仓库中开发

---

## 三、推荐目录与分支

### 3.1 工作副本目录

- `E:/git_clone/novusai-saas-yudi-ai1`
- `E:/git_clone/novusai-saas-yudi-ai2`
- `E:/git_clone/novusai-saas-yudi-ai3`
- `E:/git_clone/novusai-saas-yudi-ai4`
- `E:/git_clone/novusai-saas-yudi-integrator`

### 3.2 分支名

- `feat/orchestration-ai1-design-time`
- `feat/orchestration-ai2-runtime`
- `feat/orchestration-ai3-admin-ui`
- `feat/orchestration-ai4-tenant-ui`
- `feat/orchestration-integrator`

---

## 四、启动前检查

在主仓库执行：

```powershell
git -C E:/git_clone/novusai-saas-yudi status --short
git -C E:/git_clone/novusai-saas-yudi branch --show-current
git -C E:/git_clone/novusai-saas-yudi rev-parse HEAD
```

记录：

- 当前基准分支
- 当前基准提交 SHA
- 主仓库是否有未提交改动

### 4.1 建议

- 如果主仓库有不应带入并行阶段的未提交改动，先由人工确认再开始
- 不要在不清楚基准状态时直接创建 5 个 worktree

---

## 五、创建 worktree 的标准命令

以下命令示例假设基准分支是当前分支。

在 PowerShell 中执行：

```powershell
git -C E:/git_clone/novusai-saas-yudi worktree add E:/git_clone/novusai-saas-yudi-ai1 -b feat/orchestration-ai1-design-time
git -C E:/git_clone/novusai-saas-yudi worktree add E:/git_clone/novusai-saas-yudi-ai2 -b feat/orchestration-ai2-runtime
git -C E:/git_clone/novusai-saas-yudi worktree add E:/git_clone/novusai-saas-yudi-ai3 -b feat/orchestration-ai3-admin-ui
git -C E:/git_clone/novusai-saas-yudi worktree add E:/git_clone/novusai-saas-yudi-ai4 -b feat/orchestration-ai4-tenant-ui
git -C E:/git_clone/novusai-saas-yudi worktree add E:/git_clone/novusai-saas-yudi-integrator -b feat/orchestration-integrator
```

如果要从指定提交启动，可先 checkout 到该基准提交或显式指定基准引用。

---

## 六、创建后校验

执行：

```powershell
git -C E:/git_clone/novusai-saas-yudi worktree list
git -C E:/git_clone/novusai-saas-yudi-ai1 branch --show-current
git -C E:/git_clone/novusai-saas-yudi-ai2 branch --show-current
git -C E:/git_clone/novusai-saas-yudi-ai3 branch --show-current
git -C E:/git_clone/novusai-saas-yudi-ai4 branch --show-current
git -C E:/git_clone/novusai-saas-yudi-integrator branch --show-current
```

预期结果：

- 所有目录均已列在 `worktree list`
- 每个目录都在自己的专属分支上
- 没有目录仍停留在主仓库分支且混用

---

## 七、推荐的初始化记录表

建议 `coordinator` 初始化后立刻记录：

| 角色 | 工作副本路径 | 分支名 | 基准 SHA | 创建时间 |
|---|---|---|---|---|
| `AI-1` |  |  |  |  |
| `AI-2` |  |  |  |  |
| `AI-3` |  |  |  |  |
| `AI-4` |  |  |  |  |
| `integrator` |  |  |  |  |

---

## 八、分发前的二次确认命令

在每个工作副本目录执行：

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
```

需要确认：

- 工作副本是干净状态
- 分支名正确
- 基准 SHA 一致

---

## 九、并行期间的建议命令

### 9.1 查看每个工作副本状态

```powershell
git -C E:/git_clone/novusai-saas-yudi-ai1 status --short
git -C E:/git_clone/novusai-saas-yudi-ai2 status --short
git -C E:/git_clone/novusai-saas-yudi-ai3 status --short
git -C E:/git_clone/novusai-saas-yudi-ai4 status --short
git -C E:/git_clone/novusai-saas-yudi-integrator status --short
```

### 9.2 查看某个角色最后提交

```powershell
git -C E:/git_clone/novusai-saas-yudi-ai1 rev-parse HEAD
```

### 9.3 查看某个角色是否误改共享文件

```powershell
git -C E:/git_clone/novusai-saas-yudi-ai1 diff --name-only
```

---

## 十、清理与回收

当某个 worktree 不再需要时，先确认其中改动已处理完，再清理。

### 10.1 清理前检查

```powershell
git -C E:/git_clone/novusai-saas-yudi-ai1 status --short
```

### 10.2 移除 worktree

```powershell
git -C E:/git_clone/novusai-saas-yudi worktree remove E:/git_clone/novusai-saas-yudi-ai1
```

如目录残留，可在确认无用后人工清理。

### 10.3 清理失效记录

```powershell
git -C E:/git_clone/novusai-saas-yudi worktree prune
```

---

## 十一、常见错误与处理

### 11.1 在主仓库直接开发

问题：

- 与 worktree 并行控制目标冲突

处理：

- 停止在主仓库开发
- 把角色切回自己的 worktree

### 11.2 多个角色共用一个 worktree

问题：

- 极易互相覆盖和误读中间态

处理：

- 立即拆分为独立 worktree
- 重新确认边界和冻结文件

### 11.3 worktree 分支名错误

问题：

- 后续交接和集成无法准确定位来源

处理：

- 在正式开工前纠正
- 更新角色映射表

### 11.4 worktree 不是同一基准 SHA

问题：

- 并行结果不可比
- 合并成本显著上升

处理：

- 重新建立不一致的 worktree
- 统一回到同一基准提交

---

## 十二、结论

并行交付最容易被低估的不是提示词，而是工作副本基础设施。

`git worktree` 做对以后，后面的：

- 文件边界
- handoff
- 冻结
- 集成

才有执行基础。
