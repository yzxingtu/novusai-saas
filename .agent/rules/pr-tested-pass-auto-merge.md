---
trigger: model_decision
description: PR 测试通过后合并
---
# PR 测试通过

- 只有在本地测试、CI 或人工验收明确通过后，才能标记 `tested-pass`。
- 标准顺序：先 approval，再添加 `tested-pass`。
- 命令：

```bash
gh pr review <编号> --approve
gh pr edit <编号> --add-label tested-pass
```

- 当前账号是 PR 作者时不能自审批；说明原因，等待有写权限的其他 reviewer 或 owner 处理。
- `tested-pass` 只触发自动合并，不替代 CI、代码审查或安全检查。
- PR 追加 commit 后重新确认测试结论，必要时重新触发标签流程。
- 不绕过 `main` 保护规则。
