# Repository Stabilization Control Plane

## Goal

建立全仓脏改稳定化总控，把当前已经分散在 backend、frontend、AI runtime、plugin、permission 与 Trellis 治理层的并行改动拆成可归属、可验证、可回滚的分轨工作流。

## Requirements

- 建立一个 umbrella task，统一托管以下工作流：
  - `04-04-04-04-ai-orchestration-runtime-rebuild`
  - `04-04-ai-gateway-provider-compat`
  - `04-03-page-awareness-navigation-v2`
  - `04-03-04-03-plugin-system-audit-hardening`
  - `04-04-permission-tree-fix`
  - `04-04-tenant-org-permission-assignment`
- 建立文件归属矩阵，明确每条工作流的 owned files、风险、合并顺序与验证责任。
- 将上述 child tasks 迁移到 path-driven Trellis 契约，去掉 legacy `finish/create-pr` 生命周期。
- 冻结所有暂未归属的脏改与 sibling tasks，禁止在稳定化期间继续扩散。
- 明确整体合并策略：先单轨验证，再总装验收；禁止整仓一次性合并。
- 新控制面必须承认并保留当前 AI runtime/Trellis 新架构方向，不允许回流到 regex-first planner、whole-turn retry、marker loop 等旧行为。

## Acceptance Criteria

- 本任务的 `task.json`、`prd.md`、`info.md`、`ownership-matrix.md` 与 curated JSONL context 已就位。
- 六个主 child tasks 已全部挂载到 umbrella task 下。
- 需要继续实施的 child tasks 已迁移到 path-driven Trellis 契约，并具备所需 artifacts。
- `ownership-matrix.md` 能覆盖五条主工作流以及 frozen backlog。
- `.trellis/spec/guides/repo-stabilization-workstreams.md` 已成为 canonical guide，并在 guides index 中可见。
- 总控文档明确写出冻结规则、单轨验收规则、总装顺序与 warning 政策。

## Out Of Scope

- 在本任务内直接完成所有业务子系统代码收尾
- 回滚已经完成的 AI runtime/Trellis 架构替换
- 为未归属任务补做业务实现而不是先冻结边界
