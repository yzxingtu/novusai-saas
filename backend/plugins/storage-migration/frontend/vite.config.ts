/**
 * 插件前端 UMD 构建配置
 */
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'node:path';

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/index.ts'),
      name: 'NovusPlugin_storage_migration',
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