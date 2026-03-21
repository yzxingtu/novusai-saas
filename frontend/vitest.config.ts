import { fileURLToPath } from 'node:url';

import Vue from '@vitejs/plugin-vue';
import VueJsx from '@vitejs/plugin-vue-jsx';
import { configDefaults, defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [Vue(), VueJsx()],
  resolve: {
    alias: {
      '#/adapter': fileURLToPath(
        new URL('./apps/web-antd/src/core/adapter', import.meta.url),
      ),
      '#': fileURLToPath(new URL('./apps/web-antd/src', import.meta.url)),
    },
  },
  test: {
    environment: 'happy-dom',
    exclude: [...configDefaults.exclude, '**/e2e/**'],
  },
});
