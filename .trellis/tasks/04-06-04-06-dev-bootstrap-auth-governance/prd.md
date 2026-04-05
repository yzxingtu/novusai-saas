# Dev-only Bootstrap Credential Governance

## Objective

- Provide a documented, constrained dev-only bootstrap credential flow for local
  Playwright/Chrome E2E so developers can seed authenticated sessions without
  relying on production secrets or captcha-prone logins.
- Keep the existing `/auth/login` contract as a fallback so non-local/CI suites
  can continue to use real credentials.

## Requirements

1. The bootstrap endpoints must only respond when `APP_ENV=development` and an
   explicit opt-in flag `DEV_BOOTSTRAP_AUTH_ENABLED=true` is set.
2. Allowlist requests to loopback hosts (`localhost`, `127.0.0.1`, `::1`) and
   local dev hosts (`*.local`), and require developer-specific secrets defined
   only in local `backend/.env`:
   - `DEV_ADMIN_BOOTSTRAP_SECRET`
   - `DEV_TENANT_BOOTSTRAP_SECRET`
   Tracked `.env.example` and docs may only contain placeholders; never commit
   real secrets.
3. The backend target accounts must also be local-only configuration, not
   request-driven user selection:
   - `DEV_ADMIN_BOOTSTRAP_USERNAME`
   - `DEV_TENANT_BOOTSTRAP_USERNAME`
   - `DEV_TENANT_BOOTSTRAP_TENANT_CODE`
4. Bootstrap JWTs must expire with the same (or shorter) TTL as ordinary login
   tokens. Do not issue forever tokens or drop the `exp` claim; keep refresh and
   rotation flows active so the credentials cannot live indefinitely.
5. Document the feature flag, host guard, endpoint paths, and `.env` secret in
   Trellis guides so
   each developer can reproduce the handshake without sharing confidential data.
6. Playwright and local browser helpers should prefer:
   - `POST /admin/auth/dev/bootstrap`
   - `POST /tenant/auth/dev/bootstrap`
   on supported workstations, but `/auth/login` remains the fallback when the
   flag is unset or the suite runs in CI/remote environments.

## Constraints

- Sensitive values for the bootstrap secret, feature flag, and any generated
  tokens must never be committed. Use placeholders or `XXXX`-style hints in docs.
- The bootstrap flow must be an explicit opt-in; default configs should keep it
  disabled so shared and production runners are unaffected.
- Preserve existing auth token routing so backend services and frontend apps can
  detect when to switch between bootstrap vs `/auth/login`.

## Acceptance Criteria

- [ ] Backend only serves bootstrap tokens when a developer workstation opts in
  and when the request originates from a loopback host with a valid local secret.
- [ ] Bootstrap JWTs honor expiration and refresh expectations; tests fail if `exp`
  is missing or set to a non-expiring value.
- [ ] Playwright/local helpers prefer the bootstrap path but fall back to
  `/auth/login` when the feature flag or host guard blocks the bootstrap attempt.
- [ ] Trellis specs and `.env.example` document the new flag, allowlist, and local
  secret requirement. Operations teams can read the PRD/info docs to understand
  why this governance exists.
