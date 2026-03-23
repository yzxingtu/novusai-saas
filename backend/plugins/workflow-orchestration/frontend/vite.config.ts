import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

const GLOBAL_VAR = 'NovusPlugin_workflow_orchestration';

function emitReleaseManifest() {
  return {
    closeBundle() {
      const distDir = resolve(__dirname, 'dist');
      mkdirSync(distDir, { recursive: true });
      writeFileSync(
        resolve(distDir, 'plugin.manifest.json'),
        `${JSON.stringify(
          {
            format: 'novus.plugin.release.v1',
            entry: 'index.js',
            global_var: GLOBAL_VAR,
            css: [],
            assets: [],
          },
          null,
          2,
        )}\n`,
        'utf-8',
      );
    },
    name: 'workflow-orchestration-release-manifest',
  };
}

export default defineConfig({
  plugins: [vue(), emitReleaseManifest()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/index.ts'),
      name: GLOBAL_VAR,
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
        assetFileNames: 'assets/[name][extname]',
      },
    },
    cssCodeSplit: false,
    minify: 'esbuild',
  },
});
