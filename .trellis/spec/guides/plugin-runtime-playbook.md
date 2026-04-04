# Plugin Runtime Playbook

Use this guide when a task touches plugin manifests, runtime loading, permissions,
menu/title localization, release artifacts, or plugin browser regression.

## Canonical Rule

Plugin truth must come from the plugin manifest and the host runtime contract.
Do not split the truth across host menu files, ad-hoc frontend constants, or
inline AI notes.

## Read Order

1. Target plugin `backend/plugins/{plugin_name}/plugin.yaml`
2. Host runtime consumers:
   - `/permissions/menus`
   - `/plugins/slots`
   - `ensurePluginRoutes()`
   - `loadPluginComponents()` / `getPluginComponent()`
3. Relevant backend/frontend indexes:
   - `.trellis/spec/backend/index.md`
   - `.trellis/spec/frontend/index.md`

## Required Contracts

### Manifest As Truth

- Pages live in `extensions.frontend.pages[*]`
- Menu definitions live in `pages[*].menu`
- Page title comes from `pages[*].title`
- Menu title comes from `pages[*].menu.title`
- Dev entry comes from `extensions.frontend.dev.entry`
- Release manifest comes from `extensions.frontend.release.manifest`

Do not introduce or revive legacy fields such as `frontend.menus`,
`frontend.standalone_pages`, `frontend.admin.entry`, `frontend.tenant.entry`, or
`frontend.npm_dependencies`.

### Assets And Scope

- Authenticated plugin UI must use `/plugin-assets/...` with `{ endpoint }`
- Public plugin UI must use `/plugin-public-assets/...` with `{ publicEndpoint }`
- `endpoint` and `publicEndpoint` are mutually exclusive
- Loader cache keys must include both scope and runtime signature
- `setup()` success is the only time runtime cache may be committed

### Permissions

- Menu visibility, page accessibility, and runtime gate are separate checks
- `pages[*].menu` implies the page access code must bridge back to the menu code
- First screen requests must gate on permission before issuing API calls
- CTA visibility must consider both permission and current state

### Localization

- `pages[*].title` and `pages[*].menu.title` must provide at least `zh-CN` and `en`
- Plugin-internal locale registration uses `plugin.{manifest-name}`
- Host menu titles do not belong in backend `menu.json`
- Language switches must update sidebar, breadcrumb, tab title, page heading,
  and `document.title`

### Release Contract

Run all of these when plugin runtime or packaging changes:

```bash
novusai plugin validate backend/plugins/{name}
novusai plugin build backend/plugins/{name}
novusai plugin pack backend/plugins/{name} --release
```

Confirm `frontend/dist/plugin.manifest.json` exists and that every declared
entry/css/asset/component is real.

## Browser Regression Minimum

At minimum, verify:

1. Menu entry
2. Direct URL
3. Hard refresh
4. Language switch
5. Public asset auth/cookie behavior when a public entry exists

## Anti-Patterns

- Copying manifest text into host menu locale files
- Treating visible menu entry as proof the runtime gate is correct
- Reusing public asset paths for authenticated pages
- Shipping a plugin without validate/build/pack regression
- Depending on a deleted compatibility playbook instead of this guide
