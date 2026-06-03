# Customer Overlays

This directory is for downstream customer delivery overlays in forks of
`novusai-saas-yudi`.

It is not the primary business-code directory. Real customer or vertical
business code should live under `business/<project-code>/`.

Use `customer/<project-code>/` for:

- deployment overlays
- environment examples without secrets
- tenant bootstrap and seed data
- branding assets and customer copy
- customer acceptance notes
- fork decisions and sync records

Do not put long-lived core patches here. Do not hide business modules here when
they should live under `business/<project-code>/`.

Start new customer overlays from `customer/_template/`.
