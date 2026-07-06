---
trigger: model_decision
description: 切分支、合并、处理 hotfix 
---
# 分支策略

> 与 [`github-issues-workflow`](./github-issues-workflow.mdc) 配合使用：**先有 Issue，再开分支**。

## 主干与保护

- **`main`**：长期主干，**始终保持可构建/可部署**。
- **保护规则**（GitHub Settings → Branches）：
  - 禁止直接 `git push` 到 `main`，只接受 PR 合入；
  - 建议要求 **至少 1 人 review** 与 **CI 通过**；
  - 合并方式建议 **Squash merge**，保持历史线性。

## 分支以「任务」为单位，不以「人」为单位

**每个 Issue（或更小的可独立合并单元）开一条短期分支**，而不是「每位成员一条长期分支」。
长期个人分支会让代码混在一起、难评审、易冲突，是反模式。

| 场景 | 推荐做法 |
| :--- | :--- |
| 新功能 | `feat/issue-<编号>-<简短描述>` |
| 缺陷修复 | `fix/issue-<编号>-<简短描述>` |
| 文档/杂务 | `docs/issue-<编号>-...` / `chore/issue-<编号>-...` |
| 紧急线上修复 | `hotfix/<简短描述>`（合入后回填到 `main`） |
| 个人探索 / 无 Issue | `spike/<姓名拼音>-<主题>`（**不合入 `main`**） |

命名规则：**全部小写**、用连字符 `-`，**避免中文与空格**；尽量短而表意。

## 生命周期

1. 在最新的 `main` 上切分支：`git switch -c feat/issue-12-spine-pipeline origin/main`。
2. 频繁小步提交；与 `main` 保持同步：`git fetch && git rebase origin/main`（或 `merge`，团队统一一种）。
3. 推送并开 PR：`gh pr create --title "..." --body "Fixes #12 ..."`。
4. **PR 通过 review 与 CI** 后 squash 合并；**合并后删除分支**（GitHub 可设置自动删除）。
5. 一条分支对应**一个**聚焦的 PR；范围扩大请拆 Issue、拆分支。

## 约束

- 修改前先 **`git switch -c`** 到符合命名规范的分支，**绝不直接在 `main` 上提交**。
- 分支名必须包含对应 **Issue 编号**（除 `hotfix` / `spike` 外）；找不到 Issue 时，先建 Issue 再开分支。
- 所有提交描述必须使用中文，格式为 `<type>(scope): <中文说明>`。
- 一次任务只在**一条分支**上推进；遇到无关改动，新开分支处理。
