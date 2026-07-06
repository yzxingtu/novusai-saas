---
trigger: model_decision
description: Issue、PR、GitHub CLI
---
# GitHub 工作流

- Issue 是需求、缺陷、技术债的事实来源；实现以 Issue 的范围和 AC 为准。
- 新需求/缺陷先查重：`gh issue list --state all --search "<关键词>"`。
- 已有 Issue/PR 时优先跟进，不重复创建；结论写回 Issue 或 PR。
- 新建 Issue 使用精简结构：背景、范围、验收标准、风险/依赖。
- 开 PR 时说明变更、测试、风险；关联 Issue 用 `Fixes #编号` 或 `Refs #编号`。
- 使用 `gh` 处理远端：`gh issue view`、`gh issue create`、`gh pr create`、`gh pr checks`、`gh pr view`。
- 长正文用临时 markdown 文件和 `--body-file`，避免 shell 转义破坏内容。
- 不编造 Issue/PR 编号；不把认证信息写入仓库。
