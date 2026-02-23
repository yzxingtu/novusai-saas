import { resolve } from 'node:path';

import { defineConfig } from '@vben/vite-config';

// @ts-ignore — dual vite versions in monorepo cause Plugin type mismatch
import { novusPluginsLoader } from './src/utils/vite-plugin-novus-plugins';

export default defineConfig(async () => {
  return {
    application: {},
    vite: {
      plugins: [
        novusPluginsLoader({
          pluginsDir: resolve(__dirname, '../../../backend/plugins'),
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
