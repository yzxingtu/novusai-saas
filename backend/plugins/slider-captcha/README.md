# Slider CAPTCHA Plugin

Chinese version: [README.zh-CN.md](./README.zh-CN.md)

Modern slider puzzle CAPTCHA plugin for NovusAI login flows.

This plugin registers `slider` as a dynamic captcha provider and can be used on:

- Admin login
- Tenant admin login
- Tenant user login
- Tenant user self-registration

## Purpose

This plugin exists to keep slider CAPTCHA behavior inside the plugin boundary instead of hardcoding it into the host project.

The host only provides generic runtime capabilities:

- Captcha provider registration
- Public plugin asset loading
- Public config exposure for login pages
- Generic plugin configuration rendering

The actual slider challenge generation, verification, frontend rendering, bundled backgrounds, and plugin locale messages all live inside this plugin.

## Scope and Endpoint Coverage

- Plugin resource scope: `global_shared`
- Captcha provider code: `slider`
- Supported public endpoints: `admin`, `tenant`, `user`

Effective config mapping:

| Surface | Toggle / Gate | Provider key |
|---|---|---|
| Admin login | `login_captcha_enabled` | `captcha_provider` |
| Tenant admin login | `tenant_captcha_enabled` | `tenant_captcha_provider` |
| Tenant user login | `tenant_captcha_enabled` | `tenant_captcha_provider` |
| Tenant user registration | `user_registration_captcha_enabled` controls whether registration requires captcha; provider still follows tenant login provider | `tenant_captcha_provider` |

Notes:

- Because the plugin scope is `global_shared`, admins can use it and all tenants can use it.
- No tenant assignment table is required for this plugin.

## Runtime Architecture

Runtime flow:

1. `plugin.yaml` declares a custom extension with `type: captcha_provider` and `name: slider`.
2. The host registers the provider metadata at plugin startup.
3. Public config APIs expose the selected captcha provider and, when active, the plugin frontend runtime payload for the login page.
4. Login pages load the plugin frontend dynamically through the host plugin runtime.
5. The plugin frontend registers the `slider` provider component at runtime.
6. The slider component requests `/api/public/captcha/challenge` with `provider_code=slider`.
7. The plugin backend provider creates an in-memory challenge and returns the puzzle payload.
8. The login form submits `captchaChallengeId`, `captchaSolution`, and `captchaProviderCode=slider`.
9. The host auth service re-verifies the solution through the registered provider before login or registration continues.

Key files:

- `plugin.yaml`: plugin manifest, scope, config schema, captcha provider extension
- `backend/captcha_provider.py`: challenge generation and verification
- `frontend/src/SliderCaptcha.vue`: slider UI and public challenge loading
- `frontend/src/index.ts`: runtime provider registration

## Deployment Constraints

This section is critical. The current implementation has real runtime constraints.

### In-memory Challenge Store

The provider stores active challenges in process memory:

- Store location: `backend/captcha_provider.py`
- TTL: 120 seconds
- Challenge state is not shared across workers or instances

Operational impact:

- Single-process deployment works as expected.
- Multi-worker or multi-instance deployment requires sticky sessions, otherwise a challenge can be created on one worker and verified on another worker that does not have the in-memory state.
- Hot reload, worker restart, rolling restart, or pod rescheduling can invalidate active challenges immediately.
- If users report "challenge created successfully but login says captcha invalid/not found", check routing and worker topology first.

Current recommendation:

- Local development: safe
- Single-instance small deployment: acceptable
- Horizontal scaling or multiple worker processes: only use with sticky session routing, or replace the in-memory challenge store with Redis/shared cache before relying on it in production

### Security Positioning

This plugin is currently best treated as a low-to-medium friction login CAPTCHA, not a high-assurance anti-bot control.

Reasons:

- Challenge state is stored in memory only.
- The frontend renders a puzzle-oriented payload and then submits the solved offset back to the host login flow for server verification.
- It improves automation cost and login UX, but it is not designed as a hardened bot-defense product.

If you need stronger protection, the next evolution should include:

- Shared challenge storage such as Redis
- A stronger proof protocol for the slider challenge
- Additional anti-replay and anti-automation hardening

## Development vs Release Runtime

The plugin supports two runtime modes.

### Local Repo / DEBUG Runtime

