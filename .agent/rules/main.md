---
trigger: always_on
---
# Agent 主规则

## 必守

- 先读 `README.md`；涉及文档、架构、接口、部署时再查 `docs/` 和相关源码。
- 可交付工作必须关联 GitHub Issue；收到需求/缺陷先 `gh issue list --search "<关键词>"` 查重。
- 不直接推 `main`；从最新 `main` 切短分支，PR 合入。
- 代码变更影响行为、接口、配置、部署或规则时，同步更新文档。
- 复杂业务逻辑不得堆在路由、控制层或 UI 事件中；下沉到服务、领域模块或可复用函数。
- 远端操作优先用 `gh`；不得把 token、密钥、PAT 写入仓库。
- 所有提交描述必须使用中文，格式：`<type>(scope): <中文说明>`。

## 规则索引

- `project-context-and-docs.md`：项目背景、文档位置。
- `github-issues-workflow.md`：Issue/PR/gh 工作流。
- `branching-strategy.md`：分支与提交。
- `pr-tested-pass-auto-merge.md`：测试通过与自动合并。
