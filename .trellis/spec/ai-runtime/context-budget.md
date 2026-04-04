# Context Budget

## Goal

Inject the smallest context that preserves correctness.

## Rules

- System prompt additions must be budgeted.
- Tool awareness and capability summaries should be injected once per turn, not every round.
- Old history should be summarized before it crowds out active work.
- Tool results must be size-limited; large raw payloads are not valid default context.
- Directory-wide spec loading is not allowed in default governance flows.

## Priority Order

1. current turn and active intent
2. minimal system/runtime rules
3. current page or active external context
4. compacted history
5. memory/RAG extras

## Prohibited Patterns

- full workflow injection at session start
- full spec-index injection at session start
- full file bodies for every referenced context file
- repeated capability/tool rule duplication across system prompts, hooks, and skills
