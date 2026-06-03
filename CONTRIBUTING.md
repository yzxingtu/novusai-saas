# Contributing to NovusAI SaaS

**Languages:** English · [简体中文说明见 README.md 贡献相关章节](README.md#参与贡献)

Thank you for your interest in improving this project. This document describes how we expect contributions to be made.

## Getting started

1. Read [README.md](README.md) for prerequisites and **Quick start** (Docker, backend venv, frontend `pnpm`).
2. Review the relevant backend or frontend source, tests, and README sections before changing code.

## Upstream-first contribution rules

`novusai-saas-yudi` is the canonical multi-tenant SaaS upstream. Customer
projects should remain thin forks or overlays, with customer-specific workflows,
branding, deployment overlays, configuration, seed data, and plugins kept in the
customer repository.

- Develop common platform bug fixes and shared SaaS features in Yudi first.
- Keep customer-only workflows, branding, deployment overlays, and plugins in
  the customer repository.
- Triage ambiguous changes explicitly before implementation so they land
  upstream or downstream intentionally.
- Reproduce common bugs in Yudi with a focused regression test, fix and verify
  them here, then synchronize customer repositories from the Yudi release or
  hotfix line.
- Do not keep long-lived downstream patches to auth, tenant isolation, task
  queues, notifications, AI runtime, plugin framework, migrations, Docker
  baseline, or shared UI.

For the full policy, release/backport steps, and customer sync runbooks, use the
current docs under [`docs/guides/`](docs/guides/) and
[`docs/operations/`](docs/operations/) instead of copying policy text into PRs.

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

## Tests

- **Backend:** from `backend`, run `pytest` before submitting. Add or update tests for bug fixes and new behavior where practical.
- **Frontend:** from `frontend`, run `pnpm test:unit` when your change affects testable logic.

## Internationalization and comments

- Do not hardcode user-visible strings: frontend uses `$t()` / `t()`, backend uses `_()`.
- New comments in code should be short, useful, and written only when they clarify non-obvious behavior.

## Security

Do **not** open public issues for security vulnerabilities. See [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under the same terms as the project — see [LICENSE](LICENSE).
