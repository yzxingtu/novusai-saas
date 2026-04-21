# Design Notes

## Why A Separate Task

This seam was found during the post-commit audit after
`682b9ff6a Externalize browser connector live transport`.

Reopening WS4 would blur a checkpoint that is already stable:

1. live action transport is already explicit-`page_session_id`;
2. `page_key -> page_session_id` recovery is already gone;
3. WS4 closeout is already documented and committed.

The remaining issue is narrower: join acknowledgement still uses `page_key` as
part of the frontend readiness contract. That deserves a targeted follow-up
task instead of silently reopening the completed workstream.

## Ownership

This task sits between the connector boundary and frontend live-truth work:

1. it depends on the WS4 connector contract freeze;
2. it removes a live handshake seam before WS6 freezes the frontend truth
   chain;
3. it should not reintroduce any page-key compatibility logic in backend or
   frontend transport helpers.
