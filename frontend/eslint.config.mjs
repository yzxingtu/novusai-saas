// @ts-check

import { defineConfig } from '@vben/eslint-config';

export default defineConfig([
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
