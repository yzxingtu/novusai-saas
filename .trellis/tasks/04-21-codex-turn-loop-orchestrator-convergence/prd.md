# Codex Turn Loop And Orchestrator Convergence

## Goal

把聊天核心继续收敛为 codex-main 风格的统一 turn loop / tool payload /
budget owner / stop-condition owner。核心原则是：聊天核心只保留通用运行时职责，
不再持有“当前页面该怎么理解”的逻辑，也不再在不同入口各自补一层 live truth。

## Current Gap

当前仓库虽然已经把大量 page、skill、memory seam 外推到了更明确的 owner，
但核心入口仍有剩余 glue：

1. command / dispatcher / stream bootstrap / prepare_execution 仍保留部分各自 patch-up。
2. budget、termination、continuation、fallback 证据仍可能被入口层二次拼装。
3. live routing 真相虽然已经大幅收敛，但核心入口仍可能保留过多“兼容式解释”。

## Write Scope

- `backend/app/ai/engine/dispatcher.py`
- `backend/app/ai/engine/task.py`
- `backend/app/ai/engine/prepare_execution_pipeline.py`
- `backend/app/ai/runtime/query_engine.py`
- `backend/app/ai/runtime/protocol_*.py`
- `backend/app/services/ai/agent_chat_stream_bootstrap_service.py`
- 对应 runtime / stream / prepare-execution tests

## Requirements

1. command、dispatcher、stream bootstrap、prepare_execution 必须共享同一套
   runtime turn contract，不允许各自保留 live routing patch path。
2. 核心 turn loop 只保留统一事件协议、工具协议、预算治理、停止条件，
   不得重新承担 page/browser 语义判断。
3. `turn_record`、termination、budget、continuation、fallback 证据必须由
   canonical turn session 产出，调用方只能投影，不能重建第二份 truth。
4. 允许保留 catalog/warmup/health-check 类型入口，但这些路径不得成为 live
   tool routing 或 live selected-skill truth。
5. 不得新增 prompt-hint、page-local hint、legacy fallback 驱动的核心入口旁路。

## Acceptance

1. tool-bearing turn、direct-reply turn、page turn、stream turn 在不同入口下产出的
   selected tools / selected skills / termination reason 一致。
2. 核心入口代码不再直接消费 `suggested_tools`、`page_key -> session` fallback、
   prompt-hint-led recovery 或其他 page-local live truth。
3. `turn_record` 与最终 diagnostics / summary 在 sync 与 stream 路径上保持一致，
   不需要入口层二次修补。
4. runtime contract、structured orchestration、stream runtime 回归保持绿灯。
