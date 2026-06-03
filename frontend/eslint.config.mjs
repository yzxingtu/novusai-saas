// @ts-check

import { defineConfig } from '@vben/eslint-config';

export default defineConfig([
  {
    ignores: [
      '.vendor/**',
      'apps/web-antd/build/*.js',
      'apps/web-antd/build/*.test.ts',
      'apps/web-antd/build/__tests__/**',
    ],
  },
  {
    // Keep web-antd source files on the app tsconfig so new helpers under src/**
    // do not accidentally participate in tsconfig.node project matching.
    files: ['apps/web-antd/src/**/*.{ts,tsx,vue}'],
    languageOptions: {
      parserOptions: {
        project: ['apps/web-antd/tsconfig.json'],
      },
    },
  },
  {
    // 交由 Prettier 统一处理模板换行，避免与 Vue closing bracket 规则循环修复
    rules: {
      'vue/html-closing-bracket-newline': 'off',
    },
  },
  {
    // Vue 模板插值 {{ value }} 与该规则存在误报，交由 Prettier 统一处理
    files: ['**/*.vue'],
    rules: {
      'unicorn/empty-brace-spaces': 'off',
    },
  },
  {
    // Prettier 和 vue/html-closing-bracket-newline 规则冲突
    // 这些文件的模板中有大量 code 标签嵌套，导致循环修复
    files: [
      'apps/web-antd/src/components/business/icon-picker/icon-picker.vue',
      'apps/web-antd/src/views/admin/system/organization/index.vue',
      'apps/web-antd/src/views/tenant/system/organization/index.vue',
    ],
    rules: {
      'vue/html-closing-bracket-newline': 'off',
    },
  },
]);
