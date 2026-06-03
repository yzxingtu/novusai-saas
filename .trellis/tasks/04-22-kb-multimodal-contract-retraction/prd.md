# Retract Retired KB Audio/Video Model Fields From Live Contracts

## Goal
Remove the retired knowledge-base audio/video model fields from public admin and
tenant contracts, while preserving an explicit fail-closed path if old clients
still attempt to submit them.

## Requirements
- Do not keep `audio_model_id`, `video_model_id`, `audio_model_name`, or
  `video_model_name` in live KB response payloads for the new SaaS.
- Do not keep frontend API types advertising those retired fields once the UI
  and ingest runtime no longer support them.
- Do preserve explicit write-time rejection for legacy audio/video config
  submissions instead of silently ignoring them.
- Keep the supported embedding/vision model contract intact.

## Acceptance Criteria
- [ ] Tenant/admin KB response payloads and projector helpers no longer emit the
      retired audio/video model fields.
- [ ] Frontend admin/tenant KB API typings no longer expose the retired fields.
- [ ] Backend request schemas no longer advertise those fields in public schema
      surfaces, but old submissions are still rejected explicitly.
- [ ] Verification covers both the contract retraction and the explicit
      rejection path.
