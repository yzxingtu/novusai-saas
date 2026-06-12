---
trigger: model_decision
description: PR 本地测试通过后的 approve、tested-pass 标签与自动合并流程
---
# PR 测试通过与自动合并规则

## 适用场景

当 PR 已完成必要的本地测试、手动验收或协作者验证，并且准备允许自动合并到 `main` 时，按本规则操作。

## 标准流程

1. 确认 PR 的变更范围、关联 Issue、测试结论和风险说明已经清楚。
2. 对 PR 执行审批：

```bash
gh pr review <编号> --approve
```

3. 审批完成后，为 PR 添加测试通过标签：

```bash
gh pr edit <编号> --add-label tested-pass
```

4. `tested-pass` 标签会触发 GitHub Actions 自动合并流程。只有当 PR 已通过 review approval 且带有 `tested-pass` 标签时，自动合并才会启用。

## 约束

- 不允许为了自动合并跳过 PR review。
- 不允许在未完成测试时添加 `tested-pass` 标签。
- `tested-pass` 只表示当前 PR 已按验收口径测试通过，不替代 CI、代码审查或安全审计。
- 若 PR 后续追加 commit，应重新确认测试结果；必要时移除并重新添加 `tested-pass`。
- `main` 是保护分支，仍然只接受 PR 合入，不允许直接 push。

## 常用命令

```bash
# 查看 PR 状态
gh pr view <编号>

# 审批 PR
gh pr review <编号> --approve

# 标记测试通过并触发自动合并
gh pr edit <编号> --add-label tested-pass
```

