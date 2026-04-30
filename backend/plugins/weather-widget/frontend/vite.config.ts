/**
 * 插件前端 UMD 构建配置
 *
 * 产物: dist/index.js (UMD 格式)
 * 宿主依赖通过 window 全局变量引用，不打入 bundle。
 */
import { mkdirSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

const GLOBAL_VAR = 'NovusPlugin_weather_widget';

function collectDistFiles(rootDir: string): string[] {
  const results: string[] = [];

  function walk(currentDir: string, relativePrefix = '') {
    for (const entry of readdirSync(currentDir, { withFileTypes: true })) {
      const relativePath = relativePrefix
        ? `${relativePrefix}/${entry.name}`
        : entry.name;
      const absolutePath = resolve(currentDir, entry.name);

      if (entry.isDirectory()) {
        walk(absolutePath, relativePath);
        continue;
      }

      if (statSync(absolutePath).isFile()) {
        results.push(relativePath.replaceAll('\\', '/'));
      }
    }
  }

  walk(rootDir);
  return results.sort();
}

function emitReleaseManifest() {
  return {
    closeBundle() {
      const distDir = resolve(__dirname, 'dist');
      mkdirSync(distDir, { recursive: true });
      const distFiles = collectDistFiles(distDir).filter(
        (file) => file !== 'plugin.manifest.json',
      );
      const cssFiles = distFiles.filter((file) => file.endsWith('.css'));
      const otherAssets = distFiles.filter(
        (file) => file !== 'index.js' && !file.endsWith('.css'),
      );

      writeFileSync(
        resolve(distDir, 'plugin.manifest.json'),
        `${JSON.stringify(
          {
            format: 'novus.plugin.release.v1',
            entry: 'index.js',
            global_var: GLOBAL_VAR,
            css: cssFiles,
            assets: otherAssets,
          },
          null,
          2,
        )}\n`,
        'utf-8',
      );
    },
    name: 'weather-widget-release-manifest',
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
      external: ['vue', 'vue-router', 'ant-design-vue', '@novus/plugin-shared'],
      output: {
        globals: {
          vue: 'Vue',
          'vue-router': 'VueRouter',
          'ant-design-vue': 'AntDesignVue',
          '@novus/plugin-shared': 'NovusPluginShared',
        },
        assetFileNames: '[name][extname]',
      },
    },
    cssCodeSplit: false,
    minify: 'esbuild',
  },
});
