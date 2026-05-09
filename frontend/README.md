# NovusAI Frontend

This directory is the NovusAI frontend workspace. It is based on Vben Admin, but the checked-in product app is `apps/web-antd`, not the upstream playground.

## Entry Points

- Main app: `apps/web-antd`
- Workspace manifest: `pnpm-workspace.yaml`
- Root scripts: `package.json`
- Frontend spec: `../.trellis/spec/frontend/index.md`
- Canonical workflow: `../.trellis/workflow.md`

## Requirements

- Node.js `>=20.19.0`
- pnpm `>=10.0.0` (workspace package manager: `pnpm@10.28.2`)

## Local Development

```bash
cd frontend
pnpm install
pnpm dev:antd
```

The default dev server port is configured by `apps/web-antd/.env.development` (`VITE_PORT=5666`). The default API base is `VITE_GLOB_API_URL=http://localhost:8000`.

## Checks

```bash
cd frontend
pnpm lint
pnpm test:unit
pnpm build:antd
```

For targeted app type checks:

```bash
pnpm exec vue-tsc --noEmit --skipLibCheck --pretty false -p apps/web-antd/tsconfig.json
```

## Upstream Reference

The Vben upstream docs remain useful for framework behavior, but NovusAI local commands, routes, permissions, and page patterns are governed by the Trellis frontend spec and the current `apps/web-antd` code.
