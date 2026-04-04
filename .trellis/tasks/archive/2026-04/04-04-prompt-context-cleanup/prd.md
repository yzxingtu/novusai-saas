# Prompt Context Cleanup

## Goal

Finish prompt-contract and context-injection cleanup so runtime context is minimal, one-shot, and free of dead legacy contracts.

## Requirements

- Remove `tool_awareness` templates, loader registration, and dead references.
- Keep `tool_runtime_summary` as the only runtime tool summary contract.
- Preserve safe capability rendering and concise capability descriptions.
- Eliminate duplicated contracts that describe the same runtime rule.

## Ownership

- Allowed files:
  - `backend/app/ai/prompt_contracts/*`
  - `backend/app/ai/capabilities/description_builder.py`
- Do not edit `backend/app/ai/engine/base.py`; hand integration notes back to the main agent if needed.

## Acceptance

- No active runtime contract references `tool_awareness`.
- Contract set is compact and non-duplicative.
- Capability rendering remains safe and concise.
