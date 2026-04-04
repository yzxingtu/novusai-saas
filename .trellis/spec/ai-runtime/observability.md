# Observability

## Goal

Operators should be able to inspect one turn without reconstructing it from scattered warnings.

## Required Diagnostics

- intent plan
- execution path
- candidate tools
- selected tools
- budget snapshots
- tool rounds
- retry events
- failure classification
- partial-exit reason
- provider events when present

## Logging Rules

- provider failure and orchestration failure must be recorded separately
- diagnostics must be structured and machine-readable
- compact CLI views should prefer summaries over full raw payloads

## Prohibited Patterns

- “warning only” observability for major recovery events
- requiring manual log stitching to understand one turn
- mixing provider instability with planner/recovery defects in one bucket
