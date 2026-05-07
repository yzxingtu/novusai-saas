# AI Real-Dialogue Smoke Scenarios

This ledger is a local production-acceptance reference for AI real-dialogue
smoke. The default executable smoke set is the canonical ledger under
`.trellis/tasks/04-23-codex-llm-first-dialogue-replan/`; this file keeps the
same acceptance semantics visible under `ops/`.

## Gate Semantics

This file is only the real-dialogue scenario ledger. Ledger presence may satisfy
the scenario-ledger prerequisite, but it never satisfies provider credential,
agent selector, or archived execution-report gates. If provider credentials,
agent selector, or a strict passed `ai-real-dialogue-smoke/v1` report are absent,
AI dialogue production acceptance remains `blocked`.

Capability smoke and manifest checks are separate readiness checks. They cannot
satisfy `ai_real_dialogue_smoke_execution` and cannot make production acceptance
`passed`.

## Scenario 1

- scenario_id: `SCENARIO-001-runtime-capability-smoke`
- priority: `must-pass`
- user_input: `说明一下这个系统的核心能力，并保持回答简洁。`
- required_capabilities:
  - real provider credential configured for the selected agent
  - `python -m app.cli ai smoke --agent-id <id> --json` or
    `python -m app.cli ai smoke --agent-code <code> --json` can resolve the
    agent
- expected_observable_outcome:
  - capability smoke embedded in the real-dialogue report is green or passed
  - JSON report contains provider call-log evidence for the real dialogue turn
  - output does not contain provider credential errors, missing-agent errors, or
    mocked-provider markers

## Scenario 2

- scenario_id: `SCENARIO-002-short-answer-real-turn`
- priority: `must-pass`
- user_input: `用两句话介绍 NovusAI SaaS 当前适合企业使用的能力。`
- required_capabilities:
  - real provider credential configured
  - selected agent is enabled for the tenant or global runtime scope
- expected_observable_outcome:
  - a real assistant answer is produced
  - answer is concise and relevant to enterprise SaaS usage
  - turn does not fail with quota, provider, routing, or empty-answer errors

## Scenario 3

- scenario_id: `SCENARIO-003-tool-policy-guard`
- priority: `must-pass`
- user_input: `如果当前没有联网搜索工具，请不要编造实时新闻来源。`
- required_capabilities:
  - real provider credential configured
  - runtime capability manifest is available for the selected agent
- expected_observable_outcome:
  - assistant does not fabricate live web results or citations
  - if online search is unavailable, the response clearly stays within supported
    capabilities
  - runtime diagnostics do not expose retired current-page or online-search
    capability as a live tool unless explicitly supported by the manifest
