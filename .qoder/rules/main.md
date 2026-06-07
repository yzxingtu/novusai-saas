---
trigger: always_on
---
# 团队协作主规则（Index）

> 本仓库的开发请遵循以下原则；具体细则按需查阅下方索引中的次级 rule。

## 核心原则

1. **先理解项目，再动手**：开工前阅读 `README.md`，必要时查阅已有文档。
2. **任务追溯**：所有可交付工作以 **GitHub Issue** 为单一事实来源；**先有 Issue，再写代码**。
3. **分支与 PR**：**禁止直接推 `main`**；按 Issue 切短期分支，PR 用 `Fixes #编号` 关联。
4. **文档归位**：所有文档使用相关工具并按主题分类，根目录仅保留 `README.md`。
5. **远端协作**：终端与 GitHub 交互优先使用 **GitHub CLI（`gh`）**；不在仓库写入 token。
6. **同步更新**：行为或接口变化时，**代码与文档同提交**，避免文档过期。
7. **模块化开发**：优先保证高内聚、低耦合；复杂逻辑必须拆分为独立模块或函数方法，避免巨型文件与巨型函数。

## 次级 rule 索引

| Rule | 主题 | 何时查阅 |
| :--- | :--- | :--- |
| [`project-context-and-docs`](./project-context-and-docs.md) | 项目背景与 `docs/` 目录规范 | 新增/修改文档、开始新模块前 |
| [`github-issues-workflow`](./github-issues-workflow.md) | Issue/PR 写法、`gh` 命令 | 创建/编辑 Issue、开 PR、查看 CI |
| [`branching-strategy`](./branching-strategy.md) | 分支命名、生命周期、保护规则 | 切分支、合并、处理 hotfix |

## 约束

- 找不到对应 Issue 时，**先建 Issue**（或在 PR 中补建），再开始实现。
- 修改代码前，**`git switch -c`** 到符合命名规范的分支，**绝不在 `main` 上提交**。
- 新增/修改的文档使用相关工具规范写入；**禁止在仓库根目录新增散落 `.md`**（`README.md` 除外）。
- 涉及远端操作（Issue / PR / Release / CI）时，优先使用 `gh`，并在不确定时先 `gh auth status` 检查认证。
- 实现功能时，禁止将复杂业务逻辑直接堆在路由/控制层/UI 事件中；必须下沉到可复用的领域模块、服务层或独立函数，并保持清晰接口边界。
