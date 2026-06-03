# NovusAI 前端

本目录是 NovusAI 前端 workspace。它基于 Vben Admin，但本仓正式产品应用是 `apps/web-antd`，不是上游 playground。

## 入口

- 主应用：`apps/web-antd`
- Workspace 清单：`pnpm-workspace.yaml`
- 根脚本：`package.json`
- 前端规范：`../.agent/trellis/spec/frontend/index.md`
- 正式 workflow：`../.agent/trellis/workflow.md`

## 环境要求

- Node.js `>=20.19.0`
- pnpm `>=10.0.0`（workspace package manager: `pnpm@10.28.2`）

## 本地开发

```bash
cd frontend
pnpm install
pnpm dev:antd
```

默认开发端口由 `apps/web-antd/.env.development` 配置（`VITE_PORT=5666`）。默认 API 地址为 `VITE_GLOB_API_URL=http://127.0.0.1:8000`。

## 检查命令

```bash
cd frontend
pnpm lint
pnpm test:unit
pnpm build:antd
```

主应用定向类型检查：

```bash
pnpm exec vue-tsc --noEmit --skipLibCheck --pretty false -p apps/web-antd/tsconfig.json
```

## 上游参考

Vben 上游文档仍可作为框架行为参考，但 NovusAI 的本地命令、路由、权限和页面模式以 Trellis 前端规范与当前 `apps/web-antd` 代码为准。
