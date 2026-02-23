/**
 * 虚拟模块类型声明
 *
 * novus-plugins-loader Vite 插件生成的虚拟模块
 */
declare module 'virtual:novus-plugins-registry' {
  export const BUILTIN_PLUGINS: Record<
    string,
    () => Promise<Record<string, unknown>>
  >;
}

declare module 'virtual:novus-plugin-*' {
  const mod: Record<string, unknown>;
  export default mod;
  export const setup: (() => void) | undefined;
}