When the host runs in DEBUG mode, the frontend can load directly from:

- `frontend/src/index.ts`

This is the easiest mode for local repository development and normally does not require `frontend/dist`.

### Release / Production Runtime

For release packaging, the current host contract expects compiled frontend assets under:

- `frontend/dist/index.js`
- `frontend/dist/plugin.manifest.json`

Expected UMD global variable:

- `NovusPlugin_slider_captcha`

Example release manifest:

```json
{
  "format": "novus.plugin.release.v1",
  "entry": "index.js",
  "global_var": "NovusPlugin_slider_captcha",
  "css": [],
  "assets": [
    "assets/slider-bg-01.jpg",
    "assets/slider-bg-02.jpg",
    "assets/slider-bg-03.jpg",
    "assets/slider-bg-04.jpg"
  ]
}
```

If release assets are missing or the manifest is invalid, the plugin frontend cannot be loaded on login pages in production mode.

## Build and Package

### Frontend Build

From the repository root:

```bash
cd backend/plugins/slider-captcha/frontend
pnpm install
pnpm build
```

Build output target:

- `frontend/dist/index.js`
- bundled asset files under `frontend/dist/assets/`

For production packaging, also ensure `frontend/dist/plugin.manifest.json` exists and matches the compiled assets.

### Validate and Package

After the frontend release assets are ready:

```bash
novusai plugin validate backend/plugins/slider-captcha
novusai plugin pack backend/plugins/slider-captcha
```

If you are only using the plugin inside the local repository in DEBUG mode, you can usually skip release packaging and rely on source loading.

## Install and Enable

### In-repo Development Setup

Use this path when the plugin already exists under `backend/plugins/slider-captcha`.

1. Ensure the backend can discover the plugin from the repository plugin directory.
2. Restart the backend if the plugin was added after startup.
3. Open Admin -> Plugin Management.
4. Confirm `slider-captcha` is installed or visible.
5. Enable the plugin.
6. If manifest metadata changed but the UI still shows stale scope or stale manifest data, run plugin repair or re-enable it so the DB metadata syncs again in DEBUG mode.

### ZIP / Release Installation

Use this path when distributing the plugin as an installable package.

1. Build the frontend release assets.
2. Ensure `frontend/dist/index.js` and `frontend/dist/plugin.manifest.json` are included.
3. Package the plugin.
4. Upload and install it from Admin -> Plugin Management.
5. Enable the plugin.

## Configure the Plugin

Open Admin -> Plugin Management -> `slider-captcha` -> Config and set the optional fields described below.

### Config Reference

| Key | Type | Accepted value | Default | Notes |
|---|---|---|---|---|
| `background_1` to `background_4` | string | empty string, public attachment ID, or directly reachable image URL | empty | Each slot overrides one bundled background image. Empty keeps the bundled image for that slot. |
| `square_length` | integer | `36` to `54` | `42` | Main puzzle square size. Larger values increase visual footprint and generally make the gap easier to see. |
| `tolerance_px` | integer | `3` to `12` | `6` | Allowed offset error in pixels. Larger values are easier to pass. |

### Background Override Semantics

The background fields support three cases:

- Empty string: keep the plugin-bundled image for that slot
- Numeric string such as `"123"`: treated as an attachment ID and resolved to `/api/public/attachments/{id}/image`
- Non-numeric string: treated as a raw image URL

Operational recommendations:

- Prefer using the plugin config image picker from the host UI. It stores public attachment IDs and is the safest path for login pages.
- If you configure attachment IDs manually, the attachment must be publicly readable on pre-login pages.
- If you use direct image URLs, they must be reachable before login. Same-origin URLs are safest.
- Cross-origin image URLs may fail when drawn onto canvas unless the remote server is configured for appropriate CORS behavior.

If a custom background cannot be loaded, the frontend attempts to fall back to a bundled background image.

## Enable It for Admin, Tenant, and User Login

### Admin Login

In platform security settings:

1. Enable `login_captcha_enabled`
2. Set `captcha_provider = slider`
3. Optionally tune `captcha_enable_threshold_admin`

Expected result:

- Admin login page receives `captcha_provider = slider`
- Public platform config also includes a `captcha_plugin` runtime payload

### Tenant Admin Login and Tenant User Login

