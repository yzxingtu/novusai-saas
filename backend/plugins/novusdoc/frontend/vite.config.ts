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
      name: 'NovusPlugin_novusdoc',
      formats: ['umd'],
      fileName: () => 'index.js',
    },
    rollupOptions: {
      external: [
        'vue', 'vue-router', 'ant-design-vue', '@novus/plugin-shared', '@vben/common-ui', '@vben/icons',
        // @tiptap/* and lowlight are bundled directly into the UMD to avoid host globals complexity
      ],
      output: {
        globals: {
          vue: 'Vue',
          'vue-router': 'VueRouter',
          'ant-design-vue': 'AntDesignVue',
          '@novus/plugin-shared': 'NovusPluginShared',
          '@vben/common-ui': 'VbenCommonUI',
          '@vben/icons': 'VbenIcons',
        },
        assetFileNames: '[name][extname]',
      },
    },
    cssCodeSplit: false,
    minify: 'esbuild',
  },
});
