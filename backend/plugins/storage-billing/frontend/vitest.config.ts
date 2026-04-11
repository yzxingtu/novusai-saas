import path from 'node:path';
import { fileURLToPath } from 'node:url';

import Vue from '@vitejs/plugin-vue';
import { defineConfig } from '../../../../frontend/node_modules/vitest/dist/config.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [Vue()],
  test: {
    environment: 'happy-dom',
    include: ['src/**/*.test.{ts,tsx}'],
  },
  resolve: {
    alias: {
      '@novus/plugin-shared': path.resolve(
        __dirname,
        'src/test-support/plugin-shared-stub.ts',
      ),
      'ant-design-vue': path.resolve(
        __dirname,
        '../../../../frontend/apps/web-antd/node_modules/ant-design-vue',
      ),
      vue: path.resolve(
        __dirname,
        'node_modules/vue',
      ),
    },
  },
});
