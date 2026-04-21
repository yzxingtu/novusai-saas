# Close Out Placeholder Audio/Video Describers In Knowledge-Base Ingest

## Goal
Bring knowledge-base audio/video ingest back to honest live behavior by either
implementing real audio/video describers or retracting the configuration
surfaces that currently imply those paths work.

## Requirements
- Do not keep audio/video model selectors exposed in admin or tenant knowledge
  base forms if the ingest path still cannot extract text from those files.
- Do not let placeholder describers remain on the live parse path for the new
  SaaS once multimodal ingest is advertised as configurable behavior.
- Error copy and product surfaces must describe the real system state instead of
  implying that model configuration alone will make ingest work.
- Verification must cover the end-to-end ingest behavior for audio/video
  documents, not just unit-level model lookup.

## Acceptance Criteria
- [ ] Audio/video knowledge-base ingest either produces real text output through
      implemented describers or is explicitly blocked before users can configure
      those modes.
- [ ] Admin and tenant knowledge-base forms no longer expose non-working
      audio/video configuration surfaces.
- [ ] User-facing errors and help text match the real runtime behavior.
- [ ] Validation proves the live parser/processor path no longer relies on
      placeholder describers that always return empty content.
