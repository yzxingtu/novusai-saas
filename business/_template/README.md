# Business Module Template

Copy this directory to `business/<project-code>/` in a customer or vertical
product fork.

Use this for real business code that should not be mixed into the Yudi SaaS
core directories.

## Layout

- `backend/`: backend domain code, services, repositories, tasks, and tests.
- `frontend/`: frontend pages, composables, API adapters, and module UI.
- `shared/`: cross-layer contracts, enums, payload examples, and templates.
- `adapters/yudi-plugin/`: Yudi plugin runtime adapter metadata and glue.

## Boundary

Business code may depend on stable Yudi APIs and extension points. It must not
patch shared SaaS internals directly. If a shared hook is missing, implement the
hook in Yudi upstream first and sync the downstream project afterward.
