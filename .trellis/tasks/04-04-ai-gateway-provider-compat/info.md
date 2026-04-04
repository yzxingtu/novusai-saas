# Implementation Notes

## Boundary

This workstream owns provider/model compatibility and the admin/runtime
contract around effective upstream model parameters.

It may change:

- `AIModel.config.runtime_overrides`
- provider diagnostics and health output
- runtime request planning inside OpenAI-compatible adapters
- admin model/provider form and monitoring surfaces that consume those fields

It must not silently change:

- the runtime intent planner/state machine contract already established by
  `04-04-04-04-ai-orchestration-runtime-rebuild`
- page-awareness read/navigation/write semantics that belong to the
  page-awareness workstream

## Key Risks

- Legacy model codes appear to work in CRUD but fail at runtime.
- Admin forms expose overrides that do not actually apply to the chosen model.
- Provider health noise is mistaken for orchestration failure.
- Duplicate model codes regress uniqueness rules across providers.
