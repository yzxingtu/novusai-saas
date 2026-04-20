# Codex Capability Pack Startup Owner Convergence

## Goal

把已安装 skill pack / connector capability 继续收敛为单一 startup/live owner
链路。catalog discoverability 可以存在，但不能重新渗回 live routing truth；
resolver、manifest、runtime inventory、diagnostics、capability reporting
必须都明确说出“inventory 是什么、本轮 live 选中了什么、为什么选中”。

## Current Gap

当前已经完成了：

1. turn-level activation seam；
2. startup prefilter；
3. manifest-backed plugin startup preview；
4. runtime inventory 复用统一 `resolve_for_agent(...)`；
5. activation observability 进入 diagnostics / summary。

剩余缺口仍在于：

1. catalog-only metadata 仍可能在部分边界上看起来像 live truth；
2. connector/plugin preview 不完整时，还缺少更强的 bounded discoverability owner；
3. batch/warmup/capability-reporting 与 live tool-bearing turn 的边界还需要继续锁死。

## Write Scope

- `backend/app/ai/skills/**`
- `backend/app/ai/runtime/context_assembler.py`
- `backend/app/ai/runtime/manifest.py`
- `backend/app/ai/runtime/types.py`
- `backend/app/services/ai/runtime_inventory_service.py`
- `backend/app/services/ai/runtime_inventory_service_support.py`
- 对应 skill/runtime inventory/context capability tests

## Requirements

1. startup prefilter、turn activation、runtime manifest、runtime inventory、
   diagnostics 必须共享同一条 inventory vs live owner 链。
2. `Skill.skill_md`、package `SKILL.md`、`prompt_skill`、preview metadata、
   manifest hints 只能作为 catalog/startup/discoverability 输入，不得重新成为
   live selected-tool 或 live selected-skill truth。
3. capability-reporting turn 可以保留 broader inventory，但 tool-bearing turn
   必须在 manifest、summary、diagnostics、read-model 上严格 collapse 到 live subset。
4. unknown preview / connector discoverability 需要通过 bounded catalog surface、
   explicit search、或更强 startup metadata owner 解决，而不是回退到全量 eager resolve。
5. batch warmup、runtime inventory、install-time manifest read-model 允许保留
   catalog 语义，但必须显式标注其非 live 性质。

## Acceptance

1. skill resolver、runtime inventory、capability reporting、prepare-execution、
   conversation detail 对同一 turn 的 inventory/live 解释一致。
2. catalog-only descriptor、preview fields、prompt-skill compatibility inputs
   不再被任何 live runtime summary 当成 selected truth。
3. capability-reporting 与 tool-bearing turn 的差异只体现在显式 owner contract，
   而不是隐式例外逻辑。
4. skill resolver、runtime inventory、context capability 回归保持绿灯。
