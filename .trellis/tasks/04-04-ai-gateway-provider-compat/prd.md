# Multi-Model Runtime Overrides

## Goal
Replace the GPT-specific compatibility field approach with a structured multi-model runtime override system that works for the current OpenAI-compatible adapter family and leaves clear extension points for future native adapters.

## Requirements
- Keep following `.trellis` workflow and project coding standards.
- Treat `AIModel.code` as the upstream model id shown and edited in admin model management.
- Store model-specific runtime overrides in `AIModel.config.runtime_overrides`.
- Allow duplicate model codes across different providers while keeping provider-local uniqueness for active rows.
- Do not auto-fix provider `base_url` by appending `/v1`; keep manual configuration and improve diagnostics instead.
- Support legacy rows like `gpt-5.4-xhigh` at runtime and in the admin edit form through compatibility fallback.
- Ensure gateway test, health probe, and runtime logs show effective upstream model parameters plus applied/ignored override diagnostics clearly.
- Keep the UI in a structured advanced configuration mode instead of exposing raw JSON editing.
- Only show model-family-specific runtime parameters when they actually apply.

## Acceptance Criteria
- [ ] Admin can create and edit models with upstream model id plus structured runtime overrides and see values round-trip correctly.
- [ ] Runtime requests use `AIModel.code` plus `AIModel.config.runtime_overrides` when building upstream OpenAI-compatible requests.
- [ ] Legacy `gpt-5.4-xhigh` rows still work without one-off data backfill.
- [ ] Models with the same code can exist under different providers, but duplicate active codes under the same provider are rejected.
- [ ] Provider diagnostics and health results distinguish base URL misconfiguration from model-parameter incompatibility.
- [ ] Unsupported model families ignore incompatible overrides and surface clear diagnostics instead of silently appearing configurable.
- [ ] Targeted backend and frontend tests cover request rewriting, CRUD round-trip, uniqueness, diagnostics, structured advanced config, and legacy fallback.

## Technical Notes
- Backend touches include `AIModel` uniqueness, repository/service validation, gateway/model lookup, OpenAI adapter request planning, health checks, and model test diagnostics.
- Frontend touches include `/admin/ai/models`, structured advanced runtime config, providers warnings, health types/UI, API typings, and i18n.
- No automatic `/v1` normalization is allowed.
