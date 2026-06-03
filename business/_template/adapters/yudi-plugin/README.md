# Yudi Plugin Adapter

Put Yudi plugin runtime adapter files here when the business module is exposed
through the Yudi plugin system.

This adapter should contain only integration glue:

- `plugin.yaml`
- page, route, permission, and menu declarations
- thin imports or entrypoints into the business module

The business implementation belongs in the sibling `backend/`, `frontend/`,
and `shared/` directories. Plugin framework changes belong in Yudi upstream.
