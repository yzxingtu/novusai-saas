# Admin Org Member AI Switch Runtime Smoke - 2026-05-02

## Scope

Reported regression: `PUT /admin/organization/1/members/2` with
`"ai_enabled": false` returned 200, but the response omitted `ai_enabled` and the
member still appeared AI-enabled.

## Diagnosis

- Before backend restart, `http://localhost:8000/openapi.json` showed
  `AdminOrgNodeUpdateMemberRequest` without `ai_enabled`.
- The running uvicorn process logged runtime identity
  `codex/admin-account-ai-availability@ef9a4a7d5`, while the committed
  account-AI implementation is `b24c995a4`.
- Root cause for the observed local failure was a stale backend process serving
  the pre-feature route/schema contract.

## Runtime Verification

- Restarted backend on `http://localhost:8000`.
- Startup logs show runtime identity
  `codex/admin-account-ai-availability@b24c995a4`.
- OpenAPI now includes `AdminOrgNodeUpdateMemberRequest.properties.ai_enabled`
  as `boolean | null`.
- Using local development admin bootstrap auth, sent:

```json
{
  "email": "1034010678@qq.com",
  "phone": null,
  "nickname": null,
  "is_active": true,
  "ai_enabled": false,
  "avatar": "27",
  "org_node_id": 1
}
```

to `PUT /admin/organization/1/members/2`.

## Observed Result

```json
{
  "update_code": 0,
  "update_ai_enabled": false,
  "listed_ai_enabled": false,
  "member_found": true
}
```

Database check after the request:

```json
{
  "id": 2,
  "username": "adminaa",
  "ai_enabled": false
}
```

## Status

PASS for this reported runtime path. This is a targeted local API smoke, not a
full browser Playwright e2e run.
