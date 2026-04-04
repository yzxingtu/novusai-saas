# Implementation Notes

## Audit Snapshot

- 当前工作树处于高噪声状态：`git status --short` 显示 356 处未提交改动。
- 顶层分布近似为：`frontend=159`、`backend=156`、`.trellis=22`、`.claude=8`、`.cursor=6`、`.agents=3`。
- `04-04-04-04-ai-orchestration-runtime-rebuild` 已进入 `verified`，但其 sibling tasks 仍混有 legacy Trellis 生命周期与未归属脏改。
- 本总控任务的职责不是吞并所有实现，而是把后续实现恢复成“按轨推进”的状态。

## Workstream Order

1. `control-plane`
   - 收口 Trellis 任务契约、ownership matrix、freeze rules 与 canonical guide。
2. `runtime-core`
   - 以 `04-04-04-04-ai-orchestration-runtime-rebuild` 为基线，清 warning、补 golden regressions、确认无 legacy fallback。
3. `page-awareness-provider-admin`
   - 对齐页面读/导航/写 intent、provider failure 归因、AI admin/monitoring 字段消费。
4. `plugin-runtime-frontend`
   - 对齐 manifest/source-of-truth、plugin runtime 恢复链、插件管理 UI 与 release/build/test 闭环。
5. `permission-org-shared-api`
   - 对齐 org node、permission tree、shared helper/API、前端 selector/preview 契约。
6. `assembly`
   - 只做组合验证，不再引入新设计。

## Freeze Rules

- 未出现在 `ownership-matrix.md` 的 dirty files 一律视为冻结。
- 未纳入本次五条工作流的 sibling tasks 仅允许补充归档/冻结信息，不允许继续扩散实现。
- 任一 workstream 若需要触碰他轨 owned files，必须先更新 matrix 与对应 child task。
- `test-results/`、临时诊断文件、手工导出快照都不能视作可交付产物。

## Warning Policy

- warning 不是可接受的“假绿灯”。
- AI runtime 线必须清掉已知 `AsyncMock` 未 await 等测试 warning，或在 owning task 中记录明确豁免。
- 最终 assembly 只能带着有记录的豁免通过，不能靠口头说明。

## Frozen Backlog

以下任务目前不属于本轮五条主工作流，默认冻结，待后续重新归类：

- `04-04-ai-admin-time-display-format`
- `04-03-project-audit-hardening`
- `04-03-04-03-novusdoc-writer-plugin-source-sync`
- `04-02-capability-awareness-followup`

此外，附件、知识库、租户域名/存储、以及不在五条工作流边界内的前端大面改动，也先按照 matrix 中的 `freeze` 规则处理。

## Immediate Next Steps

1. 完成所有主 child tasks 的 path-driven contract 迁移。
2. 对每条 workstream 补足最小 `info.md` / `research.jsonl`，让后续执行不再依赖隐式上下文。
3. 将 runtime 主线的 warning 清理和回归矩阵作为第一个业务稳定化收口目标。
