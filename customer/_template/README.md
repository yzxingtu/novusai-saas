# Customer Overlay Template

Copy this directory to `customer/<project-code>/` in a customer fork.

Use this directory for deployment, config, seed, branding, and delivery
overlays only. Real business code belongs in `business/<project-code>/`.

## Layout

- `overlays/`: Docker, Helm, env, reverse-proxy, and platform-specific
  deployment overlays.
- `seeds/`: tenant bootstrap, feature defaults, demo data, and import fixtures.
- `decisions/`: customer fork decisions and sync rationale.

Every customer fork should keep `.yudi-base` at repository root and verify it
with `ops/verify-yudi-base.ps1`.
