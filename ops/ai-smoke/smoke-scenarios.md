# AI Real-Dialogue Smoke Scenarios

This ledger is the local production-acceptance entry point for AI
real-dialogue smoke. It does not replace the living bug ledger under
`.trellis/tasks/04-23-codex-llm-first-dialogue-replan/`; it gives the
production probe a stable scenario source that is not ignored by git.

## Scenario 1

- scenario_id: `PROD-AI-SMOKE-001-basic-provider-dialogue`
- user_input: `请用一句话回答：NovusAI 生产验收 smoke ping。`
- required_capabilities:
  - real provider credential configured through the runtime provider config or
    environment
  - `AI_SMOKE_AGENT_ID` or `AI_SMOKE_AGENT_CODE` selector
  - backend database and Redis available
- expected_observable_outcome:
  - command completes without provider/tool runtime exception
  - assistant text is non-empty and directly answers the ping
  - generated report records `overall_status: passed`

## Scenario 2

- scenario_id: `PROD-AI-SMOKE-002-runtime-capability-smoke`
- user_input: `请简要说明当前智能体可用能力，不要编造不存在的工具。`
- required_capabilities:
  - same provider and agent selector prerequisites as Scenario 1
  - `novusai ai smoke --agent-id/--agent-code --json` command available
- expected_observable_outcome:
  - runtime capability smoke reports green or passed
  - report does not expose retired current-page/page-operation or online-search
    tools unless they are explicitly installed as supported runtime capabilities