In tenant security settings:

1. Enable `tenant_captcha_enabled`
2. Set `tenant_captcha_provider = slider`
3. Optionally tune `tenant_captcha_enable_threshold`

Expected result:

- Tenant login page uses the slider plugin
- User login page also uses the same tenant provider

### Tenant User Registration

Registration uses tenant-side provider selection but has its own captcha requirement switch.

To require registration captcha:

1. Enable tenant registration
2. Enable `user_registration_captcha_enabled`
3. Keep `tenant_captcha_provider = slider`

Expected result:

- The registration page uses the same slider provider when captcha is required

## Verification Checklist

### Automated Check

```bash
pytest backend/tests/plugins/test_slider_captcha_plugin.py
```

This covers:

- Provider loading
- Challenge generation
- Background override URL resolution
- Verification roundtrip
- Dynamic captcha option injection

### Manual API Checks

Admin public config:

```bash
curl http://localhost:8000/api/public/platform/config
```

Tenant public config:

```bash
curl http://localhost:8000/api/public/tenant/config
```

Expected when active:

- `captcha_provider` is `slider`
- `captcha_plugin.plugin_name` is `slider-captcha`

Challenge request:

```bash
curl -X POST http://localhost:8000/api/public/captcha/challenge \
  -H "Content-Type: application/json" \
  -d "{\"action\":\"login\",\"endpoint\":\"admin\",\"provider_code\":\"slider\"}"
```

Expected when active:

- response `data.type = "slider"`
- response contains `challenge_id`
- response contains slider payload fields such as `canvas_width`, `piece_y`, and background data

### Manual UI Checks

Check each flow:

1. Admin login shows the slider UI
2. Tenant admin login shows the slider UI
3. User login shows the slider UI
4. User registration shows the slider UI when registration captcha is required
5. Refresh action loads a new challenge
6. Broken custom background still falls back to a bundled background instead of blocking login entirely

## Fallback and Troubleshooting

### Provider Not Visible in Config Dropdown

Symptoms:

- `slider` does not appear in captcha provider select options

Check:

- Plugin is installed and enabled
- Plugin manifest metadata is synced
- The current endpoint is listed in `public_endpoints`

If the plugin scope or manifest was changed after initial install, run plugin repair or re-enable the plugin so metadata is refreshed.

### Login Page Falls Back to Built-in Image CAPTCHA

Symptoms:

- Config was set to `slider`, but the login page shows the built-in image captcha

Meaning:

- The host could not load the plugin frontend runtime and fell back to the built-in provider

Check:

- Browser console warnings from the captcha plugin loader
- Public config response contains `captcha_plugin`
- Network requests for public plugin assets
- Release manifest and `index.js` existence in production mode

Useful request paths:

- `/plugin-public-assets/admin/slider-captcha/...`
- `/plugin-public-assets/tenant/slider-captcha/...`
- `/plugin-public-assets/user/slider-captcha/...`

### Challenge Generates but Verify Randomly Fails

Symptoms:

- Users can drag successfully, but login fails with invalid captcha
- Failures appear intermittent across requests

Primary cause:

- Challenge generation and verification hit different workers or instances

Check:

- Number of backend workers
- Load balancer sticky session configuration
- Pod or worker restarts
- Challenge age greater than 120 seconds

### Background Override Does Not Display

Symptoms:

- Bundled image appears instead of the configured override
- Image fails to render on login page

Check:

- Attachment is public
- Manual URL is reachable from a pre-login page
- URL is same-origin or CORS-compatible for canvas rendering

### Useful Logs

Start with:

- `logs/captcha.log`
- `logs/auth.log`

These are the first places to check for challenge generation, verification failure, and login-side captcha enforcement behavior.

## Known Limitations and Follow-up Work

Current known limitations:

- In-memory challenge store only
- 120-second challenge TTL
- Not suitable for non-sticky scale-out by default
- Background override URL handling is permissive and depends on the operator providing public/canvas-safe URLs
- Current implementation is integration-oriented, not hardened as a dedicated anti-bot product

Recommended future work:

- Move challenge store to Redis or another shared cache
- Add stronger challenge proof and anti-replay hardening
- Formalize release-manifest generation in the plugin build pipeline
- Add plugin-specific frontend tests for public login integration
