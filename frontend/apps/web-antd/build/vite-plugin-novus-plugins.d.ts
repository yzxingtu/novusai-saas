import type { Plugin } from 'vite';

export interface NovusPluginsOptions {
  pluginsDir?: string;
}

export declare function novusPluginsLoader(
  options?: NovusPluginsOptions,
): Plugin;
