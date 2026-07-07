---
trigger: model_decision
description: 分支、提交、合并
---
# 分支策略

- `main` 是受保护主干，只接受 PR 合入。
- 开发前从最新 `main` 切短分支：`git switch main && git pull --ff-only && git switch -c <branch>`。
- 分支尽量绑定 Issue：`feat/issue-<编号>-<desc>`、`fix/issue-<编号>-<desc>`、`docs/issue-<编号>-<desc>`。
- 分支名小写，用连字符，避免中文和空格。
- 一个分支只做一个聚焦任务；范围扩大时拆 Issue、拆分支。
- 提交要小步、可回滚；提交描述必须中文：`fix(engine): 修复空结果降级`。
- PR 描述写清范围、测试、风险；能关闭 Issue 时使用 `Fixes #编号`。
