import process from 'node:process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { defineConfig } from '@vben/vite-config';

import { loadEnv } from 'vite';

// @ts-ignore — dual vite versions in monorepo cause Plugin type mismatch
import { novusPluginsLoader } from './build/vite-plugin-novus-plugins';

const DEFAULT_PROXY_TARGET = 'http://127.0.0.1:8000';

// Read global version from VERSION file at repo root
function readAppVersion(): string {
  try {
    const versionPath = fileURLToPath(
      new URL('../../../VERSION', import.meta.url),
    );
    return readFileSync(versionPath, 'utf8').trim();
  } catch {
    return 'dev';
  }
}

function resolveProxyTarget(rawApiUrl?: string): string {
  const normalized = rawApiUrl?.trim();
  if (!normalized) {
    return DEFAULT_PROXY_TARGET;
  }

  try {
    const parsed = new URL(normalized);
    if (!/^https?:$/.test(parsed.protocol)) {
      return DEFAULT_PROXY_TARGET;
    }
    return parsed.origin;
  } catch {
    return DEFAULT_PROXY_TARGET;
  }
}

export default defineConfig(async ({ mode }) => {
  const pluginsDir = fileURLToPath(
    new URL('../../../backend/plugins', import.meta.url),
  );
  const persistedStateEntry = fileURLToPath(
    new URL(
      '../../packages/stores/node_modules/pinia-plugin-persistedstate/dist/index.js',
      import.meta.url,
    ),
  );
  const sharedSourceAliases = {
    '@vben-core/shared/cache': fileURLToPath(
      new URL(
        '../../packages/@core/base/shared/src/cache/index.ts',
        import.meta.url,
      ),
    ),
    '@vben-core/shared/color': fileURLToPath(
      new URL(
        '../../packages/@core/base/shared/src/color/index.ts',
        import.meta.url,
      ),
    ),
    '@vben-core/shared/constants': fileURLToPath(
      new URL(
        '../../packages/@core/base/shared/src/constants/index.ts',
        import.meta.url,
      ),
    ),
    '@vben-core/shared/global-state': fileURLToPath(
      new URL(
        '../../packages/@core/base/shared/src/global-state.ts',
        import.meta.url,
      ),
    ),
    '@vben-core/shared/store': fileURLToPath(
      new URL('../../packages/@core/base/shared/src/store.ts', import.meta.url),
    ),
    '@vben-core/shared/utils': fileURLToPath(
      new URL(
        '../../packages/@core/base/shared/src/utils/index.ts',
        import.meta.url,
      ),
    ),
  };
  const env = loadEnv(mode, process.cwd(), '');
  const pluginProxyTarget = resolveProxyTarget(env.VITE_GLOB_API_URL);

  return {
    application: {},
    vite: {
      define: {
        __APP_VERSION__: JSON.stringify(readAppVersion()),
      },
      plugins: [
        novusPluginsLoader({
          pluginsDir,
        }) as any,
      ],
      resolve: {
        alias: {
          '#/adapter': '/src/core/adapter',
          // Keep client builds on the browser runtime entry and avoid Nuxt-only subpath scanning.
          'pinia-plugin-persistedstate': persistedStateEntry,
          ...sharedSourceAliases,
        },
      },
      server: {
        allowedHosts: true,
        proxy: {
          '/plugin-assets': {
            changeOrigin: true,
            target: pluginProxyTarget,
          },
          '/plugin-public-assets': {
            changeOrigin: true,
            target: pluginProxyTarget,
          },
          '/plugin-icons': {
            changeOrigin: true,
            target: pluginProxyTarget,
          },
        },
      },
    },
  };
});
