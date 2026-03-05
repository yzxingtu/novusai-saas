/**
 * DataForge Studio 插件前端 UMD 构建配置
 *
 * vue / vue-router / ant-design-vue / @vben/* / @novus/plugin-shared 由宿主提供（external）。
 * @vue-flow/* / sortablejs 打包进 bundle。
 */
import { resolve } from 'node:path';

import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/index.ts'),
      name: 'NovusPlugin_novus_crud_code',
      formats: ['umd'],
      fileName: () => 'index.js',
    },
    rollupOptions: {
      external: [
        'vue',
        'vue-router',
        'ant-design-vue',
        '@vben/common-ui',
        '@vben/icons',
        '@novus/plugin-shared',
      ],
      output: {
        globals: {
          vue: 'Vue',
          'vue-router': 'VueRouter',
          'ant-design-vue': 'AntDesignVue',
          '@vben/common-ui': 'VbenCommonUi',
          '@vben/icons': 'VbenIcons',
          '@novus/plugin-shared': 'NovusPluginShared',
        },
        assetFileNames: '[name][extname]',
      },
    },
    cssCodeSplit: false,
    minify: 'esbuild',
  },
});
