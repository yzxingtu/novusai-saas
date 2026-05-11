# Business Modules

This directory is the sanctioned root for downstream customer or vertical
business code in forks of `novusai-saas-yudi`.

Use this directory when a project needs real business modules that are not part
of the shared SaaS platform core. Examples include ecommerce ERP, industry
workflows, customer portals, private operational modules, or customer-specific
domain services.

## Rule

- Put customer or vertical business code in `business/<project-code>/`.
- Keep Yudi SaaS core code in `backend/`, `frontend/`, and shared platform
  packages.
- Put deployment/config/seed/branding overlays in `customer/<project-code>/`.
- Put reusable plugins, connectors, or skill packages in `extensions/` when
  they are not specific to one project.
- If the work changes shared SaaS behavior, fix it upstream in Yudi first.

## Expected Module Layout

```text
business/<project-code>/
├── README.md
├── backend/
├── frontend/
├── shared/
└── adapters/
    └── yudi-plugin/
```

The `adapters/yudi-plugin/` directory is only integration glue. The business
module itself should live in `backend/`, `frontend/`, and `shared/`.

Start new projects from `business/_template/`.
