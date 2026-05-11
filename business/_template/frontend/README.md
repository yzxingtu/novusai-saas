# Frontend Business Code

Put project-specific frontend domain code here.

Suggested split:

- `src/pages/`: thin route/page shells.
- `src/modules/`: focused business modules.
- `src/composables/`: data loading and workflow logic.
- `src/api/`: business API adapters.
- `src/components/`: module-local UI components.

Do not cross-import another surface's business internals. Shared shell, route
guard, API client, or component changes belong in Yudi upstream first.
