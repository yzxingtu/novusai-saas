# Codex Thread Memory Owner Convergence

## Goal

把当前已经 normalized 的 `memory_runtime_policy` / `thread_memory_state`
继续推进为更明确的 thread-owned memory lifecycle。目标是让 startup priming、
capture eligibility、recall gating、pollution guard、read-model projection
都围绕 thread owner 运作，而不是继续停留在“请求 flag + assistant metadata +
thread snapshot 的松耦合组合”。

## Current Gap

当前已经完成了：

1. `memory_runtime_policy` 统一 owner；
2. assistant metadata 和 `thread_memory_state` 持久化；
3. conversation detail 可显式投影 source / freshness；
4. polluted turn 的 durable capture 抑制。

剩余 gap 在于：

1. thread owner 还偏轻量 snapshot，没有更强的 lifecycle/state transition；
2. startup priming、recall、capture、background consolidation 还没完全收口；
3. 后续 runtime-core cleanup 之前，需要先把 memory owner 稳定下来。

## Write Scope

- `backend/app/ai/memory_policy.py`
- `backend/app/ai/context/orchestrator.py`
- `backend/app/services/ai/agent_chat_memory_support.py`
- `backend/app/services/ai/conversation_message_persistence*.py`
- `backend/app/services/ai/conversation_runtime_projection_service.py`
- memory/background pipeline related tests

## Requirements

1. startup priming、long-term recall、session-memory load、capture eligibility、
   pollution guard 必须共享同一份 thread owner state。
2. thread state transition 必须显式可投影，不能再主要依赖 raw request flags 或
   call-site 私有推断。
3. polluted external-context turn 要有统一的 capture / recall 降级策略，
   并保留 machine-readable reason。
4. conversation read-model、error-only fallback、post-turn persistence
   都必须继续显式暴露 source、freshness、mode，必要时还要保留 background state。
5. 不得重新把 memory 绑定回 page-local hints、prompt fixups 或 explicit
   memory intent 之外的隐式旁路。

## Acceptance

1. generic turn、web/plugin polluted turn、error-only turn、post-turn capture
   都服从同一条 thread owner contract。
2. `thread_memory_state` 与 assistant metadata 不再表现为两条竞争的 live truth，
   而是一个 canonical owner 的不同 projection。
3. startup helper、capture helper、conversation detail projection 保持 source/
   freshness/mode 一致。
4. memory gating、agent chat memory scene、conversation detail 回归保持绿灯。
