# PRD

## Goal

Make the main Yudi repository define clear filesystem roots for downstream
customer or vertical business code, so future customer projects do not mix
business modules into Yudi SaaS core directories.

## Requirements

- Add a root `business/` directory for real customer or vertical business code.
- Add a root `customer/` directory for deployment/config/seed/branding overlays.
- Add a root `extensions/` directory for reusable non-core packages.
- Document that plugin adapters are integration glue, not the required shape of
  all business code.
- Update Trellis governance and customer fork docs to point developers to these
  roots.
- Keep shared SaaS defects and platform hooks upstream-first in Yudi.

## Acceptance Criteria

- Root directories and templates exist.
- README and customer fork policy mention where business code belongs.
- PR template asks whether downstream code is placed in the sanctioned roots.
- Validation records path checks and contradiction scans.
