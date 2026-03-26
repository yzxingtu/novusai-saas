# Contributing to NovusAI SaaS

**Languages:** English · [简体中文说明见 README.zh-CN.md 贡献相关章节](README.zh-CN.md#参与贡献)

Thank you for your interest in improving this project. This document describes how we expect contributions to be made.

## Getting started

1. Read [README.md](README.md) for prerequisites and **Quick start** (Docker, backend venv, frontend `pnpm`).
2. Skim the rule index [`.cursor/rules/novusai-saas.md`](.cursor/rules/novusai-saas.md) so your changes match layering, i18n, and AI/plugin boundaries.

## Branching and pull requests

- Base your work on the branch your team uses for integration (often `develop`).
- Use short-lived branches such as `feature/…` or `fix/…`.
- Open a **Pull Request** with a clear description, linked issues (if any), and screenshots for UI changes when helpful.
- Keep PRs focused; large refactors should be discussed first.

## Commits

- Prefer clear, imperative subject lines (e.g. `fix: handle empty tenant id in export`).
- If your repo uses **commitlint** / **czg** (see `frontend` workspace tooling), follow the same conventions as other commits in the history.

## Code style

| Area | Tooling | Notes |
|------|---------|--------|
| Backend | Ruff (lint + format), pytest | Run from `backend`: `ruff check .`, `ruff format .`, `pytest` |
| Frontend | ESLint / Prettier via `pnpm lint` | Run from `frontend`: `pnpm lint` |

Deeper conventions:

- Backend: [docs/guides/backend-development.md](docs/guides/backend-development.md), [`.cursor/skills/novusai-saas/references/backend-spec.md`](.cursor/skills/novusai-saas/references/backend-spec.md)
- Frontend: [`.cursor/skills/novusai-saas/references/frontend-spec.md`](.cursor/skills/novusai-saas/references/frontend-spec.md)

## Tests

- **Backend:** from `backend`, run `pytest` before submitting. Add or update tests for bug fixes and new behavior where practical.
- **Frontend:** from `frontend`, run `pnpm test:unit` when your change affects testable logic.

## Internationalization and comments

- Do not hardcode user-visible strings: frontend uses `$t()` / `t()`, backend uses `_()`.
- New comments in code should follow the project’s bilingual convention; see [docs/comment-compliance-remaining.md](docs/comment-compliance-remaining.md) and the specs linked from [`.cursor/rules/novusai-saas.md`](.cursor/rules/novusai-saas.md).

## Security

Do **not** open public issues for security vulnerabilities. See [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under the same terms as the project — see [LICENSE](LICENSE).
