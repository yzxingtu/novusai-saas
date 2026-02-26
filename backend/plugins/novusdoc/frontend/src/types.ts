/**
 * 宿主共享 API 类型声明（仅用于类型提示，不打入 bundle）
 */
export interface NovusPluginSharedAPI {
  requestClient: {
    get: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>;
    post: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>;
  };
  $t: (key: string, ...args: unknown[]) => string;
  IconifyIcon: unknown;
  usePluginSlotsStore: () => unknown;
  registerLocale: (locale: string, prefix: string, messages: Record<string, unknown>) => void;
}
