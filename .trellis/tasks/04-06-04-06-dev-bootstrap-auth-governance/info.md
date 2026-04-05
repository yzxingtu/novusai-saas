# Implementation Notes

## Governance Scope

- Define dev-only bootstrap credentials as part of Trellis quality guidelines so
  both backend and frontend teams enforce the same guard rails.
- Update `.env.example` and developer setup docs with placeholder config only:
  - `DEV_BOOTSTRAP_AUTH_ENABLED`
  - `DEV_BOOTSTRAP_ALLOWED_HOSTS`
  - `DEV_ADMIN_BOOTSTRAP_SECRET`
  - `DEV_ADMIN_BOOTSTRAP_USERNAME`
  - `DEV_TENANT_BOOTSTRAP_SECRET`
  - `DEV_TENANT_BOOTSTRAP_USERNAME`
  - `DEV_TENANT_BOOTSTRAP_TENANT_CODE`
  so onboarding stays repeatable without sharing real values.
- Playwright helpers should default to the new bootstrap handshake when running
  on localhost but keep `/auth/login` as the fallback for CI, remote workstations,
  or when the flag is unset.

## Key Safeguards

- Loopback/local-dev host enforcement (`localhost`, `127.0.0.1`, `::1`, `.local`)
  stops external environments from reusing the bootstrap endpoint.
- The bootstrap secret stays purely local; tracked files only show placeholders and
  instructions for generating a developer-specific value.
- The request body stays minimal: `{ "bootstrap_secret": "..." }`. Backend-side
  env config decides which admin / tenant admin account may be issued.
- JWT expiration must match normal session TTLs so bootstrap tokens continue to
  obey refresh/rotation expectations; issuing forever tokens is disallowed.
  Operators should see invalid tokens rejected immediately.

## Verification Checklist

- [ ] Backend unit/integration tests ensure bootstrap routes are gated by
  `APP_ENV`, the opt-in flag, and the host allowlist.
- [ ] Playwright/local helpers have a feature toggle to pick the bootstrap path
  when available and revert to `/auth/login` otherwise.
- [ ] Trellis docs (`.trellis/spec/*`) mention the new governance so any task
  touching auth resets can align with the same rule set.
