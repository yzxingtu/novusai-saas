import { fileURLToPath } from 'node:url';

import { defineConfig } from '@vben/vite-config';

// @ts-ignore — dual vite versions in monorepo cause Plugin type mismatch
import { novusPluginsLoader } from './src/utils/vite-plugin-novus-plugins';

export default defineConfig(async () => {
  const pluginsDir = fileURLToPath(
    new URL('../../../backend/plugins', import.meta.url),
  );

  return {
    application: {},
    vite: {
      plugins: [
        novusPluginsLoader({
          pluginsDir,
        }) as any,
      ],
      resolve: {
        alias: {
          '#/adapter': '/src/core/adapter',
        },
      },
      server: {
        allowedHosts: true,
        proxy: {
          '/plugin-assets': {
            changeOrigin: true,
            target: 'http://127.0.0.1:8000',
          },
        },
      },
    },
  };
});
