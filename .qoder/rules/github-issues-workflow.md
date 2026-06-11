---
trigger: model_decision
description: 创建/编辑 Issue、开 PR、查看 CI 
---
# GitHub Issues 任务管理与跟踪

## 基本原则

- **可交付工作**优先落在 **GitHub Issues**：需求、缺陷、技术债、里程碑拆解后的任务均应有 Issue，避免只在聊天或口头约定范围。
- **Issue 为单一事实来源**：实现范围、验收标准、依赖关系以 Issue 描述为准；讨论若有结论，应写回 Issue 或关联 `docs/decisions/`。

## GitHub CLI（`gh`）

- **约定**：在本仓库内需要通过终端与 GitHub 交互时（Issue / PR / 检查 CI / Release 等），**优先使用官方 [GitHub CLI](https://cli.github.com/) `gh`**，与网页操作等价、便于脚本化与团队协作复述同一套命令。
- **认证**：每位成员本地执行一次 `gh auth login`，按需选择 HTTPS 与凭证托管方式；**勿将 token 写入仓库**。
- **常用命令**（在项目根目录执行，`OWNER/REPO` 可省略则默认当前 `git remote`）：

```bash
gh auth status
gh repo view
gh issue list --state open
gh issue view <编号>
gh issue create --title "[feat] ..." --body-file path/to/body.md   # 或 --body "..."
gh issue edit <编号> --add-label type/feature --add-label area/engine
gh pr list
gh pr create --title "..." --body "Fixes #<编号>\n\n- AC: ..."
gh pr checks <编号>
gh pr merge <编号> --squash   # 合并策略以团队约定为准
```

- **与 Issues 规则对齐**：创建 Issue / PR 时的标题、正文结构、`Fixes #` / `Refs #`、Labels 等，仍遵循下文章节；`gh` 只是推荐载体。
- **受限环境**：若无安装 `gh` 或无法认证，再退回网页端或 API；并在 Issue / PR 描述中保持同一套关联与 AC 写法。

## 创建 Issue 时的建议结构

标题：`[类型] 简短说明`（类型示例：`feat` / `fix` / `docs` / `chore` / `perf`）

正文尽量包含：

1. **背景与目标**：要解决什么问题，与 README / `docs/` 中哪一节相关（可贴链接或路径）。
2. **验收标准（AC）**：可勾选的完成条件，便于评审与测试。
3. **范围**：包含什么；**不包含什么**（避免范围蔓延）。
4. **依赖与风险**：阻塞项、数据或环境前提。

鼓励使用 **Labels** 区分：`type/*`、`priority/*`、`area/*`（与架构分层一致，如 `ui`、`engine`、`cv`、`infra`）。团队可在仓库首次协作前约定一套固定标签表。

## 开发与合并习惯

- **分支命名**：建议 `issue-<编号>-简短描述` 或团队统一的 `feat/issue-<编号>-...`。
- **Pull Request**：描述中必须 **`Fixes #编号`**（关闭 Issue）或 **`Related #编号`** / **`Refs #编号`**（关联但不自动关闭）；简述如何满足 AC。
- **闭合 Issue 前**：AC 已满足；若行为或接口变化，已同步更新 **`docs/`** 中对应文档（参见项目文档规范 rule）。

## 给 AI 代理的约束

### 任务前置调查（防重复工作）

收到用户反馈的缺陷或新功能需求时，必须按以下顺序执行，**不得跳过**：

1. **代码分析**：先用搜索工具定位相关代码，理解当前实现和架构边界。
2. **Issue 查重**：`gh issue list --state open --search "<关键词>"` 搜索是否已有相关 Issue；同时检查 `--state closed` 确认是否已修复。
3. **进度评估**：若已存在相关 Issue：
   - 已有 PR 且已合并 → 告知用户该问题已修复，确认是否需要补充。
   - 已有 Issue 且已分配 → 告知用户已有人在处理，询问是否要协作或跟进。
   - 已有 Issue 未分配 → 可主动认领，在 Issue 中表明接手。
4. **新建或关联**：确认无重复后才新建 Issue；若部分相关，新建 Issue 并用 `Refs #编号` 关联已有 Issue。

### 其他约束

- 在开始较大功能或重构前：**确认已有 Issue 编号或链接**；若没有，建议协作者先建 Issue 再写代码，或在 PR 中补建并关联。
- 实现与验收：**严格对齐 Issue 中的 AC**，超出范围的需求应在 Issue 中追加或拆新 Issue，而非静默扩展。
- **Questions / Discussions**：零散问答可用 GitHub Discussions；**需要跟踪交付物的事项仍应建 Issue**。
- **终端与 GitHub 交互**：在可行且用户环境已安装 `gh` 时，**优先通过 `gh` 列出/创建/编辑 Issue、创建 PR、查看 checks**，避免凭空编造 Issue 编号；执行前可向用户确认已 `gh auth login`。不得在仓库中写入 token 或 PAT。
